"use client"

import { useCallback, useEffect, useState } from "react"

import { ApiError, getInvestigation, getInvestigationJobs, subscribeEngagementStream } from "@/lib/api-client"
import { isInvestigationTerminal } from "@/lib/investigation-status"
import { matchesInvestigation } from "@/lib/status-events"
import type { InvestigationDetail, JobSummary, StatusStreamEvent } from "@/lib/types"
import { InvestigationFindings } from "@/components/investigation-findings"
import { InvestigationTimeline } from "@/components/investigation-timeline"
import { JobCard } from "@/components/job-card"
import { PageSection } from "@/components/page-section"
import { PersonaStepper } from "@/components/persona-stepper"
import { useStatusStream } from "@/hooks/use-status-stream"
import { RouteSkeleton } from "@/vendor/gui/shared/skeletons"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Alert, AlertDescription, AlertTitle } from "@/vendor/gui/ui/alert"
import { Badge } from "@/vendor/gui/ui/badge"
import { CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"

type InvestigationDetailViewProps = {
  investigationId: string
  initialDetail?: InvestigationDetail
  initialJobs?: JobSummary[]
}

function plannerBadgeVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "ready" || status === "ok") return "default"
  if (status === "fallback") return "secondary"
  if (status === "error") return "destructive"
  return "outline"
}

function formatPlannerRationale(rationale: string): string {
  if (rationale === "planner_invalid_personas_fallback") {
    return "Planner proposed unavailable personas; defaulted to catalog fallback."
  }
  return rationale
}

export function InvestigationDetailView({
  investigationId,
  initialDetail,
  initialJobs,
}: InvestigationDetailViewProps) {
  const [detail, setDetail] = useState<InvestigationDetail | null>(initialDetail ?? null)
  const [jobs, setJobs] = useState<JobSummary[]>(initialJobs ?? [])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(!initialDetail)

  const refresh = useCallback(async () => {
    if (!investigationId) {
      return
    }
    try {
      const [nextDetail, nextJobs] = await Promise.all([
        getInvestigation(investigationId),
        getInvestigationJobs(investigationId),
      ])
      setDetail(nextDetail)
      setJobs(nextJobs.jobs)
      setError(null)
    } catch (exc) {
      if (exc instanceof ApiError && exc.status === 404) {
        setError("Investigation not found")
        setDetail(null)
        setJobs([])
        return
      }
      setError(exc instanceof Error ? exc.message : "Failed to refresh investigation")
    } finally {
      setLoading(false)
    }
  }, [investigationId])

  const onStreamEvent = useCallback(
    (event: StatusStreamEvent) => {
      if (matchesInvestigation(event, investigationId)) {
        void refresh()
      }
    },
    [investigationId, refresh],
  )

  const { events, status: streamStatus } = useStatusStream(onStreamEvent)
  const streamConnected = streamStatus === "open"
  const terminal = isInvestigationTerminal(detail, jobs)

  useEffect(() => {
    if (initialDetail) {
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const [nextDetail, nextJobs] = await Promise.all([
          getInvestigation(investigationId),
          getInvestigationJobs(investigationId),
        ])
        if (cancelled) return
        setDetail(nextDetail)
        setJobs(nextJobs.jobs)
        setError(null)
      } catch (exc) {
        if (cancelled) return
        if (exc instanceof ApiError && exc.status === 404) {
          setError("Investigation not found")
          setDetail(null)
          setJobs([])
          return
        }
        setError(exc instanceof Error ? exc.message : "Failed to refresh investigation")
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [initialDetail, investigationId])

  useEffect(() => {
    if (!detail || terminal) {
      return
    }
    if (detail.status !== "in_progress" && detail.status !== "open") {
      return
    }
    const timer = setInterval(() => {
      void refresh()
    }, 12000)
    return () => clearInterval(timer)
  }, [detail, terminal, refresh])

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_EGRESS_SSE !== "1" || !investigationId || terminal) {
      return
    }
    return subscribeEngagementStream(investigationId, () => {
      void refresh()
    })
  }, [investigationId, terminal, refresh])

  if (!investigationId) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Missing investigation id</AlertTitle>
      </Alert>
    )
  }

  if (loading) {
    return <RouteSkeleton variant="detail" />
  }

  if (!detail) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Investigation" description={investigationId} backHref="/" backLabel="Investigations" />
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={detail.investigation_id}
        backHref="/"
        backLabel="Investigations"
        description={detail.goal || "No goal recorded"}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{detail.status}</Badge>
            {terminal ? (
              <Badge variant="default">Completed</Badge>
            ) : (
              <Badge variant={streamConnected ? "secondary" : "outline"}>
                {streamConnected ? "SSE Connected" : "SSE Reconnecting"}
              </Badge>
            )}
          </div>
        }
      />

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {detail.planner_status ? (
        <PageSection>
          <CardHeader className="flex flex-row items-center justify-between gap-2">
            <CardTitle>Planner</CardTitle>
            <Badge variant={plannerBadgeVariant(detail.planner_status)}>{detail.planner_status}</Badge>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-xs">
            {detail.planner_rationale ? (
              <p className="text-muted-foreground">{formatPlannerRationale(detail.planner_rationale)}</p>
            ) : null}
            {detail.planner_error ? (
              <Collapsible>
                <CollapsibleTrigger className="text-destructive hover:underline">
                  Show planner error
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <Alert variant="destructive" className="mt-2">
                    <AlertTitle>Planner error</AlertTitle>
                    <AlertDescription className="font-mono text-xs whitespace-pre-wrap">
                      {detail.planner_error}
                    </AlertDescription>
                  </Alert>
                </CollapsibleContent>
              </Collapsible>
            ) : null}
          </CardContent>
        </PageSection>
      ) : null}

      <PageSection>
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
      </PageSection>

      <InvestigationFindings
        findings={detail.findings_summary ?? []}
        completedPersonas={detail.completed_personas ?? []}
        jobs={jobs}
      />

      {jobs.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {jobs.map((job) => (
            <JobCard key={job.job_id} job={job} />
          ))}
        </div>
      ) : null}

      <InvestigationTimeline investigationId={investigationId} events={events} />
    </div>
  )
}
