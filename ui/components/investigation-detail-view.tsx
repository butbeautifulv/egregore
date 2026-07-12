"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { ApiError, getEngagementEvents, getInvestigation, getInvestigationJobs } from "@/lib/api-client"
import { formatApiError, getApiErrorTitle } from "@/lib/format-api-error"
import { plannerJobId, eventDedupeKey, eventPayload, shouldRefreshOnEvent, sortChatEntries } from "@/lib/engagement-chat-state"
import { isFollowUpJobId, buildFollowUpJobMap, groupFollowUpChildEntries, isFollowUpChildJob, isFollowUpOrchestratorJob, isFollowUpTurn } from "@/lib/follow-up"
import { isInvestigationTerminal } from "@/lib/investigation-status"
import { matchesInvestigation } from "@/lib/status-events"
import type { InvestigationDetail, JobSummary, StatusStreamEvent } from "@/lib/types"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { EngagementChatThread } from "@/components/engagement/engagement-chat-thread"
import { usePlatformBreadcrumbLabel } from "@/components/platform-breadcrumb"
import { useApiFeatures } from "@/hooks/use-api-features"
import { useEngagementChatState } from "@/hooks/use-engagement-chat"
import { useFollowUpMessages } from "@/hooks/use-follow-up-messages"
import { useEngagementStream } from "@/hooks/use-engagement-stream"
import { useStatusStream } from "@/hooks/use-status-stream"
import { EgregoreRouteSkeleton } from "@/components/skeletons"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Badge } from "@/vendor/gui/ui/badge"

type InvestigationDetailViewProps = {
  investigationId: string
  initialDetail?: InvestigationDetail
  initialJobs?: JobSummary[]
}

const SSE_ENABLED = process.env.NEXT_PUBLIC_EGRESS_SSE === "1"

