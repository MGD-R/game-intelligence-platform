from __future__ import annotations

import sys

import numpy as np

from src.research.neural_embeddings import cosine, neural_pair_scores, tfidf_pair_scores


def test_cosine_similarity_handles_zero_vectors() -> None:
    assert cosine(np.array([0.0, 0.0]), np.array([1.0, 0.0])) == 0.0


def test_tfidf_pair_scores_are_deterministic() -> None:
    pairs = [("Doom", "DOOM"), ("Doom", "Civilization")]

    scores = tfidf_pair_scores(pairs)

    assert len(scores) == 2
    assert scores[0] >= scores[1]


def test_neural_pair_scores_falls_back_when_sentence_transformers_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    mode, scores, warning = neural_pair_scores([("Doom", "DOOM")])

    assert mode == "tfidf_fallback"
    assert len(scores) == 1
    assert warning
