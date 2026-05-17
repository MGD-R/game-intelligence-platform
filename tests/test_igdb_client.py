from src.ingestion.igdb_client import IGDBClient


def test_igdb_client_dry_run_redacts_auth_header() -> None:
    client = IGDBClient(repository=None)
    response = client.get_games_by_ids([1020], dry_run=True)
    assert response.dry_run is True
    assert response.request_metadata["headers"]["Authorization"] == "***REDACTED***"
