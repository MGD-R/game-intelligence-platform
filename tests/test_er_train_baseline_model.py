from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from src.entity_resolution.train_baseline_model import main


def test_train_baseline_model_handles_tiny_fixture_dataset(monkeypatch, tmp_path: Path) -> None:
    training = pl.DataFrame(
        [
            {
                "pair_id": "p1",
                "label": 1,
                "name_similarity": 1.0,
                "alias_similarity": 1.0,
                "release_year_diff": 0,
                "external_id_exact_match": True,
                "developer_overlap": 1.0,
                "publisher_overlap": 1.0,
                "platform_jaccard": 1.0,
                "genre_jaccard": 1.0,
                "tag_jaccard": 1.0,
                "description_available_flag": True,
                "description_language_match": True,
                "source_count_signal": 3,
            },
            {
                "pair_id": "p2",
                "label": 1,
                "name_similarity": 0.95,
                "alias_similarity": 0.9,
                "release_year_diff": 0,
                "external_id_exact_match": False,
                "developer_overlap": 0.8,
                "publisher_overlap": 0.8,
                "platform_jaccard": 0.9,
                "genre_jaccard": 0.8,
                "tag_jaccard": 0.7,
                "description_available_flag": True,
                "description_language_match": True,
                "source_count_signal": 3,
            },
            {
                "pair_id": "p3",
                "label": 0,
                "name_similarity": 0.2,
                "alias_similarity": 0.1,
                "release_year_diff": 8,
                "external_id_exact_match": False,
                "developer_overlap": 0.0,
                "publisher_overlap": 0.0,
                "platform_jaccard": 0.0,
                "genre_jaccard": 0.0,
                "tag_jaccard": 0.0,
                "description_available_flag": False,
                "description_language_match": False,
                "source_count_signal": 1,
            },
            {
                "pair_id": "p4",
                "label": 0,
                "name_similarity": 0.3,
                "alias_similarity": 0.2,
                "release_year_diff": 10,
                "external_id_exact_match": False,
                "developer_overlap": 0.0,
                "publisher_overlap": 0.0,
                "platform_jaccard": 0.1,
                "genre_jaccard": 0.1,
                "tag_jaccard": 0.0,
                "description_available_flag": False,
                "description_language_match": False,
                "source_count_signal": 1,
            },
        ]
    )
    reports_dir = tmp_path / "reports"
    models_dir = tmp_path / "models"
    predictions_dir = tmp_path / "predictions"
    reports_dir.mkdir()
    models_dir.mkdir()
    predictions_dir.mkdir()

    monkeypatch.setattr(
        "src.entity_resolution.train_baseline_model.ensure_er_inputs",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "src.entity_resolution.train_baseline_model.build_training_frame",
        lambda *args, **kwargs: training,
    )
    monkeypatch.setattr(
        "src.entity_resolution.train_baseline_model.load_candidate_pairs_frame",
        lambda *args, **kwargs: pl.DataFrame(),
    )
    monkeypatch.setattr(
        "src.entity_resolution.train_baseline_model.load_feature_base_frame",
        lambda *args, **kwargs: pl.DataFrame(),
    )
    monkeypatch.setattr(
        "src.entity_resolution.train_baseline_model.load_source_games_frame",
        lambda *args, **kwargs: pl.DataFrame(),
    )
    monkeypatch.setattr(
        "src.entity_resolution.train_baseline_model.load_reviewed_manual_labels_frame",
        lambda *args, **kwargs: pl.DataFrame(),
    )
    monkeypatch.setattr(
        "src.entity_resolution.train_baseline_model.ensure_output_directories",
        lambda: type(
            "P",
            (),
            {
                "reports_dir": reports_dir,
                "models_dir": models_dir,
                "predictions_dir": predictions_dir,
            },
        )(),
    )

    exit_code = main([])

    assert exit_code == 0
    assert (models_dir / "logistic_regression_baseline.joblib").exists()
    metrics = json.loads((reports_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "precision" in metrics
    assert (predictions_dir / "predictions.parquet").exists()
