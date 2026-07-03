import type { InvestigationDetail, JobSummary } from "@/lib/types"

export function isInvestigationTerminal(
  detail: InvestigationDetail | null,
  jobs: JobSummary[] = [],
): boolean {
  if (!detail) {
    return false
  }
  if (detail.status === "closed") {
    return true
  }
  const plan = detail.planner_plan ?? []
  if (plan.length > 0) {
    const completed = new Set(detail.completed_personas ?? [])
    if (plan.every((persona) => completed.has(persona))) {
      return true
    }
  }
  if (jobs.length === 0) {
    return false
  }
  const planSet = plan.length > 0 ? new Set(plan) : null
  const relevant = planSet ? jobs.filter((job) => planSet.has(job.persona)) : jobs
  if (relevant.length === 0) {
    return false
  }
  return relevant.every((job) => job.status === "completed" || job.status === "failed")
}
