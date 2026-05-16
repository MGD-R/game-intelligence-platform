"""Entity resolution feature placeholder."""

from __future__ import annotations


def feature_catalog() -> list[str]:
    return [
        "title_similarity",
        "alias_similarity",
        "year_difference",
        "developer_overlap",
        "platform_overlap",
        "embedding_cosine_similarity",
    ]
