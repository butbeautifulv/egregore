const WORKSPACE_STORAGE_KEY = "egregore_workspace_id"
const TENANT_STORAGE_KEY = "egregore_tenant_id"

export function getSelectedWorkspaceId(): string {
  if (typeof window === "undefined") {
    return ""
  }
  return window.localStorage.getItem(WORKSPACE_STORAGE_KEY) ?? ""
}

export function setSelectedWorkspaceId(workspaceId: string): void {
  if (typeof window === "undefined") {
    return
  }
  if (!workspaceId.trim()) {
    window.localStorage.removeItem(WORKSPACE_STORAGE_KEY)
    return
  }
  window.localStorage.setItem(WORKSPACE_STORAGE_KEY, workspaceId.trim())
}

export function getSelectedTenantId(): string {
  if (typeof window === "undefined") {
    return "default"
  }
  return window.localStorage.getItem(TENANT_STORAGE_KEY) ?? "default"
}

export function setSelectedTenantId(tenantId: string): void {
  if (typeof window === "undefined") {
    return
  }
  const value = tenantId.trim() || "default"
  window.localStorage.setItem(TENANT_STORAGE_KEY, value)
}
