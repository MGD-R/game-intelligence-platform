"""Entity resolution feature helpers."""

from __future__ import annotations


def feature_catalog() -> list[str]:
    return [
        "name_similarity",
        "alias_similarity",
        "release_year_diff",
        "external_id_exact_match",
        "developer_overlap",
        "publisher_overlap",
        "platform_jaccard",
        "genre_jaccard",
        "tag_jaccard",
        "description_available_flag",
        "description_language_match",
        "source_count_signal",
    ]
