from src.ingestion.igdb_client import IGDBClient


def test_igdb_client_dry_run_redacts_auth_header() -> None:
    client = IGDBClient(repository=None)
    response = client.get_games_by_ids([1020], dry_run=True)
    assert response.dry_run is True
    assert response.request_metadata["headers"]["Authorization"] == "***REDACTED***"


def test_igdb_client_search_dry_run_contains_query() -> None:
    client = IGDBClient(repository=None)
    response = client.search_games("Portal 2", dry_run=True, limit=3, release_year=2011)
    assert response.dry_run is True
    assert response.request_metadata["body"]["raw_body"]
    assert 'search "Portal 2";' in str(response.request_metadata["body"]["raw_body"])
