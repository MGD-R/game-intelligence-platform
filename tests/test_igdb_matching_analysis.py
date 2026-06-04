from __future__ import annotations

from src.entity_resolution.build_igdb_matching_analysis import (
    confidence_bucket,
    high_risk_reviewed_negatives,
    likely_positive_candidates,
    precision_row,
    rank_bucket,
    reviewed_precision_by_bucket,
    safe_ratio,
)


def test_safe_ratio_handles_empty_denominator() -> None:
    assert safe_ratio(1, 2) == 0.5
    assert safe_ratio(1, 0) is None


def test_rank_and_confidence_buckets_are_stable() -> None:
    assert rank_bucket(None) == "unknown"
    assert rank_bucket(1) == "1"
    assert rank_bucket(3) == "2-3"
    assert rank_bucket(5) == "4-5"
    assert rank_bucket(9) == "6+"

    assert confidence_bucket(None) == "unknown"
    assert confidence_bucket(0.96) == "0.95-1.00"
    assert confidence_bucket(0.90) == "0.85-0.95"
    assert confidence_bucket(0.80) == "0.70-0.85"
    assert confidence_bucket(0.20) == "<0.70"


def test_precision_row_calculates_reviewed_precision() -> None:
    assert precision_row(
        bucket_name="rank",
        bucket_value="1",
        reviewed_positive_count=3,
        reviewed_negative_count=1,
    ) == {
        "bucket_name": "rank",
        "bucket_value": "1",
        "reviewed_count": 4,
        "reviewed_positive_count": 3,
        "reviewed_negative_count": 1,
        "reviewed_precision": 0.75,
    }


def test_reviewed_precision_by_bucket_ignores_pending_rows() -> None:
    rows = [
        {"review_status": "reviewed", "review_label": True, "rank_bucket": "1"},
        {"review_status": "reviewed", "review_label": False, "rank_bucket": "1"},
        {"review_status": "pending", "review_label": None, "rank_bucket": "1"},
    ]

    result = reviewed_precision_by_bucket(
        rows,
        bucket_name="rank_bucket",
        bucket_key="rank_bucket",
    )

    assert result == [
        {
            "bucket_name": "rank_bucket",
            "bucket_value": "1",
            "reviewed_count": 2,
            "reviewed_positive_count": 1,
            "reviewed_negative_count": 1,
            "reviewed_precision": 0.5,
        }
    ]


def test_high_risk_reviewed_negatives_selects_model_risk_cases() -> None:
    rows = [
        {
            "pair_id": "risk",
            "review_status": "reviewed",
            "review_label": False,
            "same_game_probability": 0.91,
            "model_decision": "manual_review",
        },
        {
            "pair_id": "ignored",
            "review_status": "reviewed",
            "review_label": False,
            "same_game_probability": 0.20,
            "model_decision": "no_merge",
        },
    ]

    result = high_risk_reviewed_negatives(rows)

    assert [row["pair_id"] for row in result] == ["risk"]
    assert result[0]["case_type"] == "reviewed_negative_high_model_score"


def test_likely_positive_candidates_requires_rank_confidence_name_and_year() -> None:
    rows = [
        {
            "pair_id": "likely",
            "review_status": "pending",
            "name_similarity": 0.95,
            "igdb_search_rank": 1,
            "igdb_search_confidence": 0.90,
            "release_year_diff": 1,
        },
        {
            "pair_id": "wrong-rank",
            "review_status": "pending",
            "name_similarity": 0.95,
            "igdb_search_rank": 2,
            "igdb_search_confidence": 0.90,
            "release_year_diff": 1,
        },
    ]

    result = likely_positive_candidates(rows)

    assert [row["pair_id"] for row in result] == ["likely"]
    assert result[0]["case_type"] == "unreviewed_likely_positive"
