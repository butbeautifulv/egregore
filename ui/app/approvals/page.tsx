import { listPendingApprovals } from "@/lib/api-client"

import { ApprovalActions } from "@/components/approval-actions"

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
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Approvals</h1>
        <p className="text-muted-foreground text-sm">Human-in-the-loop tool actions awaiting operator decision.</p>
      </div>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}

      {approvals.length === 0 ? (
        <p className="text-muted-foreground text-sm">No pending approvals.</p>
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
