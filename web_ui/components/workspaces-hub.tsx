"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { createWorkspace, type WorkspaceSummary } from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"
import { getSelectedTenantId } from "@/lib/workspace"
import { invalidateWorkspaces, useWorkspaces } from "@/hooks/use-workspaces"
import {
  createWorkspaceColumns,
  workspaceGlobalFilter,
} from "@/lib/data-table/columns/workspace-columns"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { EgregoreRouteSkeleton } from "@/components/skeletons"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { DataTable } from "@/vendor/gui/data-table/data-table"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { Input } from "@/vendor/gui/ui/input"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Spinner } from "@/vendor/gui/ui/spinner"

export function WorkspacesHub() {
  const router = useRouter()
  const tenantId = getSelectedTenantId()
  const { workspaces, loading, error, rawError, refresh } = useWorkspaces(tenantId)

  const [name, setName] = useState("")
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<unknown>(null)

  const columns = useMemo(() => createWorkspaceColumns(), [])

  async function onCreate() {
    const trimmed = name.trim()
    if (!trimmed || creating) return
    setCreating(true)
    setCreateError(null)
    try {
      await createWorkspace({ name: trimmed, tenant_id: tenantId })
      setName("")
      invalidateWorkspaces(tenantId)
      await refresh()
    } catch (exc) {
      setCreateError(exc)
    } finally {
      setCreating(false)
    }
  }

  if (loading && !workspaces) {
    return <EgregoreRouteSkeleton variant="table" />
  }

  return (
    <div className="@container/main flex flex-col gap-6">
      <PageHeader title="Workspaces" description="Team sandboxes for custom worker personas" />

      <Card>
        <CardHeader>
          <CardTitle>Create workspace</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {createError ? (
            <ApiErrorAlert
              error={createError}
              fallback={formatApiError(createError, "Failed to create workspace")}
              onRetry={() => void onCreate()}
            />
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void onCreate()
              }}
              placeholder="Blue Team"
              className="max-w-sm"
              disabled={creating}
            />
            <Button type="button" onClick={() => void onCreate()} disabled={creating || !name.trim()}>
              {creating ? <Spinner data-icon="inline-start" /> : null}
              Create
            </Button>
          </div>
        </CardContent>
      </Card>

      {error ? (
        <ApiErrorAlert
          error={rawError}
          fallback="Failed to load workspaces"
          onRetry={() => void refresh()}
          isStale={Boolean(workspaces)}
        />
      ) : null}

      {workspaces && workspaces.length === 0 && !error ? (
        <EmptyTableState
          title="No workspaces yet"
          description="Create a workspace above to get started."
        />
      ) : (
        <DataTable
          columns={columns}
          data={workspaces ?? []}
          searchPlaceholder="Search workspaces…"
          globalFilterFn={workspaceGlobalFilter}
          pageSize={20}
          onRowClick={(row: WorkspaceSummary) => router.push(`/workspaces/${row.id}`)}
        />
      )}
    </div>
  )
}
