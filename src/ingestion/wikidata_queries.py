"""Named SPARQL query builders for Wikidata ingestion."""

from __future__ import annotations

QUERY_NAMES = (
    "external_ids_sitelinks",
    "labels_aliases",
)

SPARQL_PREFIXES = """
PREFIX bd: <http://www.bigdata.com/rdf#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
""".strip()


def _sparql_string_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def external_ids_sitelinks_query(limit: int) -> str:
    return f"""
{SPARQL_PREFIXES}

SELECT DISTINCT ?game ?qid ?label ?rawg ?steam ?igdb ?articleRu ?articleEn ?releaseDate WHERE {{
  OPTIONAL {{ ?game wdt:P9968 ?rawg. }}
  OPTIONAL {{ ?game wdt:P1733 ?steam. }}
  OPTIONAL {{ ?game wdt:P9043 ?igdb. }}
  FILTER(BOUND(?rawg) || BOUND(?steam) || BOUND(?igdb))

  BIND(STRAFTER(STR(?game), STR(wd:)) AS ?qid)

  OPTIONAL {{ ?game wdt:P577 ?releaseDate. }}
  OPTIONAL {{
    ?articleRu schema:about ?game ;
               schema:isPartOf <https://ru.wikipedia.org/> .
  }}
  OPTIONAL {{
    ?articleEn schema:about ?game ;
               schema:isPartOf <https://en.wikipedia.org/> .
  }}

  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "ru,en".
    ?game rdfs:label ?label.
  }}
}}
LIMIT {max(1, limit)}
""".strip()


def labels_aliases_query(limit: int) -> str:
    return f"""
{SPARQL_PREFIXES}

SELECT DISTINCT ?game ?qid ?labelRu ?labelEn ?aliasRu ?aliasEn ?releaseDate WHERE {{
  OPTIONAL {{ ?game wdt:P9968 ?rawg. }}
  OPTIONAL {{ ?game wdt:P1733 ?steam. }}
  OPTIONAL {{ ?game wdt:P9043 ?igdb. }}
  FILTER(BOUND(?rawg) || BOUND(?steam) || BOUND(?igdb))

  BIND(STRAFTER(STR(?game), STR(wd:)) AS ?qid)

  OPTIONAL {{ ?game wdt:P577 ?releaseDate. }}
  OPTIONAL {{ ?game rdfs:label ?labelRu FILTER(LANG(?labelRu) = "ru") }}
  OPTIONAL {{ ?game rdfs:label ?labelEn FILTER(LANG(?labelEn) = "en") }}
  OPTIONAL {{ ?game skos:altLabel ?aliasRu FILTER(LANG(?aliasRu) = "ru") }}
  OPTIONAL {{ ?game skos:altLabel ?aliasEn FILTER(LANG(?aliasEn) = "en") }}
}}
LIMIT {max(1, limit)}
""".strip()


def rawg_ids_query(rawg_ids: list[str]) -> str:
    normalized_ids = [value.strip() for value in rawg_ids if value.strip()]
    if not normalized_ids:
        raise ValueError("rawg_ids_query requires at least one RAWG ID")

    values_clause = " ".join(_sparql_string_literal(value) for value in normalized_ids)
    return f"""
{SPARQL_PREFIXES}

SELECT DISTINCT
  ?game ?qid ?rawg ?steam ?igdb ?articleRu ?articleEn ?releaseDate ?labelRu ?labelEn
WHERE {{
  VALUES ?rawg {{ {values_clause} }}
  ?game wdt:P9968 ?rawg .

  BIND(STRAFTER(STR(?game), STR(wd:)) AS ?qid)

  OPTIONAL {{ ?game wdt:P1733 ?steam. }}
  OPTIONAL {{ ?game wdt:P9043 ?igdb. }}
  OPTIONAL {{ ?game wdt:P577 ?releaseDate. }}
  OPTIONAL {{ ?game rdfs:label ?labelRu FILTER(LANG(?labelRu) = "ru") }}
  OPTIONAL {{ ?game rdfs:label ?labelEn FILTER(LANG(?labelEn) = "en") }}
  OPTIONAL {{
    ?articleRu schema:about ?game ;
               schema:isPartOf <https://ru.wikipedia.org/> .
  }}
  OPTIONAL {{
    ?articleEn schema:about ?game ;
               schema:isPartOf <https://en.wikipedia.org/> .
  }}
}}
""".strip()


QUERY_BUILDERS = {
    "external_ids_sitelinks": external_ids_sitelinks_query,
    "labels_aliases": labels_aliases_query,
}


def build_query(name: str, *, limit: int) -> str:
    try:
        builder = QUERY_BUILDERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown Wikidata query name: {name}") from exc
    return builder(limit)
