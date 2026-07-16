CREATE TABLE IF NOT EXISTS tool_catalog (
    id TEXT NOT NULL,
    profile_id TEXT NOT NULL DEFAULT 'cybersec-soc',
    payload JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, profile_id)
);
