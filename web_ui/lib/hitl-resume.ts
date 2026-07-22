import { resumeJob } from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"
import type { PendingApproval } from "@/lib/types"

export async function resumeHitlApproval(
  approval: Pick<PendingApproval, "job_id" | "approval_id">,
  decision: "approve" | "reject",
  actor = "operator-ui",
): Promise<void> {
  await resumeJob(approval.job_id, {
    decision,
    approval_id: approval.approval_id,
    actor,
  })
}

export function formatHitlResumeError(exc: unknown, fallback = "Action failed"): string {
  return formatApiError(exc, fallback)
}
