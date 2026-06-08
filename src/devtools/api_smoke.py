"""Smoke-check the local FastAPI demo API."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SmokeRequest:
    method: str
    path: str
    body: dict[str, Any] | None = None


DEFAULT_REQUESTS = (
    SmokeRequest("GET", "/health"),
    SmokeRequest("GET", "/version"),
    SmokeRequest("GET", "/stats/catalog"),
    SmokeRequest("GET", "/stats/ml"),
    SmokeRequest("GET", "/stats/readiness"),
    SmokeRequest("GET", "/stats/graph"),
    SmokeRequest("GET", "/games?limit=1"),
    SmokeRequest("GET", "/matches/review?limit=1&review_status=all"),
    SmokeRequest("GET", "/explain/recommendation?limit=1"),
    SmokeRequest("GET", "/explain/match?limit=1"),
    SmokeRequest("POST", "/recommend", {"liked_games": ["DOOM"], "limit": 1}),
)


def request_json(base_url: str, item: SmokeRequest, timeout: float) -> tuple[int, dict[str, Any]]:
    url = f"{base_url.rstrip('/')}{item.path}"
    data = json.dumps(item.body).encode("utf-8") if item.body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=item.method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        return exc.code, json.loads(payload) if payload else {}


def run_smoke(base_url: str, timeout: float = 5.0) -> list[dict[str, Any]]:
    results = []
    for item in DEFAULT_REQUESTS:
        try:
            status_code, payload = request_json(base_url, item, timeout)
            ok = 200 <= status_code < 300
            results.append(
                {
                    "method": item.method,
                    "path": item.path,
                    "status_code": status_code,
                    "ok": ok,
                    "warning_count": len(payload.get("warnings") or [])
                    if isinstance(payload, dict)
                    else 0,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "method": item.method,
                    "path": item.path,
                    "status_code": None,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-check FastAPI demo endpoints.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://localhost:8000"),
        help="FastAPI base URL.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = run_smoke(args.base_url)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"API smoke base URL: {args.base_url}")
        for row in results:
            marker = "OK" if row["ok"] else "FAIL"
            print(f"{marker} {row['method']} {row['path']} -> {row['status_code']}")
    return 0 if all(row["ok"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
