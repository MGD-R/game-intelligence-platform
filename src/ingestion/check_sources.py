"""Safe local and tiny network source checks for the ingestion framework."""

from __future__ import annotations

import os
from typing import Any

from src.ingestion.base_client import BaseAPIClient, CacheMissError
from src.ingestion.cli import build_common_parser
from src.ingestion.repository import IngestionRepository, database_dsn_configured
from src.ingestion.request_cache import ResponseCache
from src.utils.config import load_yaml_config


def required_env_names(settings: dict[str, Any]) -> list[str]:
    return [
        env_name
        for key, env_name in settings.items()
        if key.endswith("_env") and isinstance(env_name, str)
    ]


def build_parser():  # type: ignore[no-untyped-def]
    parser = build_common_parser("Check ingestion source configuration and connectivity.")
    parser.set_defaults(network=False)
    return parser


def load_sources() -> dict[str, dict[str, Any]]:
    return load_yaml_config("sources").get("sources", {})


def build_repository() -> IngestionRepository | None:
    try:
        return IngestionRepository()
    except Exception:
        return None


def run_no_network_checks(source_filter: str | None = None) -> int:
    sources = load_sources()
    cache = ResponseCache()

    print("Config files: ok")
    print(f"Database URL configured: {'yes' if database_dsn_configured() else 'no'}")
    print(f"Cache directory: {cache.cache_root}")

    for source_name, settings in sources.items():
        if source_filter and source_name != source_filter:
            continue
        env_names = required_env_names(settings)
        enabled = bool(settings.get("enabled"))
        configured = all(os.getenv(name) for name in env_names) if env_names else True
        print(
            f"- {source_name}: enabled={enabled}, required_envs={env_names or ['none']}, "
            f"configured={configured}"
        )

    return 0


def build_source_client(
    source_name: str,
    settings: dict[str, Any],
    repository: IngestionRepository | None,
) -> BaseAPIClient:
    default_headers: dict[str, str] = {}
    if source_name in {"wikidata", "wikipedia"}:
        user_agent_env = settings.get("user_agent_env")
        if isinstance(user_agent_env, str) and os.getenv(user_agent_env):
            default_headers["User-Agent"] = os.getenv(user_agent_env, "")

    return BaseAPIClient(
        source=source_name,
        base_url=str(settings.get("base_url", "")),
        timeout_seconds=int(settings.get("timeout_seconds", 10)),
        default_headers=default_headers,
        source_settings=settings,
        repository=repository,
    )


def rawg_check(
    client: BaseAPIClient, settings: dict[str, Any], args  # type: ignore[no-untyped-def]
) -> tuple[bool, str]:
    api_key_env = settings.get("api_key_env")
    if not isinstance(api_key_env, str) or not os.getenv(api_key_env):
        return False, "skipped: RAWG_API_KEY is not configured"
    response = client.request(
        "GET",
        "/games",
        params={"page_size": max(1, args.limit), "key": os.getenv(api_key_env, "")},
        use_cache=not args.force_refresh,
        force_refresh=args.force_refresh,
        dry_run=args.dry_run,
        from_cache_only=args.from_cache_only,
    )
    detail = f"status={response.http_status}, cache={response.from_cache}"
    return (response.http_status or 0) < 400, detail


def wikidata_check(
    client: BaseAPIClient, settings: dict[str, Any], args  # type: ignore[no-untyped-def]
) -> tuple[bool, str]:
    user_agent_env = settings.get("user_agent_env")
    if not isinstance(user_agent_env, str) or not os.getenv(user_agent_env):
        return False, "skipped: WIKIMEDIA_USER_AGENT is not configured"
    response = client.request(
        "GET",
        "https://query.wikidata.org/sparql",
        params={
            "query": "SELECT ?item WHERE { ?item wdt:P31 wd:Q7889 . } LIMIT 1",
            "format": "json",
        },
        use_cache=not args.force_refresh,
        force_refresh=args.force_refresh,
        dry_run=args.dry_run,
        from_cache_only=args.from_cache_only,
    )
    detail = f"status={response.http_status}, cache={response.from_cache}"
    return (response.http_status or 0) < 400, detail


def steam_check(
    client: BaseAPIClient, settings: dict[str, Any], args  # type: ignore[no-untyped-def]
) -> tuple[bool, str]:
    response = client.request(
        "GET",
        "/appdetails",
        params={"appids": "292030"},
        use_cache=not args.force_refresh,
        force_refresh=args.force_refresh,
        dry_run=args.dry_run,
        from_cache_only=args.from_cache_only,
    )
    detail = f"status={response.http_status}, cache={response.from_cache}"
    return (response.http_status or 0) < 400, detail


def wikipedia_check(
    client: BaseAPIClient, settings: dict[str, Any], args  # type: ignore[no-untyped-def]
) -> tuple[bool, str]:
    user_agent_env = settings.get("user_agent_env")
    if not isinstance(user_agent_env, str) or not os.getenv(user_agent_env):
        return False, "skipped: WIKIMEDIA_USER_AGENT is not configured"
    response = client.request(
        "GET",
        "/page/summary/Minecraft",
        use_cache=not args.force_refresh,
        force_refresh=args.force_refresh,
        dry_run=args.dry_run,
        from_cache_only=args.from_cache_only,
    )
    detail = f"status={response.http_status}, cache={response.from_cache}"
    return (response.http_status or 0) < 400, detail


def igdb_check(
    client: BaseAPIClient, settings: dict[str, Any], args  # type: ignore[no-untyped-def]
) -> tuple[bool, str]:
    client_id_env = settings.get("client_id_env")
    client_secret_env = settings.get("client_secret_env")
    if (
        not isinstance(client_id_env, str)
        or not isinstance(client_secret_env, str)
        or not os.getenv(client_id_env)
        or not os.getenv(client_secret_env)
    ):
        return False, "skipped: IGDB credentials are not configured"
    return False, "skipped: IGDB minimal network check will be added with the auth flow stage"


NETWORK_CHECKS = {
    "rawg": rawg_check,
    "wikidata": wikidata_check,
    "steam": steam_check,
    "wikipedia": wikipedia_check,
    "igdb": igdb_check,
}


def run_network_checks(args) -> int:  # type: ignore[no-untyped-def]
    sources = load_sources()
    repository = build_repository()
    overall_ok = True

    for source_name, settings in sources.items():
        if args.source and source_name != args.source:
            continue
        if not settings.get("enabled"):
            continue
        client = build_source_client(source_name, settings, repository)
        check_fn = NETWORK_CHECKS[source_name]
        try:
            ok, detail = check_fn(client, settings, args)
        except CacheMissError as exc:
            ok, detail = False, str(exc)
        except Exception as exc:  # pragma: no cover - network path
            ok, detail = False, f"{exc.__class__.__name__}: {exc}"
        overall_ok = overall_ok and ok
        print(f"- {source_name}: {'ok' if ok else 'warning'} ({detail})")

    return 0 if overall_ok else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.network:
        return run_network_checks(args)
    return run_no_network_checks(args.source)


if __name__ == "__main__":
    raise SystemExit(main())
