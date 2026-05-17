"""Restore local data stage from a prepared data pack without API calls."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.entity_resolution.build_candidate_pairs import main as candidate_pairs_main
from src.entity_resolution.build_feature_base import main as feature_base_main
from src.ingestion.repository import IngestionRepository
from src.preprocessing.build_ml_ready_datasets import main as ml_ready_main
from src.preprocessing.build_staging import main as build_staging_main
from src.preprocessing.data_quality import main as data_quality_main
from src.preprocessing.export_data_pack import main as export_data_pack_main
from src.preprocessing.igdb_to_staging import main as igdb_to_staging_main
from src.preprocessing.import_data_pack import main as import_data_pack_main
from src.preprocessing.match_external_ids import main as match_external_ids_main
from src.preprocessing.steam_to_staging import main as steam_to_staging_main
from src.preprocessing.wikipedia_to_staging import main as wikipedia_to_staging_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore the local data stage from files.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", help="Optional output directory for the rebuilt data pack.")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_root = Path(args.input)
    if not input_root.exists():
        raise RuntimeError(f"Data pack does not exist: {input_root}")

    output_root = (
        Path(args.output) if args.output else input_root.parent / f"{input_root.name}_restored"
    )
    if args.dry_run:
        print(
            {
                "input": str(input_root),
                "output": str(output_root),
                "steps": [
                    "import raw data pack",
                    "rebuild staging",
                    "rebuild external ID matches",
                    "rebuild candidate pairs",
                    "rebuild feature base",
                    "rebuild DQ reports",
                    "rebuild ML-ready datasets",
                    "export refreshed data pack manifest",
                ],
            }
        )
        return 0

    import_data_pack_main(["--input", str(input_root)])
    build_staging_main(["--all"])
    repository = IngestionRepository()
    if repository.count_rows("raw.steam_app_details") > 0:
        steam_to_staging_main([])
    if repository.count_rows("raw.wikipedia_pages") > 0:
        wikipedia_to_staging_main([])
    if repository.count_rows("raw.igdb_games") > 0:
        igdb_to_staging_main([])
    match_external_ids_main([])
    candidate_pairs_main([])
    feature_base_main([])
    data_quality_main([])
    ml_ready_main(["--rebuild"])
    export_data_pack_main(
        [
            "--output",
            str(output_root),
            "--include-cache",
            "--include-processed",
            "--include-reports",
        ]
    )
    print({"input": str(input_root), "output": str(output_root), "status": "restored"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
