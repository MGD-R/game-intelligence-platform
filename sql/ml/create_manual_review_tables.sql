CREATE TABLE IF NOT EXISTS ml.entity_resolution_manual_reviews (
    review_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pair_id UUID NOT NULL REFERENCES ml.entity_candidate_pairs (pair_id) ON DELETE CASCADE,
    review_label BOOLEAN,
    review_status TEXT NOT NULL DEFAULT 'pending',
    selection_strategy TEXT NOT NULL DEFAULT 'manual',
    priority_score NUMERIC(10, 6) NOT NULL DEFAULT 0,
    reviewer TEXT,
    review_notes TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_entity_resolution_manual_reviews_pair UNIQUE (pair_id),
    CONSTRAINT ck_entity_resolution_manual_reviews_status CHECK (
        review_status IN ('pending', 'reviewed', 'unsure', 'skipped')
    ),
    CONSTRAINT ck_entity_resolution_manual_reviews_reviewed_at CHECK (
        (review_status = 'reviewed' AND reviewed_at IS NOT NULL AND review_label IS NOT NULL)
        OR (review_status <> 'reviewed')
    )
);

CREATE INDEX IF NOT EXISTS ix_entity_resolution_manual_reviews_status
    ON ml.entity_resolution_manual_reviews (review_status, selection_strategy, priority_score DESC);

ALTER TABLE ml.entity_resolution_manual_reviews
    DROP CONSTRAINT IF EXISTS ck_entity_resolution_manual_reviews_reviewed_at;

ALTER TABLE ml.entity_resolution_manual_reviews
    ADD CONSTRAINT ck_entity_resolution_manual_reviews_reviewed_at CHECK (
        (review_status = 'reviewed' AND reviewed_at IS NOT NULL AND review_label IS NOT NULL)
        OR (review_status <> 'reviewed')
    );

CREATE OR REPLACE VIEW ml.v_entity_resolution_review_candidates AS
WITH latest_predictions AS (
    SELECT DISTINCT ON (pair_id)
        pair_id,
        model_name,
        model_version,
        same_game_probability,
        decision,
        predicted_at
    FROM ml.entity_resolution_predictions
    ORDER BY pair_id, predicted_at DESC
),
rawg_urls AS (
    SELECT DISTINCT ON (source, source_game_id)
        source,
        source_game_id,
        url AS rawg_url
    FROM stg.source_game_urls
    WHERE source = 'rawg'
      AND url_type IN ('rawg', 'website', 'background_image')
    ORDER BY source, source_game_id, CASE WHEN url_type = 'rawg' THEN 0 ELSE 1 END
),
igdb_urls AS (
    SELECT DISTINCT ON (source, source_game_id)
        source,
        source_game_id,
        url AS igdb_external_url
    FROM stg.source_game_urls
    WHERE source = 'igdb'
      AND url_type IN ('igdb', 'website')
    ORDER BY source, source_game_id, CASE WHEN url_type = 'igdb' THEN 0 ELSE 1 END
)
SELECT
    cp.pair_id,
    cp.source_a,
    cp.source_id_a,
    game_a.name AS name_a,
    game_a.release_year AS release_year_a,
    game_a.slug AS slug_a,
    CASE
        WHEN cp.source_a = 'rawg' AND game_a.slug IS NOT NULL
            THEN 'https://rawg.io/games/' || game_a.slug
        ELSE rawg_urls.rawg_url
    END AS rawg_url,
    cp.source_b,
    cp.source_id_b,
    game_b.name AS name_b,
    game_b.release_year AS release_year_b,
    game_b.slug AS slug_b,
    CASE
        WHEN cp.source_b = 'igdb' AND game_b.slug IS NOT NULL
            THEN 'https://www.igdb.com/games/' || game_b.slug
        ELSE igdb_urls.igdb_external_url
    END AS igdb_url,
    cp.candidate_source,
    cp.label_source,
    cp.label_value,
    cp.confidence AS candidate_confidence,
    isc.search_rank AS igdb_search_rank,
    isc.query_text AS igdb_query_text,
    isc.query_strategy AS igdb_query_strategy,
    isc.confidence AS igdb_search_confidence,
    f.name_similarity,
    f.alias_similarity,
    f.release_year_diff,
    f.external_id_exact_match,
    f.developer_overlap,
    f.publisher_overlap,
    f.platform_jaccard,
    f.genre_jaccard,
    f.tag_jaccard,
    f.description_available_flag,
    f.description_language_match,
    f.source_count_signal,
    p.model_name,
    p.model_version,
    p.same_game_probability,
    p.decision AS model_decision,
    r.review_label,
    r.review_status,
    r.selection_strategy,
    r.priority_score,
    r.reviewer,
    r.review_notes,
    r.reviewed_at
FROM ml.entity_candidate_pairs cp
JOIN ml.entity_resolution_features f
    ON f.pair_id = cp.pair_id
LEFT JOIN latest_predictions p
    ON p.pair_id = cp.pair_id
LEFT JOIN stg.source_games game_a
    ON game_a.source = cp.source_a
   AND game_a.source_game_id = cp.source_id_a
LEFT JOIN stg.source_games game_b
    ON game_b.source = cp.source_b
   AND game_b.source_game_id = cp.source_id_b
LEFT JOIN ml.igdb_search_candidates isc
    ON isc.source_name = cp.source_a
   AND isc.source_game_id = cp.source_id_a
   AND isc.igdb_id = cp.source_id_b
LEFT JOIN rawg_urls
    ON rawg_urls.source = cp.source_a
   AND rawg_urls.source_game_id = cp.source_id_a
LEFT JOIN igdb_urls
    ON igdb_urls.source = cp.source_b
   AND igdb_urls.source_game_id = cp.source_id_b
LEFT JOIN ml.entity_resolution_manual_reviews r
    ON r.pair_id = cp.pair_id;

CREATE OR REPLACE VIEW ml.v_igdb_manual_review_queue AS
SELECT *
FROM ml.v_entity_resolution_review_candidates
WHERE candidate_source = 'igdb_search'
ORDER BY
    CASE review_status
        WHEN 'pending' THEN 0
        WHEN 'unsure' THEN 1
        WHEN 'skipped' THEN 2
        ELSE 3
    END,
    priority_score DESC,
    name_similarity ASC NULLS LAST,
    igdb_search_rank DESC NULLS LAST,
    pair_id;
