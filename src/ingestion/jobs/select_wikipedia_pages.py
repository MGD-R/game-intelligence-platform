"""Select targeted Wikipedia pages from Wikidata sitelink staging rows."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.ingestion.cli import build_common_parser
from src.ingestion.repository import IngestionRepository
from src.ingestion.wikipedia_client import load_wikipedia_settings


def default_limit() -> int:
    settings = load_wikipedia_settings()
    return int(os.getenv("WIKIPEDIA_PAGE_LIMIT", settings.get("demo_limit", 100)))


def language_from_url_type(url_type: str) -> str | None:
    mapping = {"ruwiki": "ru", "enwiki": "en"}
    return mapping.get(url_type)


def title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    title = path.rsplit("/", maxsplit=1)[-1]
    return unquote(title).replace("_", " ")


def select_pages_from_url_rows(
    rows: list[dict[str, object]],
    *,
    languages: set[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if row.get("source") != "wikidata":
            continue
        url_type = str(row.get("url_type") or "")
        language = language_from_url_type(url_type)
        if language is None:
            continue
        if languages and language not in languages:
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        title = title_from_url(url)
        key = (language, title)
        if key in seen:
            continue
        seen.add(key)
        selected.append(
            {
                "source_game_id": str(row.get("source_game_id") or ""),
                "qid": str(row.get("source_game_id") or ""),
                "language": language,
                "title": title,
                "url": url,
                "url_type": url_type,
            }
        )
        if limit is not None and len(selected) >= limit:
            break
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser(
        "Select Wikipedia page titles from Wikidata sitelink staging rows."
    )
    parser.add_argument(
        "--language",
        action="append",
        choices=("ru", "en"),
        help="Optional language filter; may be passed more than once.",
    )
    parser.add_argument("--output-file", help="Optional JSONL output file with selected page rows.")
    parser.set_defaults(limit=default_limit())
    args = parser.parse_args(argv)

    language_set = set(args.language or [])
    if args.dry_run:
        print(
            {
                "selection_source": "stg.source_game_urls",
                "filters": {
                    "source": "wikidata",
                    "url_types": sorted(
                        ["ruwiki", "enwiki"]
                        if not language_set
                        else [f"{language}wiki" for language in sorted(language_set)]
                    ),
                },
                "limit": args.limit,
                "output_file": args.output_file,
            }
        )
        return 0

    repository = IngestionRepository()
    rows = repository.fetch_staging_rows("stg.source_game_urls", source="wikidata")
    pages = select_pages_from_url_rows(rows, languages=language_set or None, limit=args.limit)
    if not pages:
        raise RuntimeError(
            "No Wikipedia sitelinks found in Wikidata staging URLs. "
            "Run `make wikidata-by-rawg`, `make wikidata-staging`, and `make staging` first."
        )
    if args.output_file:
        output = "\n".join(json.dumps(page, ensure_ascii=True) for page in pages) + "\n"
        Path(args.output_file).write_text(output, encoding="utf-8")
    print(
        {
            "selected_count": len(pages),
            "pages": pages,
            "output_file": args.output_file,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
