from __future__ import annotations

CATALOG_SCHEMA_SQL = """
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
CREATE TABLE IF NOT EXISTS catalog_audit (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL DEFAULT 'agent',
    resource_id TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'api',
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
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
CREATE TABLE IF NOT EXISTS tool_catalog (
    id TEXT NOT NULL,
    profile_id TEXT NOT NULL DEFAULT 'cybersec-soc',
    payload JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, profile_id)
);
"""
