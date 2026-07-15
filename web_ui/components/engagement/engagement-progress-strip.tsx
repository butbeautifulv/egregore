"use client"

import type { JobSummary } from "@/lib/types"
import { Badge } from "@/vendor/gui/ui/badge"

export function EngagementProgressStrip({
  completedPersonas,
  jobs,
  plannerPlan,
}: {
  completedPersonas: string[]
  jobs: JobSummary[]
  plannerPlan?: string[] | null
}) {
  const planned = plannerPlan?.length ? plannerPlan : []
  const running = jobs.filter((job) => job.status === "running" || job.status === "pending").map((j) => j.persona)
  const completed = completedPersonas.length ? completedPersonas : jobs.filter((j) => j.status === "completed").map((j) => j.persona)

  if (!planned.length && !completed.length && !running.length) {
    return null
  }

  return (
    <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
      <span className="text-foreground font-medium">Progress</span>
      {planned.map((persona) => {
        const done = completed.includes(persona)
        const active = running.includes(persona)
        return (
          <Badge key={persona} variant={done ? "secondary" : active ? "default" : "outline"}>
            {persona}
            {done ? " ✓" : active ? " …" : ""}
          </Badge>
        )
      })}
      {!planned.length
        ? completed.map((persona) => (
            <Badge key={persona} variant="secondary">
              {persona} ✓
            </Badge>
          ))
        : null}
    </div>
  )
}
