import type { CatalogAgent } from "@/lib/api-client"

const claimedApprovalIds = new Set<string>()

export function isChatAutoApproveEnabled(): boolean {
  return process.env.NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE === "1"
}

export function buildAutoApprovePersonaSet(agents: CatalogAgent[]): Set<string> {
  const personas = new Set<string>()
  for (const agent of agents) {
    if (agent.hitl_auto_approve) {
      personas.add(agent.name)
    }
  }
  return personas
}

/** Returns false if this approval_id was already claimed (dedupe Strict Mode / hydrate). */
export function claimAutoApprove(approvalId: string): boolean {
  const id = approvalId.trim()
  if (!id) return false
  if (claimedApprovalIds.has(id)) return false
  claimedApprovalIds.add(id)
  return true
}

export function resetAutoApproveClaimsForTests(): void {
  claimedApprovalIds.clear()
}
