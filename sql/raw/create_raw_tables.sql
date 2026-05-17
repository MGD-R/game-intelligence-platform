CREATE TABLE IF NOT EXISTS raw.rawg_game_index (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'rawg',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rawg_game_index_request_record
    ON raw.rawg_game_index (source, endpoint, request_hash, source_record_id);

CREATE INDEX IF NOT EXISTS ix_rawg_game_index_source_record_id
    ON raw.rawg_game_index (source, source_record_id);

CREATE TABLE IF NOT EXISTS raw.rawg_game_details (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'rawg',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rawg_game_details_request
    ON raw.rawg_game_details (source, endpoint, request_hash);

CREATE INDEX IF NOT EXISTS ix_rawg_game_details_source_record_id
    ON raw.rawg_game_details (source, source_record_id);

CREATE TABLE IF NOT EXISTS raw.rawg_reference_data (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'rawg',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rawg_reference_data_request
    ON raw.rawg_reference_data (source, endpoint, request_hash);

CREATE INDEX IF NOT EXISTS ix_rawg_reference_data_source_record_id
    ON raw.rawg_reference_data (source, source_record_id);

CREATE TABLE IF NOT EXISTS raw.wikidata_sparql_results (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'wikidata',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wikidata_sparql_results_request
    ON raw.wikidata_sparql_results (source, endpoint, request_hash);

CREATE INDEX IF NOT EXISTS ix_wikidata_sparql_results_source_record_id
    ON raw.wikidata_sparql_results (source, source_record_id);

CREATE TABLE IF NOT EXISTS raw.wikidata_entities (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'wikidata',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wikidata_entities_request_record
    ON raw.wikidata_entities (source, endpoint, request_hash, source_record_id);

CREATE INDEX IF NOT EXISTS ix_wikidata_entities_source_record_id
    ON raw.wikidata_entities (source, source_record_id);

CREATE TABLE IF NOT EXISTS raw.steam_app_details (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'steam',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_steam_app_details_request_record
    ON raw.steam_app_details (source, endpoint, request_hash, source_record_id);

CREATE INDEX IF NOT EXISTS ix_steam_app_details_source_record_id
    ON raw.steam_app_details (source, source_record_id);

CREATE TABLE IF NOT EXISTS raw.wikipedia_pages (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'wikipedia',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wikipedia_pages_request_record
    ON raw.wikipedia_pages (source, endpoint, request_hash, source_record_id);

CREATE INDEX IF NOT EXISTS ix_wikipedia_pages_source_record_id
    ON raw.wikipedia_pages (source, source_record_id);

CREATE TABLE IF NOT EXISTS raw.igdb_games (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'igdb',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_igdb_games_request_record
    ON raw.igdb_games (source, endpoint, request_hash, source_record_id);

CREATE INDEX IF NOT EXISTS ix_igdb_games_source_record_id
    ON raw.igdb_games (source, source_record_id);

CREATE TABLE IF NOT EXISTS raw.igdb_reference_data (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES meta.api_request_log (request_id),
    source TEXT NOT NULL DEFAULT 'igdb',
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    source_record_id TEXT,
    response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_hash TEXT,
    response_storage_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    http_status INTEGER,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_igdb_reference_data_request
    ON raw.igdb_reference_data (source, endpoint, request_hash);

CREATE INDEX IF NOT EXISTS ix_igdb_reference_data_source_record_id
    ON raw.igdb_reference_data (source, source_record_id);
