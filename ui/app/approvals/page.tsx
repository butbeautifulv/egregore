import { listPendingApprovals } from "@/lib/api-client"

import { ApprovalActions } from "@/components/approval-actions"
import { PageHeader } from "@/vendor/gui/layout/page-header"

export default async function ApprovalsPage() {
  let error: string | null = null
  let approvals: Awaited<ReturnType<typeof listPendingApprovals>>["approvals"] = []

  try {
    const response = await listPendingApprovals()
    approvals = response.approvals
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Failed to load approvals"
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Approvals"
        description="Human-in-the-loop tool actions awaiting operator decision."
      />

      {error ? <p className="text-destructive text-xs">{error}</p> : null}

      {approvals.length === 0 ? (
        <p className="text-muted-foreground text-xs">No pending approvals.</p>
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
