"""Helpers for redacting secrets from logs and request metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "***REDACTED***"
SECRET_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "database_url",
    "key",
    "password",
    "postgres_password",
    "token",
    "user_agent",
}


def normalize_secret_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def is_secret_key(key: str) -> bool:
    normalized = normalize_secret_key(key)
    if normalized in SECRET_KEYS:
        return True
    return any(token in normalized for token in ("secret", "token", "password", "authorization"))


def redact_value(key: str, value: object) -> object:
    if is_secret_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(key, item) for item in value]
    return value


def redact_mapping(mapping: Mapping[str, object] | None) -> dict[str, object]:
    if not mapping:
        return {}
    return {key: redact_value(key, value) for key, value in mapping.items()}


def redact_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {key: str(redact_value(key, value)) for key, value in headers.items()}


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    redacted_query = [
        (key, REDACTED if is_secret_key(key) else value)
        for key, value in sorted(query, key=lambda item: item[0])
    ]
    if parts.username or parts.password:
        username = parts.username or ""
        password = REDACTED if parts.password else ""
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        netloc = f"{username}:{password}@{host}{port}" if username else f"{host}{port}"
    else:
        netloc = parts.netloc
    return urlunsplit(
        (
            parts.scheme,
            netloc,
            parts.path,
            urlencode(redacted_query, doseq=True),
            parts.fragment,
        )
    )


def redact_dsn(dsn: str) -> str:
    return redact_url(dsn)
