-- Worker job status and HITL pause state (durable across process restarts)

CREATE TABLE IF NOT EXISTS worker_jobs (
    job_id TEXT PRIMARY KEY,
    persona TEXT NOT NULL,
    event_id TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    tenant_id TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL,
    session_id TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    hitl_preview_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    pending_hitl_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_worker_jobs_status ON worker_jobs (status);
CREATE INDEX IF NOT EXISTS idx_worker_jobs_correlation ON worker_jobs (tenant_id, correlation_id);
