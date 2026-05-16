from src.ingestion.request_hash import build_request_hash


def test_request_hash_is_stable_across_param_order() -> None:
    first = build_request_hash(
        source="rawg",
        endpoint="https://api.rawg.io/api/games",
        method="GET",
        params={"page_size": 1, "search": "doom"},
    )
    second = build_request_hash(
        source="rawg",
        endpoint="https://api.rawg.io/api/games",
        method="GET",
        params={"search": "doom", "page_size": 1},
    )

    assert first == second


def test_request_hash_ignores_secret_only_changes() -> None:
    first = build_request_hash(
        source="rawg",
        endpoint="https://api.rawg.io/api/games?key=secret-1",
        method="GET",
        params={"page_size": 1, "key": "secret-1"},
    )
    second = build_request_hash(
        source="rawg",
        endpoint="https://api.rawg.io/api/games?key=secret-2",
        method="GET",
        params={"page_size": 1, "key": "secret-2"},
    )

    assert first == second
