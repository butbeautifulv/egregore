"use client"

import { useCallback, useEffect, useState } from "react"

import { getInvestigation, getInvestigationJobs } from "@/lib/api-client"
import type { InvestigationDetail, JobSummary } from "@/lib/types"
import { InvestigationFindings } from "@/components/investigation-findings"
import { InvestigationTimeline } from "@/components/investigation-timeline"
import { JobCard } from "@/components/job-card"
import { PersonaStepper } from "@/components/persona-stepper"
import { useStatusStream } from "@/hooks/use-status-stream"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { PageHeader } from "@/vendor/gui/layout/page-header"

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
      <PageHeader
        title={detail.investigation_id}
        description={
          <>
            {detail.goal || "No goal recorded"}
            <span className="mt-1 block text-xs">
              Status: {detail.status} · SSE {connected ? "connected" : "reconnecting"}
            </span>
          </>
        }
      />

      {error ? <p className="text-destructive text-xs">{error}</p> : null}

      {detail.planner_status ? (
        <Card>
          <CardHeader>
            <CardTitle>Planner</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs">
            <p>
              Status: <span className="font-medium">{detail.planner_status}</span>
              {detail.planner_rationale ? ` · ${detail.planner_rationale}` : null}
            </p>
            {detail.planner_error ? (
              <p className="text-destructive">Error: {detail.planner_error}</p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Persona pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <PersonaStepper
            plannerPlan={detail.planner_plan}
            completedPersonas={detail.completed_personas}
            jobs={jobs}
          />
        </CardContent>
      </Card>

      <InvestigationFindings
        findings={detail.findings_summary ?? []}
        completedPersonas={detail.completed_personas ?? []}
      />

      <div className="grid gap-4 md:grid-cols-2">
        {jobs.map((job) => (
          <JobCard key={job.job_id} job={job} />
        ))}
      </div>

      <InvestigationTimeline investigationId={investigationId} events={events} />
    </div>
  )
}
