from src.ingestion.igdb_queries import (
    build_games_by_ids_query,
    build_multiquery_reference,
    build_reference_query,
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
