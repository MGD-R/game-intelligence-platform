"""Load targeted Wikidata EntityData payloads into raw storage."""

from __future__ import annotations

import os
from pathlib import Path

from src.ingestion.cli import build_common_parser
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.wikidata_client import WikidataClient


def parse_qids(raw_qids: str | None, qids_file: str | None) -> list[str]:
    values: list[str] = []
    if raw_qids:
        values.extend(part.strip() for part in raw_qids.split(",") if part.strip())
    if qids_file:
        values.extend(
            line.strip()
            for line in Path(qids_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return values


def default_limit() -> int:
    return int(os.getenv("WIKIDATA_ENTITY_LIMIT", "0"))


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load targeted Wikidata EntityData payloads.")
    parser.add_argument("--qids", help="Comma-separated Wikidata QIDs.")
    parser.add_argument("--qids-file", help="File with one Wikidata QID per line.")
    parser.set_defaults(limit=default_limit())
    args = parser.parse_args(argv)

    client = WikidataClient()
    logger = PipelineRunLogger(
        pipeline_name="wikidata_entities",
        stage_name="raw",
        repository=None if args.dry_run else client.repository,
    )
    logger.mark_started(parameters={"limit": args.limit})

    try:
        qids = parse_qids(args.qids, args.qids_file)
        if args.limit > 0:
            qids = qids[: args.limit]
        else:
            qids = []

        for qid in qids:
            response = client.get_entity_data(
                qid,
                dry_run=args.dry_run,
                force_refresh=args.force_refresh,
                from_cache_only=args.from_cache_only,
            )
            if response.dry_run:
                print({"qid": qid, "planned": response.request_metadata})
                continue
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for Wikidata entity load")
            client.repository.insert_raw_record(
                table_name="raw.wikidata_entities",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=qid,
                response_json=response.payload if isinstance(response.payload, dict) else {},
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )

        logger.mark_finished(status="completed", metrics={"requested_qids": len(qids)})
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
