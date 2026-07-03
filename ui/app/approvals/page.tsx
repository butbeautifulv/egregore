"use client"

import { useEffect, useState } from "react"

import { listPendingApprovals, type PendingApproval } from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"

import { ApprovalActions } from "@/components/approval-actions"
import { RouteSkeleton } from "@/vendor/gui/shared/skeletons"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Alert, AlertDescription } from "@/vendor/gui/ui/alert"

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<PendingApproval[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const response = await listPendingApprovals()
        if (cancelled) return
        setApprovals(response.approvals)
        setError(null)
      } catch (exc) {
        if (cancelled) return
        setError(formatApiError(exc, "Failed to load approvals"))
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <RouteSkeleton variant="table" />
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Approvals"
        description="Human-in-the-loop tool actions awaiting operator decision."
      />

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {approvals.length === 0 ? (
        <EmptyTableState title="No pending approvals" description="All tool actions are resolved." />
      ) : (
        <div className="grid gap-4">
          {approvals.map((approval) => (
            <ApprovalActions key={approval.approval_id} approval={approval} />
          ))}
        </div>
      )}
    </div>
  )
}
