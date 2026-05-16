from __future__ import annotations

from src.preprocessing.validate_ml_ready_data import validate_ml_ready_state


class ValidationRepositoryStub:
    def __init__(self, *, rawg_count: int = 0, wikidata_count: int = 0) -> None:
        self.row_counts = {
            ("stg.source_games", "rawg"): rawg_count,
            ("stg.source_games", "wikidata"): wikidata_count,
            ("stg.source_games", "steam"): 0,
            ("stg.source_games", "wikipedia"): 0,
            ("stg.source_games", "igdb"): 0,
            ("stg.source_game_external_ids", "rawg"): rawg_count,
            ("stg.source_game_external_ids", "wikidata"): wikidata_count,
            ("ml.entity_candidate_pairs", None): 1,
            ("ml.entity_resolution_features", None): 1,
        }

    def fetch_existing_tables(self, *, schemas: list[str]) -> set[tuple[str, str]]:
        return {
            ("raw", "rawg_game_index"),
            ("stg", "source_games"),
            ("stg", "source_game_aliases"),
            ("stg", "source_game_external_ids"),
            ("stg", "source_game_genres"),
            ("stg", "source_game_tags"),
            ("stg", "source_game_platforms"),
            ("stg", "source_game_companies"),
            ("stg", "source_game_descriptions"),
            ("stg", "source_game_ratings"),
            ("stg", "source_game_popularity"),
            ("stg", "source_game_urls"),
            ("ml", "entity_candidate_pairs"),
            ("ml", "entity_resolution_features"),
            ("dm", "canonical_games"),
            ("meta", "pipeline_run_log"),
        }

    def count_rows(self, table_name: str, *, source: str | None = None) -> int:
        return self.row_counts.get((table_name, source), self.row_counts.get((table_name, None), 0))

    def fetch_candidate_pairs(self) -> list[dict[str, object]]:
        return [
            {
                "pair_id": "pair-1",
                "source_a": "rawg",
                "source_id_a": "1",
                "source_b": "wikidata",
                "source_id_b": "Q1",
                "label_value": "1",
            }
        ]

    def fetch_staging_rows(
        self,
        table_name: str,
        *,
        source: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        if table_name == "stg.source_games":
            rows = []
            if self.row_counts[("stg.source_games", "rawg")]:
                rows.append(
                    {
                        "source": "rawg",
                        "source_game_id": "1",
                        "name": "Game One",
                        "name_normalized": "game one",
                        "release_year": 2013,
                    }
                )
            if self.row_counts[("stg.source_games", "wikidata")]:
                rows.append(
                    {
                        "source": "wikidata",
                        "source_game_id": "Q1",
                        "name": "Game One",
                        "name_normalized": "game one",
                        "release_year": 2013,
                    }
                )
            return rows
        if table_name == "stg.source_game_external_ids":
            return [
                {
                    "source": "wikidata",
                    "source_game_id": "Q1",
                    "external_source": "rawg",
                    "external_id": "1",
                }
            ]
        if table_name == "stg.source_game_descriptions":
            return [
                {
                    "source": "rawg",
                    "source_game_id": "1",
                    "description_text": "Description",
                    "language": "en",
                }
            ]
        return []


def test_validator_fails_when_required_sources_missing(tmp_path) -> None:
    validation = validate_ml_ready_state(
        ValidationRepositoryStub(rawg_count=0, wikidata_count=0),
        output_dir=str(tmp_path / "processed"),
        reports_dir=str(tmp_path / "reports"),
        manifests_dir=str(tmp_path / "manifests"),
    )

    assert not validation.ok
    assert any(
        "missing required staging rows for source: rawg" in error
        for error in validation.errors
    )


def test_validator_allows_empty_with_warnings(tmp_path) -> None:
    validation = validate_ml_ready_state(
        ValidationRepositoryStub(rawg_count=0, wikidata_count=0),
        allow_empty=True,
        dry_run=True,
        output_dir=str(tmp_path / "processed"),
        reports_dir=str(tmp_path / "reports"),
        manifests_dir=str(tmp_path / "manifests"),
    )

    assert validation.ok
    assert "optional source not loaded: steam" in validation.warnings
