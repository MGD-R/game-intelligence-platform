from __future__ import annotations

from pathlib import Path

import polars as pl

from src.entity_resolution.corpus import SourceGameRecord
from src.preprocessing.export_ml_ready_datasets import main


class ExportRepositoryStub:
    def fetch_candidate_pairs(self, *, limit: int | None = None) -> list[dict[str, object]]:
        return [
            {
                "pair_id": "pair-1",
                "source_a": "rawg",
                "source_id_a": "1",
                "source_b": "wikidata",
                "source_id_b": "Q1",
                "candidate_source": "external_id_positive",
                "label_source": "wikidata_rawg_external_id",
                "label_value": "1",
                "confidence": 1.0,
            }
        ]

    def fetch_entity_resolution_features(
        self,
        *,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "pair_id": "pair-1",
                "name_similarity": 1.0,
                "alias_similarity": 1.0,
                "release_year_diff": 0,
                "external_id_exact_match": True,
                "developer_overlap": 1.0,
                "publisher_overlap": 1.0,
                "platform_jaccard": 1.0,
                "genre_jaccard": 1.0,
                "tag_jaccard": None,
                "description_available_flag": True,
                "description_language_match": True,
                "source_count_signal": 3,
                "features_json": {},
            }
        ]

    def fetch_staging_rows(
        self,
        table_name: str,
        *,
        source: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        rows = {
            "stg.source_games": [
                {
                    "source": "rawg",
                    "source_game_id": "1",
                    "name": "Game One",
                    "name_normalized": "game one",
                }
            ],
            "stg.source_game_aliases": [
                {"source": "rawg", "source_game_id": "1", "alias": "Game One", "language": "en"}
            ],
            "stg.source_game_external_ids": [
                {
                    "source": "wikidata",
                    "source_game_id": "Q1",
                    "external_source": "rawg",
                    "external_id": "1",
                }
            ],
            "stg.source_game_genres": [
                {"source": "rawg", "source_game_id": "1", "genre_name": "Action"}
            ],
            "stg.source_game_tags": [],
            "stg.source_game_platforms": [
                {"source": "rawg", "source_game_id": "1", "platform_name": "PC"}
            ],
            "stg.source_game_companies": [
                {
                    "source": "rawg",
                    "source_game_id": "1",
                    "company_name": "Studio",
                    "company_role": "developer",
                }
            ],
            "stg.source_game_descriptions": [
                {
                    "source": "rawg",
                    "source_game_id": "1",
                    "description_type": "summary",
                    "language": "en",
                    "description_text": "Description",
                }
            ],
            "stg.source_game_ratings": [
                {
                    "source": "rawg",
                    "source_game_id": "1",
                    "rating_type": "critic",
                    "rating_value": 4.5,
                }
            ],
            "stg.source_game_popularity": [],
            "dm.canonical_games": [
                {
                    "canonical_game_id": "canonical-1",
                    "canonical_name": "Game One",
                    "release_year": 2013,
                }
            ],
            "dm.canonical_game_sources": [
                {
                    "canonical_game_id": "canonical-1",
                    "source": "rawg",
                    "source_game_id": "1",
                    "linkage_confidence": 1.0,
                },
                {
                    "canonical_game_id": "canonical-1",
                    "source": "wikidata",
                    "source_game_id": "Q1",
                    "linkage_confidence": 1.0,
                },
            ],
            "dm.canonical_game_aliases": [
                {
                    "canonical_game_id": "canonical-1",
                    "alias": "Game One",
                    "language": "en",
                }
            ],
            "dm.canonical_game_external_ids": [
                {
                    "canonical_game_id": "canonical-1",
                    "external_source": "rawg",
                    "external_id": "1",
                }
            ],
        }
        return rows[table_name]


class SparseExportRepositoryStub(ExportRepositoryStub):
    def fetch_staging_rows(
        self,
        table_name: str,
        *,
        source: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        if table_name in {
            "stg.source_game_aliases",
            "stg.source_game_companies",
            "stg.source_game_descriptions",
        }:
            return []
        return super().fetch_staging_rows(table_name, source=source, limit=limit)


def test_exporter_writes_expected_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "src.preprocessing.export_ml_ready_datasets.IngestionRepository",
        lambda: ExportRepositoryStub(),
    )
    monkeypatch.setattr(
        "src.preprocessing.export_ml_ready_datasets.validate_ml_ready_state",
        lambda *args, **kwargs: type("V", (), {"ok": True, "warnings": []})(),
    )
    monkeypatch.setattr(
        "src.preprocessing.export_ml_ready_datasets.load_source_records",
        lambda repository: {
            ("rawg", "1"): SourceGameRecord(
                source="rawg",
                source_game_id="1",
                name="Game One",
                name_normalized="game one",
                release_year=2013,
            ),
            ("wikidata", "Q1"): SourceGameRecord(
                source="wikidata",
                source_game_id="Q1",
                name="Game One",
                name_normalized="game one",
                release_year=2013,
            ),
        },
    )

    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "source_games.parquet").exists()
    assert (tmp_path / "manual_review_seed.parquet").exists()
    assert (tmp_path / "canonical_games.parquet").exists()
    assert (tmp_path / "canonical_game_sources.parquet").exists()
    assert pl.read_parquet(tmp_path / "entity_candidate_pairs.parquet").height == 1
    assert pl.read_parquet(tmp_path / "canonical_games.parquet").height == 1


def test_exporter_writes_empty_optional_parquet_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "src.preprocessing.export_ml_ready_datasets.IngestionRepository",
        lambda: SparseExportRepositoryStub(),
    )
    monkeypatch.setattr(
        "src.preprocessing.export_ml_ready_datasets.validate_ml_ready_state",
        lambda *args, **kwargs: type("V", (), {"ok": True, "warnings": []})(),
    )
    monkeypatch.setattr(
        "src.preprocessing.export_ml_ready_datasets.load_source_records",
        lambda repository: {
            ("rawg", "1"): SourceGameRecord(
                source="rawg",
                source_game_id="1",
                name="Game One",
                name_normalized="game one",
                release_year=2013,
            ),
            ("wikidata", "Q1"): SourceGameRecord(
                source="wikidata",
                source_game_id="Q1",
                name="Game One",
                name_normalized="game one",
                release_year=2013,
            ),
        },
    )

    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert pl.read_parquet(tmp_path / "source_aliases.parquet").height == 0
    assert pl.read_parquet(tmp_path / "source_companies.parquet").height == 0
    assert pl.read_parquet(tmp_path / "source_descriptions.parquet").height == 0
