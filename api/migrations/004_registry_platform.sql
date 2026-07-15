CREATE TABLE IF NOT EXISTS catalog_audit (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL DEFAULT 'agent',
    resource_id TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'api',
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_catalog_audit_resource ON catalog_audit (resource_type, resource_id, ts DESC);

CREATE TABLE IF NOT EXISTS skill_catalog (
    id TEXT NOT NULL,
    profile_id TEXT NOT NULL DEFAULT 'cybersec-soc',
    payload JSONB NOT NULL,
    version INT NOT NULL DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, profile_id)
);

CREATE TABLE IF NOT EXISTS plan_catalog (
    id TEXT NOT NULL,
    profile_id TEXT NOT NULL DEFAULT 'cybersec-soc',
    payload JSONB NOT NULL,
    version INT NOT NULL DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, profile_id)
);

CREATE TABLE IF NOT EXISTS mcp_server_catalog (
    id TEXT NOT NULL,
    profile_id TEXT NOT NULL DEFAULT 'cybersec-soc',
    payload JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, profile_id)
);
