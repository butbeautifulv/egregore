import type { JobSummary, PersonaStepState } from "@/lib/types"
import { Badge } from "@/vendor/gui/ui/badge"
import { cn } from "@/lib/utils"

type PersonaStepperProps = {
  plannerPlan: string[] | null | undefined
  completedPersonas: string[]
  jobs: JobSummary[]
}

function stepState(persona: string, completed: string[], jobs: JobSummary[]): PersonaStepState {
  if (completed.includes(persona)) {
    return "done"
  }
  const job = jobs.find((item) => item.persona === persona)
  if (!job) {
    return "pending"
  }
  if (job.status === "failed") {
    return "failed"
  }
  if (job.status === "running" || job.status === "awaiting_approval") {
    return "running"
  }
  if (job.status === "completed") {
    return "done"
  }
  return "pending"
}

const stateStyles: Record<PersonaStepState, string> = {
  done: "border-primary/40 bg-primary/10 text-primary",
  running: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  pending: "border-border bg-muted text-muted-foreground",
  failed: "border-destructive/40 bg-destructive/10 text-destructive",
}

export function PersonaStepper({ plannerPlan, completedPersonas, jobs }: PersonaStepperProps) {
  const personas = plannerPlan?.length ? plannerPlan : [...new Set(jobs.map((job) => job.persona))]
  if (personas.length === 0) {
    return <p className="text-muted-foreground text-sm">No persona plan yet.</p>
  }

  return (
    <ol className="flex flex-wrap gap-2">
      {personas.map((persona, index) => {
        const state = stepState(persona, completedPersonas, jobs)
        return (
          <li key={persona} className="flex items-center gap-2">
            <Badge className={cn("rounded-full px-3 py-1", stateStyles[state])} variant="outline">
              {index + 1}. {persona}
            </Badge>
            {index < personas.length - 1 ? <span className="text-muted-foreground">→</span> : null}
          </li>
        )
      })}
    </ol>
  )
}
