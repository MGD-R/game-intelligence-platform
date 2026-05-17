"""Load targeted Wikipedia summaries into raw.wikipedia_pages."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.ingestion.cli import build_common_parser
from src.ingestion.jobs.select_wikipedia_pages import (
    default_limit,
    select_pages_from_url_rows,
)
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.wikipedia_client import WikipediaClient


def default_page_limit() -> int:
    return int(os.getenv("WIKIPEDIA_PAGE_LIMIT", default_limit()))


def parse_pages_file(path: str) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        values.append(json.loads(stripped))
    return values


def normalize_selection(
    *,
    title: str | None = None,
    language: str | None = None,
    pages_file: str | None = None,
) -> list[dict[str, str]]:
    if title:
        return [
            {
                "source_game_id": "",
                "qid": "",
                "language": language or "en",
                "title": title,
                "url": "",
                "url_type": f"{language or 'en'}wiki",
            }
        ]
    if pages_file:
        return parse_pages_file(pages_file)
    return []


def build_wrapped_response(
    page: dict[str, str],
    payload: dict[str, Any] | str,
) -> dict[str, Any]:
    return {
        "selection": {
            "qid": page.get("qid"),
            "language": page.get("language"),
            "title": page.get("title"),
            "url": page.get("url"),
            "url_type": page.get("url_type"),
        },
        "response": payload,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load targeted Wikipedia summary pages.")
    parser.add_argument("--pages-file", help="JSONL file created by select_wikipedia_pages.")
    parser.add_argument("--title", help="Single explicit Wikipedia page title.")
    parser.add_argument(
        "--language",
        choices=("ru", "en"),
        help="Language for explicit --title mode.",
    )
    parser.set_defaults(limit=default_page_limit())
    args = parser.parse_args(argv)

    explicit_pages = normalize_selection(
        title=args.title,
        language=args.language,
        pages_file=args.pages_file,
    )
    preview = (
        explicit_pages[0]
        if explicit_pages
        else {
            "language": "en",
            "title": "Selected from Wikidata sitelinks",
        }
    )

    if args.dry_run:
        client = WikipediaClient(repository=None)
        response = client.get_page_summary(
            preview["language"],
            preview["title"],
            dry_run=True,
            force_refresh=args.force_refresh,
            from_cache_only=args.from_cache_only,
        )
        print(
            {
                "selection_source": "explicit_pages" if explicit_pages else "wikidata_sitelinks",
                "limit": args.limit,
                "request_preview": response.request_metadata,
            }
        )
        return 0

    client = WikipediaClient()
    logger = PipelineRunLogger(
        pipeline_name="wikipedia_pages",
        stage_name="raw",
        repository=client.repository,
    )
    logger.mark_started(parameters={"limit": args.limit})

    try:
        pages = explicit_pages
        if not pages:
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for Wikipedia selection")
            rows = client.repository.fetch_staging_rows("stg.source_game_urls", source="wikidata")
            pages = select_pages_from_url_rows(rows, limit=max(1, args.limit))
        if not pages:
            raise RuntimeError(
                "No Wikipedia sitelinks found for targeted summaries. "
                "Run `make wikidata-demo` and `make staging` first."
            )
        pages = pages[: max(1, args.limit)]

        for page in pages:
            response = client.get_page_summary(
                page["language"],
                page["title"],
                dry_run=False,
                force_refresh=args.force_refresh,
                from_cache_only=args.from_cache_only,
            )
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for Wikipedia page load")
            client.repository.insert_raw_record(
                table_name="raw.wikipedia_pages",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=f"{page['language']}:{page['title']}",
                response_json=build_wrapped_response(page, response.payload),
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )

        logger.mark_finished(status="completed", metrics={"requested_pages": len(pages)})
        print({"loaded_pages": pages})
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
