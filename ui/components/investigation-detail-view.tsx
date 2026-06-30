"use client"

import { useCallback, useEffect, useState } from "react"

import { getInvestigation, getInvestigationJobs } from "@/lib/api-client"
import type { InvestigationDetail, JobSummary } from "@/lib/types"
import { InvestigationTimeline } from "@/components/investigation-timeline"
import { JobCard } from "@/components/job-card"
import { PersonaStepper } from "@/components/persona-stepper"
import { useStatusStream } from "@/hooks/use-status-stream"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

type InvestigationDetailViewProps = {
  investigationId: string
  initialDetail: InvestigationDetail
  initialJobs: JobSummary[]
}

export function InvestigationDetailView({
  investigationId,
  initialDetail,
  initialJobs,
}: InvestigationDetailViewProps) {
  const [detail, setDetail] = useState(initialDetail)
  const [jobs, setJobs] = useState(initialJobs)
  const [error, setError] = useState<string | null>(null)
  const { events, connected } = useStatusStream()

  const refresh = useCallback(async () => {
    try {
      const [nextDetail, nextJobs] = await Promise.all([
        getInvestigation(investigationId),
        getInvestigationJobs(investigationId),
      ])
      setDetail(nextDetail)
      setJobs(nextJobs.jobs)
      setError(null)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to refresh investigation")
    }
  }, [investigationId])

  useEffect(() => {
    const timer = setInterval(() => {
      void refresh()
    }, 5000)
    return () => clearInterval(timer)
  }, [refresh])

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{detail.investigation_id}</h1>
        <p className="text-muted-foreground text-sm">{detail.goal || "No goal recorded"}</p>
        <p className="text-muted-foreground text-xs">
          Status: {detail.status} · SSE {connected ? "connected" : "reconnecting"}
        </p>
      </div>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Persona pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <PersonaStepper
            plannerPlan={detail.planner_plan}
            completedPersonas={detail.completed_personas}
            jobs={jobs}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {jobs.map((job) => (
          <JobCard key={job.job_id} job={job} />
        ))}
      </div>

      <InvestigationTimeline investigationId={investigationId} events={events} />
    </div>
  )
}
