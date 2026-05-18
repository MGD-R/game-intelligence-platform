CREATE TABLE IF NOT EXISTS ml.entity_candidate_pairs (
    pair_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_a TEXT NOT NULL,
    source_id_a TEXT NOT NULL,
    source_b TEXT NOT NULL,
    source_id_b TEXT NOT NULL,
    candidate_source TEXT,
    label_source TEXT,
    label_value TEXT,
    confidence NUMERIC(5, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_candidate_pairs_pair
    ON ml.entity_candidate_pairs (source_a, source_id_a, source_b, source_id_b);

CREATE TABLE IF NOT EXISTS ml.entity_resolution_features (
    pair_id UUID PRIMARY KEY REFERENCES ml.entity_candidate_pairs (pair_id) ON DELETE CASCADE,
    name_similarity NUMERIC(8, 6),
    alias_similarity NUMERIC(8, 6),
    release_year_diff INTEGER,
    external_id_exact_match BOOLEAN,
    developer_overlap NUMERIC(8, 6),
    publisher_overlap NUMERIC(8, 6),
    platform_jaccard NUMERIC(8, 6),
    genre_jaccard NUMERIC(8, 6),
    tag_jaccard NUMERIC(8, 6),
    description_available_flag BOOLEAN NOT NULL DEFAULT FALSE,
    description_language_match BOOLEAN,
    source_count_signal INTEGER,
    features_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ml.entity_resolution_predictions (
    prediction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pair_id UUID NOT NULL REFERENCES ml.entity_candidate_pairs (pair_id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    same_game_probability NUMERIC(8, 6) NOT NULL,
    decision TEXT NOT NULL,
    threshold_policy_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    explanation_factors_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (pair_id, model_name, model_version)
);

CREATE TABLE IF NOT EXISTS ml.igdb_search_candidates (
    candidate_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    candidate_source TEXT NOT NULL DEFAULT 'igdb',
    igdb_id TEXT NOT NULL,
    search_rank INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    query_strategy TEXT NOT NULL,
    confidence NUMERIC(5, 4),
    metadata_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_igdb_search_candidates_match
    ON ml.igdb_search_candidates (source_name, source_game_id, candidate_source, igdb_id);
