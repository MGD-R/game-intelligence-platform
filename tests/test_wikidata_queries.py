from src.ingestion.wikidata_queries import build_query


def test_external_ids_query_contains_required_properties_and_limit() -> None:
    query = build_query("external_ids_sitelinks", limit=25)

    assert "P9968" in query
    assert "P1733" in query
    assert "P9043" in query
    assert "LIMIT 25" in query


def test_labels_aliases_query_contains_required_alias_fields() -> None:
    query = build_query("labels_aliases", limit=10)

    assert "aliasRu" in query
    assert "aliasEn" in query
    assert 'LANG(?labelRu) = "ru"' in query
    assert "LIMIT 10" in query
