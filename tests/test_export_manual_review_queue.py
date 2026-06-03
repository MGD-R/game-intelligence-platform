from __future__ import annotations

from pathlib import Path

from src.entity_resolution.export_manual_review_queue import (
    build_review_query,
    export_manual_review_queue,
)


class _CursorStub:
    description = []

    def __init__(self) -> None:
        self.query = ""
        self.params: tuple[object, ...] = ()
        self.description = []

    def __enter__(self) -> "_CursorStub":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[dict[str, object]]:
        return [
            {
                "review_id": "review-1",
                "pair_id": "pair-1",
                "source_a": "rawg",
                "source_id_a": "1",
                "name_a": "Game One",
                "release_year_a": 2013,
                "rawg_url": "https://rawg.io/games/game-one",
                "source_b": "igdb",
                "source_id_b": "2",
                "name_b": "Game One",
                "release_year_b": 2013,
                "igdb_url": "https://www.igdb.com/games/game-one",
                "candidate_source": "igdb_search",
                "label_source": None,
                "label_value": None,
                "name_similarity": 1.0,
                "alias_similarity": 1.0,
                "release_year_diff": 0,
                "same_game_probability": 0.75,
                "model_decision": "manual_review",
                "selection_strategy": "v2_uncertain_igdb_manual_review",
                "priority_score": 0.9,
                "review_status": "pending",
                "review_label": None,
                "reviewer": None,
                "review_notes": None,
                "invalid_display_name_flag": False,
            }
        ]


class _ConnectionStub:
    def __init__(self) -> None:
        self.cursor_stub = _CursorStub()

    def __enter__(self) -> "_ConnectionStub":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> _CursorStub:
        return self.cursor_stub


class _RepositoryStub:
    def __init__(self) -> None:
        self.connection_stub = _ConnectionStub()

    def connection(self) -> _ConnectionStub:
        return self.connection_stub


def test_build_review_query_filters_status_and_limit() -> None:
    query, params = build_review_query(status="pending", limit=500)

    assert "r.review_status = %s" in query
    assert "LIMIT %s" in query
    assert params == ("pending", 500)


def test_export_manual_review_queue_writes_csv_and_summary(tmp_path: Path) -> None:
    repository = _RepositoryStub()

    result = export_manual_review_queue(
        repository=repository,
        output_dir=tmp_path,
        status="pending",
        limit=500,
    )

    csv_path = tmp_path / "entity_resolution_manual_review_pending.csv"
    summary_path = tmp_path / "entity_resolution_manual_review_pending_summary.json"
    assert result["row_count"] == 1
    assert csv_path.exists()
    assert summary_path.exists()
    assert "review_id,pair_id" in csv_path.read_text(encoding="utf-8")
    assert "v2_uncertain_igdb_manual_review" in summary_path.read_text(encoding="utf-8")
