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
    features_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
