"""Reusable base HTTP client for external ingestion sources."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from urllib.parse import urljoin

import httpx

from src.ingestion.http import RetryPolicy, execute_with_retry
from src.ingestion.quota import QuotaExceededError, ensure_quota_available, record_quota_usage
from src.ingestion.rate_limiter import RateLimiter, resolve_rate_limit
from src.ingestion.redaction import redact_headers, redact_mapping, redact_url
from src.ingestion.repository import IngestionRepository
from src.ingestion.request_cache import ResponseCache
from src.ingestion.request_hash import build_request_hash, stable_json_dumps
from src.utils.logging import configure_logging

LOGGER = configure_logging()


class CacheMissError(RuntimeError):
    """Raised when cache-only mode is requested and no cache entry exists."""


@dataclass(slots=True)
class IngestionResponse:
    source: str
    endpoint: str
    request_hash: str
    request_url: str
    http_status: int | None
    payload: Any
    response_hash: str | None
    from_cache: bool
    dry_run: bool
    cache_path: str | None
    request_metadata: dict[str, Any]
    error_message: str | None = None


@dataclass(slots=True)
class BaseAPIClient:
    source: str
    base_url: str
    timeout_seconds: int = 10
    default_headers: dict[str, str] = field(default_factory=dict)
    source_settings: dict[str, object] = field(default_factory=dict)
    cache: ResponseCache = field(default_factory=ResponseCache)
    repository: IngestionRepository | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    rate_limiter: RateLimiter | None = None

    def __post_init__(self) -> None:
        if self.rate_limiter is None:
            rate_limit = resolve_rate_limit(self.source, self.source_settings)
            self.rate_limiter = RateLimiter(rate_limit) if rate_limit else None

    def build_request_url(self, endpoint: str) -> str:
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return urljoin(f"{self.base_url.rstrip('/')}/", endpoint.lstrip("/"))

    def build_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        merged = dict(self.default_headers)
        if headers:
            merged.update(headers)
        return merged

    def build_params(self, params: dict[str, object] | None = None) -> dict[str, object]:
        return dict(params or {})

    def build_json_body(
        self, json_body: dict[str, object] | None = None
    ) -> dict[str, object] | None:
        return dict(json_body) if json_body else None

    def build_raw_body(self, raw_body: str | None = None) -> str | None:
        if raw_body is None:
            return None
        return str(raw_body)

    def request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        raw_body: str | None = None,
        headers: dict[str, str] | None = None,
        use_cache: bool = True,
        force_refresh: bool = False,
        dry_run: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        request_url = self.build_request_url(endpoint)
        request_params = self.build_params(params)
        request_headers = self.build_headers(headers)
        request_body = self.build_json_body(json_body)
        request_raw_body = self.build_raw_body(raw_body)
        request_hash = build_request_hash(
            source=self.source,
            endpoint=request_url,
            method=method,
            params=request_params,
            json_body=request_body,
            raw_body=request_raw_body,
        )
        request_metadata = {
            "source": self.source,
            "method": method.upper(),
            "url": redact_url(request_url),
            "params": redact_mapping(request_params),
            "headers": redact_headers(request_headers),
            "body": (
                redact_mapping(request_body)
                if request_body is not None
                else ({"raw_body": request_raw_body} if request_raw_body is not None else {})
            ),
        }

        if dry_run:
            return IngestionResponse(
                source=self.source,
                endpoint=endpoint,
                request_hash=request_hash,
                request_url=request_url,
                http_status=None,
                payload={"planned_request": request_metadata},
                response_hash=None,
                from_cache=False,
                dry_run=True,
                cache_path=None,
                request_metadata=request_metadata,
            )

        if use_cache and not force_refresh and self.cache.exists(self.source, request_hash):
            cached_entry = self.cache.read(self.source, request_hash)
            self._safe_record_cache_hit(
                endpoint=endpoint,
                request_hash=request_hash,
                request_url=request_url,
                request_params=request_params,
                request_body=request_body,
                cached_entry=cached_entry,
                method=method,
            )
            return IngestionResponse(
                source=self.source,
                endpoint=endpoint,
                request_hash=request_hash,
                request_url=request_url,
                http_status=cached_entry.get("http_status"),
                payload=cached_entry.get("response_json", cached_entry.get("response_text")),
                response_hash=cached_entry.get("response_hash"),
                from_cache=True,
                dry_run=False,
                cache_path=str(self.cache.cache_path(self.source, request_hash)),
                request_metadata=request_metadata,
            )

        if from_cache_only:
            raise CacheMissError(f"Cache miss for {self.source}:{request_hash}")

        quota_status = ensure_quota_available(self.repository, self.source)

        if self.rate_limiter is not None:
            self.rate_limiter.acquire()

        request_id = self._safe_insert_started_log(
            endpoint=endpoint,
            request_hash=request_hash,
            request_url=request_url,
            request_params=request_params,
            request_body=request_body,
            method=method,
        )

        started = monotonic()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = execute_with_retry(
                    lambda: client.request(
                        method.upper(),
                        request_url,
                        params=request_params,
                        json=request_body,
                        content=request_raw_body,
                        headers=request_headers,
                    ),
                    source=self.source,
                    retry_policy=self.retry_policy,
                )
        except Exception as exc:
            self._safe_update_finished_log(
                request_id=request_id,
                http_status=None,
                response_hash=None,
                response_storage_path=None,
                duration_ms=int((monotonic() - started) * 1000),
                error_message=f"{exc.__class__.__name__}: {exc}",
            )
            if isinstance(exc, QuotaExceededError):
                raise
            raise

        duration_ms = int((monotonic() - started) * 1000)
        payload: Any
        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        response_hash = hashlib.sha256(
            (stable_json_dumps(payload) if not isinstance(payload, str) else payload).encode(
                "utf-8"
            )
        ).hexdigest()
        cache_payload = {
            "source": self.source,
            "endpoint": endpoint,
            "request_hash": request_hash,
            "created_at": datetime.now(UTC).isoformat(),
            "http_status": response.status_code,
            "response_json": payload if not isinstance(payload, str) else None,
            "response_text": payload if isinstance(payload, str) else None,
            "response_hash": response_hash,
            "redacted_request_metadata": request_metadata,
        }
        cache_path = (
            self.cache.write(self.source, request_hash, cache_payload) if use_cache else None
        )
        self._safe_update_finished_log(
            request_id=request_id,
            http_status=response.status_code,
            response_hash=response_hash,
            response_storage_path=str(cache_path) if cache_path else None,
            duration_ms=duration_ms,
            error_message=None if response.status_code < 400 else f"HTTP {response.status_code}",
        )
        if quota_status.limit is not None:
            record_quota_usage(self.repository, self.source)

        return IngestionResponse(
            source=self.source,
            endpoint=endpoint,
            request_hash=request_hash,
            request_url=request_url,
            http_status=response.status_code,
            payload=payload,
            response_hash=response_hash,
            from_cache=False,
            dry_run=False,
            cache_path=str(cache_path) if cache_path else None,
            request_metadata=request_metadata,
            error_message=None if response.status_code < 400 else f"HTTP {response.status_code}",
        )

    def _safe_insert_started_log(
        self,
        *,
        endpoint: str,
        request_hash: str,
        request_url: str,
        request_params: dict[str, object],
        request_body: dict[str, object] | None,
        method: str,
    ) -> str | None:
        if self.repository is None:
            return None
        try:
            return self.repository.insert_started_request_log(
                source=self.source,
                endpoint=endpoint,
                request_method=method.upper(),
                request_url=request_url,
                request_params_json=request_params,
                request_body=request_body,
                request_hash=request_hash,
            )
        except Exception as exc:  # pragma: no cover - runtime integration path
            LOGGER.warning("Request log insert failed for %s: %s", self.source, exc)
            return None

    def _safe_update_finished_log(
        self,
        *,
        request_id: str | None,
        http_status: int | None,
        response_hash: str | None,
        response_storage_path: str | None,
        duration_ms: int | None,
        error_message: str | None,
    ) -> None:
        if self.repository is None or request_id is None:
            return
        try:
            self.repository.update_finished_request_log(
                request_id,
                http_status=http_status,
                response_hash=response_hash,
                response_storage_path=response_storage_path,
                duration_ms=duration_ms,
                error_message=error_message,
            )
        except Exception as exc:  # pragma: no cover - runtime integration path
            LOGGER.warning("Request log update failed for %s: %s", self.source, exc)

    def _safe_record_cache_hit(
        self,
        *,
        endpoint: str,
        request_hash: str,
        request_url: str,
        request_params: dict[str, object],
        request_body: dict[str, object] | None,
        cached_entry: dict[str, Any],
        method: str,
    ) -> None:
        if self.repository is None:
            return
        try:
            self.repository.record_cache_hit(
                source=self.source,
                endpoint=endpoint,
                request_method=method.upper(),
                request_url=request_url,
                request_params_json=request_params,
                request_body=request_body,
                request_hash=request_hash,
                http_status=cached_entry.get("http_status"),
                response_hash=cached_entry.get("response_hash"),
                response_storage_path=str(self.cache.cache_path(self.source, request_hash)),
            )
        except Exception as exc:  # pragma: no cover - runtime integration path
            LOGGER.warning("Cache hit log failed for %s: %s", self.source, exc)
