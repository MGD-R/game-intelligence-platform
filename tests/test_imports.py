import importlib

MODULES = [
    "src.api.main",
    "src.entity_resolution.blocking",
    "src.entity_resolution.features",
    "src.entity_resolution.run_pipeline",
    "src.ingestion.check_sources",
    "src.ingestion.rawg_client",
    "src.ingestion.rate_limiter",
    "src.ingestion.request_cache",
    "src.ingestion.steam_client",
    "src.ingestion.wikidata_client",
    "src.ingestion.wikipedia_client",
    "src.preprocessing.build_staging",
    "src.rag.build_index",
    "src.recommendations.build_recommendations",
    "src.utils.config",
    "src.utils.logging",
]


def test_modules_import_without_side_effects() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)
