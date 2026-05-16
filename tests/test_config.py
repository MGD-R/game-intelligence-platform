from src.utils.config import enabled_sources, load_all_configs


def test_all_configs_load() -> None:
    configs = load_all_configs()

    assert set(configs) == {
        "app",
        "data_stage",
        "database",
        "entity_resolution",
        "logging",
        "model",
        "sources",
    }


def test_enabled_sources_match_mvp_scope() -> None:
    sources = enabled_sources()

    assert sources["enabled"] == ["rawg", "wikidata", "steam", "wikipedia"]
