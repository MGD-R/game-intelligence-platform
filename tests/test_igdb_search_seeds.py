from src.ingestion.jobs.select_igdb_search_seeds import (
    build_search_queries,
    extract_attempted_source_ids,
    select_igdb_search_seeds_from_rows,
)


def test_build_search_queries_deduplicates_slug_and_aliases() -> None:
    queries = build_search_queries(
        name="Portal 2",
        slug="portal-2",
        aliases=["Portal 2", "Portal Two"],
        alias_limit=3,
    )
    assert queries[0]["query_strategy"] == "source_name"
    assert any(query["query_strategy"] == "wikidata_alias" for query in queries)
    assert len(queries) == 2


def test_select_igdb_search_seeds_can_filter_unmatched_only() -> None:
    rawg_rows = [
        {
            "source": "rawg",
            "source_game_id": "1",
            "name": "Portal 2",
            "slug": "portal-2",
            "release_year": 2011,
            "source_priority": 100,
        },
        {
            "source": "rawg",
            "source_game_id": "2",
            "name": "Binary Domain",
            "slug": "binary-domain",
            "release_year": 2012,
            "source_priority": 100,
        },
    ]
    external_rows = [
        {
            "source": "wikidata",
            "source_game_id": "Q1",
            "external_source": "rawg",
            "external_id": "portal-2",
        }
    ]
    alias_rows = [{"source": "wikidata", "source_game_id": "Q1", "alias": "Portal Two"}]
    seeds = select_igdb_search_seeds_from_rows(
        rawg_rows=rawg_rows,
        external_rows=external_rows,
        alias_rows=alias_rows,
        limit=10,
        unmatched_only=True,
    )
    assert len(seeds) == 1
    assert seeds[0]["source_game_id"] == "2"


def test_extract_attempted_source_ids_reads_anchor_payload() -> None:
    attempted = extract_attempted_source_ids(
        [
            {
                "response_json": {
                    "anchor": {"source": "rawg", "source_game_id": "42"},
                    "query": {
                        "text": "Example",
                        "strategy": "source_name",
                        "rank": None,
                    },
                    "candidate": None,
                }
            }
        ]
    )
    assert attempted == {"42"}