export function InvestigationDetailView({
  investigationId,
  initialDetail,
  initialJobs,
}: InvestigationDetailViewProps) {
  const [detail, setDetail] = useState<InvestigationDetail | null>(initialDetail ?? null)
  const [jobs, setJobs] = useState<JobSummary[]>(initialJobs ?? [])
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(!initialDetail)

  usePlatformBreadcrumbLabel(detail?.investigation_id ?? investigationId)

  const { features } = useApiFeatures()
  const chatDetail = useMemo(
    () =>
      detail
        ? {
            findings_summary: detail.findings_summary ?? [],
            planner_plan: detail.planner_plan,
            planner_rationale: detail.planner_rationale ?? "",
            planner_sub_goals: detail.planner_sub_goals ?? {},
            planner_depends_on: detail.planner_depends_on ?? {},
            execution_mode: detail.execution_mode ?? null,
            synthesis_persona: detail.synthesis_persona ?? null,
            failed_personas: detail.failed_personas ?? [],
          }
        : undefined,
    [detail],
  )
  const { entries, handleEvent } = useEngagementChatState(investigationId, features, chatDetail, jobs)
  const { messages: followUps, sending: followUpSending, sendFollowUp, handleStreamEvent } =
    useFollowUpMessages(investigationId)
  const seenKeysRef = useRef(new Set<string>())
  const replayedRef = useRef(false)
  const followUpJobMapRef = useRef(new Map<string, string>())
  const refreshDetailOnlyRef = useRef<() => Promise<void>>(async () => {})

  const refreshDetailOnly = useCallback(async () => {
    if (!investigationId) return
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
        setError(exc)
        setDetail(null)
        setJobs([])
        return
      }
      setError(exc)
    } finally {
      setLoading(false)
    }
  }, [investigationId])

  refreshDetailOnlyRef.current = refreshDetailOnly

  const applyEngagementEvent = useCallback(
    (event: Parameters<typeof handleEvent>[0]) => {
      const key = eventDedupeKey(event)
      if (seenKeysRef.current.has(key)) return
      seenKeysRef.current.add(key)

      const payload = eventPayload(event)
      const jobId = payload.job_id ? String(payload.job_id) : ""
      const followUpId = payload.follow_up_id ? String(payload.follow_up_id) : ""
      if (followUpId && jobId) {
        followUpJobMapRef.current.set(jobId, followUpId)
      }
      if (followUpId && Array.isArray(payload.job_ids)) {
        for (const item of payload.job_ids) {
          const childJobId = String(item)
          if (childJobId) followUpJobMapRef.current.set(childJobId, followUpId)
        }
      }
      if (jobId && isFollowUpJobId(jobId)) {
        handleStreamEvent(event)
        return
      }
      if (
        event.type === "follow_up_complete" ||
        event.type === "follow_up_failed" ||
        event.type === "follow_up_queued" ||
        event.type === "follow_up_plan_started" ||
        event.type === "follow_up_plan_complete"
      ) {
        handleStreamEvent(event)
        return
      }

      handleEvent(event)
      handleStreamEvent(event)
      if (shouldRefreshOnEvent(event)) {
        void refreshDetailOnlyRef.current()
      }
    },
    [handleEvent, handleStreamEvent],
  )

  const replayEngagementEvents = useCallback(async () => {
    if (!investigationId) return
    try {
      const events = await getEngagementEvents(investigationId)
      for (const event of events) {
        applyEngagementEvent(event)
      }
    } catch {
      // events endpoint optional on very old API builds
    }
  }, [investigationId, applyEngagementEvent])

  const refresh = useCallback(async () => {
    await refreshDetailOnly()
  }, [refreshDetailOnly])

  const onStreamEvent = useCallback(
    (event: StatusStreamEvent) => {
      if (matchesInvestigation(event, investigationId)) {
        void refresh()
      }
    },
    [investigationId, refresh],
  )

  const { status: globalStreamStatus } = useStatusStream(onStreamEvent)
  const terminal = isInvestigationTerminal(detail, jobs)

  const onEngagementEvent = applyEngagementEvent

  const { status: engagementStreamStatus } = useEngagementStream(
    investigationId,
    onEngagementEvent,
    SSE_ENABLED,
  )

  useEffect(() => {
    seenKeysRef.current = new Set()
    replayedRef.current = false
    followUpJobMapRef.current = new Map()
  }, [investigationId])

  useEffect(() => {
    if (replayedRef.current) return
    replayedRef.current = true
    void replayEngagementEvents()
  }, [investigationId, replayEngagementEvents])

  useEffect(() => {
    if (initialDetail) return
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
          setError(exc)
          setDetail(null)
          setJobs([])
          return
        }
        setError(exc)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [initialDetail, investigationId])

  useEffect(() => {
    if (!detail || terminal) return
    if (SSE_ENABLED && engagementStreamStatus === "open") return
    if (detail.status !== "in_progress" && detail.status !== "open" && detail.status !== "running") {
      return
    }
    const timer = setInterval(() => {
      void refresh()
    }, 12000)
    return () => clearInterval(timer)
  }, [detail, terminal, refresh, engagementStreamStatus])

  useEffect(() => {
    if (engagementStreamStatus !== "error") return
    toast.error("Engagement stream disconnected — reconnecting…")
    seenKeysRef.current = new Set()
    void replayEngagementEvents()
  }, [engagementStreamStatus, replayEngagementEvents])

  const followUpJobMap = useMemo(
    () => {
      const merged = buildFollowUpJobMap(jobs, followUps)
      for (const [jobId, fuId] of followUpJobMapRef.current) {
        merged.set(jobId, fuId)
      }
      return merged
    },
    [jobs, followUps],
  )

  const followUpChildEntries = useMemo(
    () => groupFollowUpChildEntries(entries, followUpJobMap),
    [entries, followUpJobMap],
  )

  const sortedEntries = useMemo(
    () =>
      sortChatEntries(
        entries.filter(
          (entry) =>
            !isFollowUpOrchestratorJob(entry.jobId) && !isFollowUpChildJob(entry.jobId, followUpJobMap),
        ),
        plannerJobId(investigationId),
        detail?.planner_plan ?? null,
        jobs,
      ),
    [entries, investigationId, detail?.planner_plan, jobs, followUpJobMap],
  )

  const isFollowUpPlanRunning = useMemo(() => {
    if (detail?.status === "closed") return false
    return followUps.some(
      (item) =>
        item.workKind === "follow_up_plan" &&
        (item.streaming || item.status === "pending" || item.status === "queued"),
    )
  }, [detail?.status, followUps])

  const isFirstFollowUp = useMemo(
    () => !followUps.some((item) => item.role === "operator" && isFollowUpTurn(item.followUpId)),
    [followUps],
  )

  const hasInitialQaPending = useMemo(
    () =>
      followUps.some(
        (item) =>
          item.workKind === "initial_qa" &&
          (item.streaming || item.status === "pending" || item.status === "queued"),
      ),
    [followUps],
  )

  const followUpPlanFailedMessage = useMemo(() => {
    const failed = followUps.find(
      (item) =>
        item.role === "assistant" &&
        item.workKind === "follow_up_plan" &&
        item.status === "failed",
    )
    if (!failed) return null
    return (failed.error ?? failed.text ?? "").trim() || null
  }, [followUps])

  const plannerErrorForThread = useMemo(() => {
    if (detail?.planner_status !== "error" || !detail.planner_error?.trim()) return null
    const err = detail.planner_error.trim()
    if (followUpPlanFailedMessage && err === followUpPlanFailedMessage) return null
    return err
  }, [detail?.planner_status, detail?.planner_error, followUpPlanFailedMessage])

  const streamConnected =
    engagementStreamStatus === "open" || globalStreamStatus === "open"

  if (!investigationId) {
    return (
      <ApiErrorAlert
        title="Missing work order id"
        message="Open a work order from the list or start a new one."
      />
    )
  }

  if (loading) {
    return <EgregoreRouteSkeleton variant="investigation" />
  }

  if (!detail) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Work order" description={investigationId} backHref="/" backLabel="Work orders" />
        {error ? (
          <ApiErrorAlert
            error={error}
            title={getApiErrorTitle(error, "Work order")}
            message={formatApiError(error, "Work order not found")}
            onRetry={() => void refresh()}
          />
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={detail.work_order_id ?? detail.investigation_id}
        backHref="/"
        backLabel="Work orders"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{detail.status}</Badge>
            {detail.profile_id ? <Badge variant="secondary">{detail.profile_id}</Badge> : null}
            {terminal ? (
              <Badge variant="default">Completed</Badge>
            ) : (
              <Badge variant={streamConnected ? "secondary" : "outline"}>
                {streamConnected ? "Stream connected" : "Stream reconnecting"}
              </Badge>
            )}
          </div>
        }
      />

      {error ? (
        <ApiErrorAlert
          error={error}
          title={getApiErrorTitle(error, "Work order")}
          message={formatApiError(error, "Failed to refresh work order")}
          onRetry={() => void refresh()}
        />
      ) : null}

      {isFollowUpPlanRunning ? (
        <ApiErrorAlert
          title="Re-plan in progress"
          message="The planner is running follow-up agents. The composer unlocks when the work order closes again."
        />
      ) : null}

      <EngagementChatThread
        entries={sortedEntries}
        jobs={jobs}
        findings={detail.findings_summary ?? []}
        completedPersonas={detail.completed_personas ?? []}
        intake={detail.intake}
        profileId={detail.profile_id}
        finalReport={detail.final_report}
        plannerError={plannerErrorForThread}
        plannerStatus={detail.planner_status}
        followUps={followUps}
        followUpChildEntries={followUpChildEntries}
        followUpSending={followUpSending}
        onSendFollowUp={sendFollowUp}
        composerDisabled={
          followUpSending ||
          isFollowUpPlanRunning ||
          hasInitialQaPending ||
          detail.status !== "closed"
        }
        isFirstFollowUp={isFirstFollowUp}
        isTerminal={terminal}
      />
    </div>
  )
}
