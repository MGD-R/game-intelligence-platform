from src.ingestion.igdb_queries import (
    build_games_by_ids_query,
    build_multiquery_reference,
    build_reference_query,
    build_search_games_query,
)


def test_igdb_games_query_contains_ids_and_fields() -> None:
    query = build_games_by_ids_query([1020, 2048], ["id", "name"])
    assert "where id = (1020, 2048);" in query
    assert "fields id, name;" in query


def test_igdb_reference_queries_build_multiquery() -> None:
    assert "limit 500;" in build_reference_query("genres")
    multiquery = build_multiquery_reference()
    assert multiquery
    assert multiquery[0][0]


def test_igdb_search_query_supports_year_filter_and_limit() -> None:
    query = build_search_games_query(
        'Grand Theft Auto "V"',
        fields=["id", "name"],
        limit=3,
        release_year=2013,
        year_window=1,
    )
    assert 'search "Grand Theft Auto \\"V\\"";' in query
    assert "fields id, name;" in query
    assert "first_release_date >=" in query
    assert "limit 3;" in query
