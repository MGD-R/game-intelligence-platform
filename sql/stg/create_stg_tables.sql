CREATE TABLE IF NOT EXISTS stg.source_games (
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    name TEXT NOT NULL,
    name_normalized TEXT,
    release_date DATE,
    release_year INTEGER,
    slug TEXT,
    game_type TEXT,
    is_dlc BOOLEAN NOT NULL DEFAULT FALSE,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    is_remake BOOLEAN NOT NULL DEFAULT FALSE,
    is_remaster BOOLEAN NOT NULL DEFAULT FALSE,
    is_bundle BOOLEAN NOT NULL DEFAULT FALSE,
    raw_loaded_at TIMESTAMPTZ,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_priority INTEGER,
    quality_flags_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    PRIMARY KEY (source, source_game_id)
);

CREATE INDEX IF NOT EXISTS ix_source_games_name_normalized
    ON stg.source_games (source, name_normalized);

CREATE INDEX IF NOT EXISTS ix_source_games_release_year
    ON stg.source_games (source, release_year);

CREATE TABLE IF NOT EXISTS stg.source_game_aliases (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    language TEXT,
    alias_type TEXT,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_aliases_value
    ON stg.source_game_aliases (source, source_game_id, alias, COALESCE(language, ''), COALESCE(alias_type, ''));

CREATE INDEX IF NOT EXISTS ix_source_game_aliases_source_game
    ON stg.source_game_aliases (source, source_game_id);

CREATE TABLE IF NOT EXISTS stg.source_game_external_ids (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    external_source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    confidence NUMERIC(5, 4),
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_external_ids_value
    ON stg.source_game_external_ids (source, source_game_id, external_source, external_id);

CREATE INDEX IF NOT EXISTS ix_source_game_external_ids_lookup
    ON stg.source_game_external_ids (source, external_source, external_id);

CREATE TABLE IF NOT EXISTS stg.source_game_genres (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    genre_name TEXT NOT NULL,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_genres_value
    ON stg.source_game_genres (source, source_game_id, genre_name);

CREATE TABLE IF NOT EXISTS stg.source_game_tags (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    tag_name TEXT NOT NULL,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_tags_value
    ON stg.source_game_tags (source, source_game_id, tag_name);

CREATE TABLE IF NOT EXISTS stg.source_game_themes (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    theme_name TEXT NOT NULL,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_themes_value
    ON stg.source_game_themes (source, source_game_id, theme_name);

CREATE TABLE IF NOT EXISTS stg.source_game_platforms (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    platform_name TEXT NOT NULL,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_platforms_value
    ON stg.source_game_platforms (source, source_game_id, platform_name);

CREATE TABLE IF NOT EXISTS stg.source_game_companies (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    company_role TEXT NOT NULL,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_companies_value
    ON stg.source_game_companies (source, source_game_id, company_name, company_role);

CREATE TABLE IF NOT EXISTS stg.source_game_descriptions (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    description_type TEXT NOT NULL,
    language TEXT,
    description_text TEXT NOT NULL,
    source_url TEXT,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stg.source_game_ratings (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    rating_type TEXT NOT NULL,
    rating_value NUMERIC(12, 4),
    rating_scale TEXT,
    rating_count INTEGER,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_ratings_value
    ON stg.source_game_ratings (source, source_game_id, rating_type);

CREATE TABLE IF NOT EXISTS stg.source_game_popularity (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC(18, 4),
    metric_unit TEXT,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_popularity_value
    ON stg.source_game_popularity (source, source_game_id, metric_name);

CREATE TABLE IF NOT EXISTS stg.source_game_urls (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    url_type TEXT NOT NULL,
    url TEXT NOT NULL,
    source_specific_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    stg_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_game_urls_value
    ON stg.source_game_urls (source, source_game_id, url_type, url);
