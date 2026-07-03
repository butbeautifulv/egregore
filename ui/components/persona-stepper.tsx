import { CheckCircle2, CircleDashed, LoaderCircle, XCircle } from "lucide-react"

import type { JobSummary, PersonaStepState } from "@/lib/types"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { Badge } from "@/vendor/gui/ui/badge"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"

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

const stateVariant: Record<PersonaStepState, "default" | "secondary" | "destructive" | "outline"> = {
  done: "default",
  running: "secondary",
  pending: "outline",
  failed: "destructive",
}

function StateIcon({ state }: { state: PersonaStepState }) {
  if (state === "done") return <CheckCircle2 className="size-3.5" />
  if (state === "running") return <LoaderCircle className="size-3.5 animate-spin" />
  if (state === "failed") return <XCircle className="size-3.5" />
  return <CircleDashed className="size-3.5" />
}

export function PersonaStepper({ plannerPlan, completedPersonas, jobs }: PersonaStepperProps) {
  const personas = plannerPlan?.length ? plannerPlan : [...new Set(jobs.map((job) => job.persona))]
  if (personas.length === 0) {
    return (
      <EmptyTableState
        title="No persona plan yet"
        description="The planner has not assigned personas to this investigation."
      />
    )
  }

  return (
    <ol className="flex flex-wrap gap-2">
      {personas.map((persona, index) => {
        const state = stepState(persona, completedPersonas, jobs)
        return (
          <li key={persona} className="flex items-center gap-2">
            <Badge variant={stateVariant[state]} className="gap-1.5 rounded-full px-3 py-1">
              <StateIcon state={state} />
              <OverflowText>{`${index + 1}. ${persona}`}</OverflowText>
            </Badge>
            {index < personas.length - 1 ? <span className="text-muted-foreground">→</span> : null}
          </li>
        )
      })}
    </ol>
  )
}
