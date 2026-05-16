import importlib

MODULES = [
    "src.api.main",
    "src.database.check_schema",
    "src.ingestion.base_client",
    "src.entity_resolution.blocking",
    "src.entity_resolution.features",
    "src.entity_resolution.run_pipeline",
    "src.ingestion.cli",
    "src.ingestion.check_sources",
    "src.ingestion.http",
    "src.ingestion.pipeline_log",
    "src.ingestion.quota",
    "src.ingestion.rawg_client",
    "src.ingestion.jobs.load_rawg_details",
    "src.ingestion.jobs.load_rawg_index",
    "src.ingestion.jobs.load_rawg_reference",
    "src.ingestion.rate_limiter",
    "src.ingestion.redaction",
    "src.ingestion.repository",
    "src.ingestion.request_cache",
    "src.ingestion.request_hash",
    "src.ingestion.steam_client",
    "src.ingestion.wikidata_client",
    "src.ingestion.wikipedia_client",
    "src.preprocessing.build_staging",
    "src.preprocessing.rawg_to_staging",
    "src.rag.build_index",
    "src.recommendations.build_recommendations",
    "src.utils.config",
    "src.utils.logging",
]


def test_modules_import_without_side_effects() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)
