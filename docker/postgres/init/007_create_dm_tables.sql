CREATE TABLE IF NOT EXISTS dm.canonical_games (
    canonical_game_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_name TEXT NOT NULL,
    release_year INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dm.canonical_game_sources (
    id BIGSERIAL PRIMARY KEY,
    canonical_game_id UUID NOT NULL REFERENCES dm.canonical_games (canonical_game_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_game_id TEXT NOT NULL,
    linkage_confidence NUMERIC(5, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_game_sources_value
    ON dm.canonical_game_sources (canonical_game_id, source, source_game_id);

CREATE TABLE IF NOT EXISTS dm.canonical_game_aliases (
    id BIGSERIAL PRIMARY KEY,
    canonical_game_id UUID NOT NULL REFERENCES dm.canonical_games (canonical_game_id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    language TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dm.canonical_game_external_ids (
    id BIGSERIAL PRIMARY KEY,
    canonical_game_id UUID NOT NULL REFERENCES dm.canonical_games (canonical_game_id) ON DELETE CASCADE,
    external_source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_game_external_ids_value
    ON dm.canonical_game_external_ids (canonical_game_id, external_source, external_id);
