export const DEFAULT_API_UPSTREAM =
  process.env.EGREGORE_API_UPSTREAM ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8080" : "http://egregore-api:8080")

export const PROXY_BASE = "/api/egregore"

export const WORKSPACE_HEADER = "X-Workspace-Id"

export const WORKSPACE_STORAGE_KEY = "egregore_workspace_id"

export const TENANT_STORAGE_KEY = "egregore_tenant_id"
