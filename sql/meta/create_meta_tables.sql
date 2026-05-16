CREATE TABLE IF NOT EXISTS meta.api_request_log (
    request_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_method TEXT NOT NULL DEFAULT 'GET',
    request_url TEXT,
    request_params_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    request_body TEXT,
    request_hash TEXT,
    http_status INTEGER,
    response_hash TEXT,
    response_storage_path TEXT,
    from_cache BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    cost_units NUMERIC(12, 4),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_api_request_log_source_request_hash
    ON meta.api_request_log (source, request_hash)
    WHERE request_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS meta.api_quota_usage (
    source TEXT NOT NULL,
    quota_period TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    quota_limit INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, quota_period)
);

CREATE TABLE IF NOT EXISTS meta.pipeline_run_log (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_name TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    parameters_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    metrics_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meta.ingestion_checkpoint (
    source TEXT NOT NULL,
    job_name TEXT NOT NULL,
    checkpoint_key TEXT NOT NULL,
    checkpoint_value JSONB NOT NULL DEFAULT '{}'::JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, job_name, checkpoint_key)
);
