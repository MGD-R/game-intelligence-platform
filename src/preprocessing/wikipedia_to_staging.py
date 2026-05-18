"""Transform Wikipedia summary raw payloads into source-normalized staging tables."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.ingestion.repository import IngestionRepository


def normalize_description_text(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def wikipedia_source_game_id(
    language: str,
    title: str,
    page_id: int | None,
    qid: str | None,
) -> str:
    if qid:
        return qid
    if page_id is not None:
        return str(page_id)
    return f"{language}:{title.replace(' ', '_')}"


def unwrap_summary_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(payload.get("response"), dict):
        response = payload["response"]
        selection = payload.get("selection")
        if isinstance(selection, dict):
            return response, selection
    return payload, {}


def response_language(
    response: dict[str, Any],
    selection: dict[str, Any],
) -> str:
    page_url = ""
    content_urls = response.get("content_urls")
    if isinstance(content_urls, dict):
        desktop = content_urls.get("desktop", {})
        if isinstance(desktop, dict):
            page_url = str(desktop.get("page") or "")
    return str(
        selection.get("language") or response.get("lang") or page_url.split("//", 1)[-1][:2] or "en"
    ).strip()


@dataclass(slots=True)
class WikipediaStagingBundle:
    source_game_descriptions: list[dict[str, object]] = field(default_factory=list)
    source_game_urls: list[dict[str, object]] = field(default_factory=list)
    source_game_external_ids: list[dict[str, object]] = field(default_factory=list)


def transform_wikipedia_payloads(
    raw_payloads: list[tuple[dict[str, Any], str]],
) -> WikipediaStagingBundle:
    now = datetime.now(UTC).isoformat()
    bundle = WikipediaStagingBundle()
    seen_urls: set[tuple[str, str, str]] = set()
    seen_external_ids: set[tuple[str, str]] = set()

    for payload, loaded_at in raw_payloads:
        response, selection = unwrap_summary_payload(payload)
        if not isinstance(response, dict):
            continue
        title = str(response.get("title") or selection.get("title") or "").strip()
        language = response_language(response, selection)
        if not title:
            continue
        qid = str(selection.get("qid") or "").strip()
        page_id_raw = response.get("pageid")
        page_id = int(page_id_raw) if isinstance(page_id_raw, int) else None
        source_game_id = wikipedia_source_game_id(language, title, page_id, qid or None)
        extract = normalize_description_text(str(response.get("extract") or ""))
        page_url = (
            response.get("content_urls", {}).get("desktop", {}).get("page")
            if isinstance(response.get("content_urls"), dict)
            else None
        )

        if extract:
            bundle.source_game_descriptions.append(
                {
                    "source": "wikipedia",
                    "source_game_id": source_game_id,
                    "description_type": "summary",
                    "language": language,
                    "description_text": extract,
                    "source_url": page_url,
                    "source_specific_json": {
                        "title": title,
                        "normalized_title": title.replace(" ", "_"),
                        "page_id": page_id,
                        "lang": language,
                        "content_urls": response.get("content_urls", {}),
                        "qid": qid,
                        "loaded_at": loaded_at,
                    },
                    "stg_loaded_at": now,
                }
            )

        if page_url:
            url_key = (source_game_id, "page", str(page_url))
            if url_key not in seen_urls:
                seen_urls.add(url_key)
                bundle.source_game_urls.append(
                    {
                        "source": "wikipedia",
                        "source_game_id": source_game_id,
                        "url_type": "page",
                        "url": str(page_url),
                        "source_specific_json": {
                            "language": language,
                            "title": title,
                            "qid": qid,
                            "page_id": page_id,
                        },
                        "stg_loaded_at": now,
                    }
                )

        if qid:
            ext_key = (source_game_id, qid)
            if ext_key not in seen_external_ids:
                seen_external_ids.add(ext_key)
                bundle.source_game_external_ids.append(
                    {
                        "source": "wikipedia",
                        "source_game_id": source_game_id,
                        "external_source": "wikidata",
                        "external_id": qid,
                        "confidence": 1.0,
                        "source_specific_json": {
                            "language": language,
                            "title": title,
                            "page_id": page_id,
                        },
                        "stg_loaded_at": now,
                    }
                )

    return bundle


def load_wikipedia_payloads(
    repository: IngestionRepository,
) -> list[tuple[dict[str, Any], str]]:
    rows = repository.fetch_raw_rows("raw.wikipedia_pages")
    return [
        (row.get("response_json") or {}, str(row.get("loaded_at")))
        for row in rows
        if isinstance(row.get("response_json"), dict)
    ]


def write_bundle(repository: IngestionRepository, bundle: WikipediaStagingBundle) -> None:
    repository.replace_source_staging_rows(
        source="wikipedia",
        table_name="stg.source_game_descriptions",
        rows=bundle.source_game_descriptions,
        key_columns=["source", "source_game_id", "description_type", "language"],
    )
    repository.replace_source_staging_rows(
        source="wikipedia",
        table_name="stg.source_game_urls",
        rows=bundle.source_game_urls,
        key_columns=["source", "source_game_id", "url_type", "url"],
    )
    repository.replace_source_staging_rows(
        source="wikipedia",
        table_name="stg.source_game_external_ids",
        rows=bundle.source_game_external_ids,
        key_columns=["source", "source_game_id", "external_source", "external_id"],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transform Wikipedia summaries into staging rows.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview staging targets without DB reads or writes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "source": "wikipedia",
                "raw_table": "raw.wikipedia_pages",
                "target_tables": [
                    "stg.source_game_descriptions",
                    "stg.source_game_urls",
                    "stg.source_game_external_ids",
                ],
            }
        )
        return 0

    repository = IngestionRepository()
    payloads = load_wikipedia_payloads(repository)
    if not payloads:
        raise RuntimeError("Wikipedia raw pages are empty. Run `make wikipedia-load` first.")
    bundle = transform_wikipedia_payloads(payloads)
    write_bundle(repository, bundle)
    print(
        {
            "descriptions": len(bundle.source_game_descriptions),
            "urls": len(bundle.source_game_urls),
            "external_ids": len(bundle.source_game_external_ids),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
