"""Deterministic request hashing for cache and audit purposes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from urllib.parse import parse_qsl, urlsplit

from src.ingestion.redaction import is_secret_key


def _normalize_value(value: object) -> object:
    if isinstance(value, Mapping):
        return normalize_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_value(item) for item in value]
    return value


def normalize_mapping(mapping: Mapping[str, object] | None) -> dict[str, object]:
    if not mapping:
        return {}
    normalized: dict[str, object] = {}
    for key in sorted(mapping):
        if is_secret_key(key):
            normalized[key] = "<redacted>"
        else:
            normalized[key] = _normalize_value(mapping[key])
    return normalized


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    normalized_query = {
        key: "<redacted>" if is_secret_key(key) else value
        for key, value in sorted(query_pairs, key=lambda item: item[0])
    }
    payload = {
        "scheme": parts.scheme,
        "netloc": parts.netloc,
        "path": parts.path,
        "query": normalized_query,
    }
    return stable_json_dumps(payload)


def stable_json_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_request_hash(
    *,
    source: str,
    endpoint: str,
    method: str,
    params: Mapping[str, object] | None = None,
    json_body: Mapping[str, object] | None = None,
    raw_body: str | None = None,
) -> str:
    canonical_payload = {
        "source": source.lower(),
        "endpoint": normalize_url(endpoint),
        "method": method.upper(),
        "params": normalize_mapping(params),
        "json_body": normalize_mapping(json_body),
        "raw_body": raw_body or "",
    }
    return hashlib.sha256(stable_json_dumps(canonical_payload).encode("utf-8")).hexdigest()
