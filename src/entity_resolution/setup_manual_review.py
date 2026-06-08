"""Create database objects used for entity-resolution manual review."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root


def manual_review_sql_path() -> Path:
    return project_root() / "sql" / "ml" / "create_manual_review_tables.sql"


def apply_manual_review_schema(repository: IngestionRepository | None = None) -> None:
    repository = repository or IngestionRepository()
    sql_text = manual_review_sql_path().read_text(encoding="utf-8")
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql_text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create manual-review tables and views for entity resolution."
    )
    parser.add_argument("--dry-run", action="store_true", help="Show SQL path without applying it.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = manual_review_sql_path()
    if args.dry_run:
        print({"sql_path": str(path)})
        return 0
    apply_manual_review_schema()
    print({"manual_review_schema": "ready", "sql_path": str(path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
