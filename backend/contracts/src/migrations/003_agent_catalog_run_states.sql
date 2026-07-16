CREATE TABLE IF NOT EXISTS agent_catalog (
    name TEXT NOT NULL,
    profile_id TEXT NOT NULL DEFAULT 'cybersec-soc',
    payload JSONB NOT NULL,
    version INT NOT NULL DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (name, profile_id)
);

CREATE TABLE IF NOT EXISTS profile_packs (
    id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS run_states (
    tenant_id TEXT NOT NULL DEFAULT 'default',
    context_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, context_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_run_states_tenant_updated ON run_states (tenant_id, updated_at DESC);
