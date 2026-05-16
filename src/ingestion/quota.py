"""Reusable quota tracking helpers."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import UTC, datetime

from src.ingestion.repository import IngestionRepository
from src.utils.config import load_yaml_config

QUOTA_ENV_BY_SOURCE = {
    "rawg": "RAWG_MONTHLY_LIMIT",
}


class QuotaExceededError(RuntimeError):
    """Raised when a source quota has been exhausted."""


@dataclass(frozen=True, slots=True)
class QuotaStatus:
    source: str
    quota_period: str
    used: int
    limit: int | None


def quota_period_for_month(at: datetime | None = None) -> str:
    current = at or datetime.now(UTC)
    return current.strftime("%Y-%m")


def get_quota_limit(source: str) -> int | None:
    env_name = QUOTA_ENV_BY_SOURCE.get(source.lower())
    if not env_name:
        return None
    value = os.getenv(env_name)
    return int(value) if value else None


def ensure_quota_available(
    repository: IngestionRepository | None,
    source: str,
    at: datetime | None = None,
) -> QuotaStatus:
    quota_period = quota_period_for_month(at)
    limit = get_quota_limit(source)
    if repository is None or limit is None:
        return QuotaStatus(source=source, quota_period=quota_period, used=0, limit=limit)

    existing = repository.read_quota_usage(source, quota_period)
    used = int(existing["request_count"]) if existing else 0
    if used >= limit:
        raise QuotaExceededError(
            f"Quota reached for {source}: used {used} of {limit} in period {quota_period}"
        )
    return QuotaStatus(source=source, quota_period=quota_period, used=used, limit=limit)


def record_quota_usage(
    repository: IngestionRepository | None, source: str, amount: int = 1
) -> None:
    if repository is None:
        return
    limit = get_quota_limit(source)
    repository.increment_quota_usage(
        source=source,
        quota_period=quota_period_for_month(),
        amount=amount,
        quota_limit=limit,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect configured source quotas.")
    parser.add_argument("--status", action="store_true", help="Show configured quota state.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.status:
        print("Use --status to inspect configured quotas.")
        return 0

    repository: IngestionRepository | None
    try:
        repository = IngestionRepository()
    except Exception:
        repository = None

    sources = load_yaml_config("sources").get("sources", {})
    period = quota_period_for_month()
    print(f"Quota status for period {period}:")
    for source_name in sources:
        limit = get_quota_limit(source_name)
        usage = "unavailable"
        if repository is not None:
            try:
                existing = repository.read_quota_usage(source_name, period)
                usage = str(existing["request_count"]) if existing else "0"
            except Exception:
                usage = "unavailable"
        print(f"- {source_name}: used={usage}, limit={limit if limit is not None else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
