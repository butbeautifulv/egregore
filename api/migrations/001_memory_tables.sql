-- Cross-session episodic memory and investigation state (MAS memory layer)

CREATE TABLE IF NOT EXISTS agent_memory_entries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL,
    persona TEXT,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    source_agent TEXT NOT NULL DEFAULT '',
    source_job_id TEXT NOT NULL DEFAULT '',
    trust_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    checksum TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_investigation
    ON agent_memory_entries (tenant_id, investigation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS investigation_states (
    tenant_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL,
    state_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, investigation_id)
);
