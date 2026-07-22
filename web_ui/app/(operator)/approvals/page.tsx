"use client"

import { useMemo } from "react"

import { listPendingApprovals } from "@/lib/api-client"
import { createApprovalColumns } from "@/lib/data-table/columns/approval-columns"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { useApiQuery } from "@/hooks/use-api-query"
import { EgregoreRouteSkeleton } from "@/components/skeletons"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { DataTable } from "@/vendor/gui/data-table/data-table"

export default function ApprovalsPage() {
  const { data, error, loading, refresh, isStale } = useApiQuery(
    async () => {
      const response = await listPendingApprovals()
      return response.approvals
    },
    [],
    { fallback: "Failed to load approvals" },
  )
  const approvals = data ?? []
  const columns = useMemo(() => createApprovalColumns(), [])

  if (loading && !data) {
    return <EgregoreRouteSkeleton variant="table" />
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Approvals"
        description="Human-in-the-loop tool actions awaiting operator decision."
      />

      {error ? (
        <ApiErrorAlert
          error={error}
          fallback="Failed to load approvals"
          onRetry={() => void refresh()}
          isStale={isStale}
        />
      ) : null}

      {approvals.length === 0 && !error ? (
        <EmptyTableState
          title="No pending approvals"
          description="When an agent pauses for a high-risk tool, the approval appears inline in the work order chat. This page is a global inbox for all pending actions."
        />
      ) : approvals.length > 0 ? (
        <DataTable
          columns={columns}
          data={approvals}
          searchPlaceholder="Search approvals…"
          pageSize={20}
        />
      ) : null}
    </div>
  )
}
