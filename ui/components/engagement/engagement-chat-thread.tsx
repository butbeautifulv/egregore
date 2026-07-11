"use client"

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import { ShieldAlertIcon } from "lucide-react"

import { listPendingApprovals, type PendingApproval } from "@/lib/api-client"
import { formatPlannerError } from "@/lib/format-api-error"
import {
  buildFollowUpJobMap,
  formatFollowUpMarkerLabel,
  groupFollowUpChildEntries,
  groupFollowUpPairs,
  isFollowUpChildJob,
  isFollowUpOrchestratorJob,
  type FollowUpMessage,
} from "@/lib/follow-up"
import type { AgentChatEntry, JobSummary } from "@/lib/types"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { ApprovalActions } from "@/components/approval-actions"
import { AgentMessageBlock } from "@/components/engagement/agent-message-block"
import { FindingContent } from "@/components/engagement/finding-content"
import { AssistantFindingPanel } from "@/components/engagement/assistant-finding-panel"
import { FollowUpComposer } from "@/components/engagement/follow-up-composer"
import { JsonPayloadView } from "@/components/json-payload-view"
import { StructuredFindingsDialog } from "@/components/structured-findings-dialog"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Marker, MarkerContent, MarkerIcon } from "@/components/ui/marker"
import { Button } from "@/vendor/gui/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"
import { Spinner } from "@/vendor/gui/ui/spinner"

function FollowUpOperatorBubble({ message }: { message: FollowUpMessage }) {
  const roleLabel = "You"
  return (
    <div className="flex flex-col items-end gap-1">
      <Bubble className="max-w-2xl" variant="default" align="end">
        <BubbleContent>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
        </BubbleContent>
      </Bubble>
      {message.status === "failed" ? (
        <p className="text-destructive max-w-2xl text-xs">{message.error ?? "Failed to queue follow-up"}</p>
      ) : (
        <p className="text-muted-foreground max-w-2xl text-[10px]">
          {roleLabel}
          {message.mode ? ` · ${message.mode}` : ""}
          {message.status === "queued" || message.status === "pending"
            ? " · queued"
            : message.status === "completed"
              ? " · sent"
              : ""}
        </p>
      )}
    </div>
  )
}

export function EngagementChatThread({
  goal,
  entries,
  jobs,
  findings = [],
  completedPersonas = [],
  intake,
  profileId,
  finalReport,
  plannerError,
  plannerStatus,
  followUps = [],
  followUpChildEntries = new Map(),
  followUpSending = false,
  onSendFollowUp,
  composerDisabled = false,
  isFirstFollowUp = false,
  isTerminal = false,
}: {
  goal: string
  entries: AgentChatEntry[]
  jobs: JobSummary[]
  findings?: Record<string, unknown>[]
  completedPersonas?: string[]
  intake?: Record<string, unknown> | null
  profileId?: string | null
  finalReport?: Record<string, unknown> | null
  plannerError?: string | null
  plannerStatus?: string | null
  followUps?: FollowUpMessage[]
  followUpChildEntries?: Map<string, AgentChatEntry[]>
  followUpSending?: boolean
  onSendFollowUp?: (message: string, mode: import("@/lib/follow-up").FollowUpMode) => Promise<boolean>
  composerDisabled?: boolean
  isFirstFollowUp?: boolean
  isTerminal?: boolean
}) {
  const [approvals, setApprovals] = useState<PendingApproval[]>([])
  const chatScrollRef = useRef<HTMLDivElement>(null)
  const followUpTailRef = useRef<HTMLDivElement>(null)
  const jobIds = useMemo(() => new Set(jobs.map((j) => j.job_id)), [jobs])
  const followUpPairs = useMemo(() => groupFollowUpPairs(followUps), [followUps])
  const isStreaming = entries.some((entry) => entry.streaming)
  const hasIntake = Boolean(intake && Object.keys(intake).length > 0)
  const hasFinalReport = Boolean(finalReport && Object.keys(finalReport).length > 0)

  const findingsByJobId = useMemo(() => {
    const map = new Map<string, Record<string, unknown>>()
    for (const item of findings) {
      const jobId = typeof item.job_id === "string" ? item.job_id : ""
      if (jobId) {
        map.set(jobId, item)
      }
    }
    return map
  }, [findings])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const response = await listPendingApprovals()
        if (cancelled) return
        setApprovals(response.approvals.filter((a) => jobIds.has(a.job_id)))
      } catch {
        if (!cancelled) setApprovals([])
      }
    }
    void load()
    const timer = setInterval(load, 8000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [jobIds])

  useEffect(() => {
    followUpTailRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [followUps, followUpSending])

  const hitlForThread = approvals

  return (
    <div className="flex flex-col gap-4">
      {plannerStatus ? (
        <Marker variant="separator">
          <MarkerContent>Planner · {plannerStatus}</MarkerContent>
        </Marker>
      ) : null}

      <div className="border">
        <div className="bg-muted/20 flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2">
          <p className="text-sm font-medium">Work order chat</p>
          {findings.length > 0 ? (
            <StructuredFindingsDialog
              findings={findings}
              completedPersonas={completedPersonas}
              jobs={jobs}
            />
          ) : null}
        </div>

        <div
          ref={chatScrollRef}
          className="flex max-h-[min(70vh,48rem)] flex-col gap-5 overflow-y-auto p-4"
          aria-busy={isStreaming || followUpSending}
        >
          <div className="flex justify-end">
            <Bubble className="max-w-2xl">
              <BubbleContent className="whitespace-pre-wrap">{goal || "No goal recorded"}</BubbleContent>
            </Bubble>
          </div>

          {hasIntake ? (
            <Collapsible className="max-w-2xl">
              <CollapsibleTrigger className="text-muted-foreground text-xs underline-offset-2 hover:underline">
                Request context
                {profileId ? ` · profile ${profileId}` : ""}
              </CollapsibleTrigger>
              <CollapsibleContent className="bg-muted/40 mt-2 border p-3">
                <JsonPayloadView data={intake ?? {}} title="Context" />
              </CollapsibleContent>
            </Collapsible>
          ) : null}

          {plannerError ? (
            <ApiErrorAlert title="Planner failed" message={formatPlannerError(plannerError)} />
          ) : null}

          {hitlForThread.map((approval) => (
            <div key={approval.approval_id} className="max-w-2xl space-y-3">
              <Marker variant="border" className="text-destructive">
                <MarkerIcon>
                  <ShieldAlertIcon />
                </MarkerIcon>
                <MarkerContent>Approval needed · {approval.tool_name}</MarkerContent>
              </Marker>
              <div className="bg-muted/40 border p-3">
                <ApprovalActions approval={approval} />
              </div>
            </div>
          ))}

          {entries.length === 0 && !plannerError && !isTerminal ? (
            <Marker role="status">
              <MarkerIcon>
                <Spinner />
              </MarkerIcon>
              <MarkerContent className="shimmer">Waiting for agents…</MarkerContent>
            </Marker>
          ) : (
            entries.map((entry) => (
              <AgentMessageBlock
                key={entry.jobId}
                entry={entry}
                finding={findingsByJobId.get(entry.jobId)}
                defaultOpen={entry.streaming}
              />
            ))
          )}

          {hasFinalReport ? (
            <div className="flex w-full max-w-2xl flex-col gap-2">
              <Marker variant="separator">
                <MarkerContent>Final report</MarkerContent>
              </Marker>
              <div className="bg-muted/40 border px-4 py-3">
                <FindingContent data={finalReport ?? {}} />
              </div>
            </div>
          ) : null}

          {followUpPairs.map((pair) => {
            const childEntries = followUpChildEntries.get(pair.followUpId) ?? []
            return (
            <div key={pair.followUpId} className="flex flex-col gap-3">
              <Marker variant="separator">
                <MarkerContent>
                  {formatFollowUpMarkerLabel(
                    pair.assistant?.workKind ?? pair.operator.workKind,
                    pair.assistant?.persona ?? pair.operator.persona,
                  )}
                </MarkerContent>
              </Marker>
              {pair.operator.text ? <FollowUpOperatorBubble message={pair.operator} /> : null}
              {pair.assistant ? <AssistantFindingPanel message={pair.assistant} /> : null}
              {childEntries.length > 0 ? (
                <Collapsible className="max-w-2xl">
                  <CollapsibleTrigger className="text-muted-foreground text-xs underline-offset-2 hover:underline">
                    Agents from this follow-up ({childEntries.length})
                  </CollapsibleTrigger>
                  <CollapsibleContent className="mt-3 flex flex-col gap-5">
                    {childEntries.map((entry) => (
                      <AgentMessageBlock
                        key={entry.jobId}
                        entry={entry}
                        finding={findingsByJobId.get(entry.jobId)}
                        defaultOpen={entry.streaming}
                      />
                    ))}
                  </CollapsibleContent>
                </Collapsible>
              ) : null}
            </div>
            )
          })}
          <div ref={followUpTailRef} />
        </div>

        <div className="bg-background border-t p-4">
          {onSendFollowUp ? (
            <FollowUpComposer
              disabled={composerDisabled}
              sending={followUpSending}
              isFirstFollowUp={isFirstFollowUp}
              onSend={onSendFollowUp}
            />
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-muted-foreground text-xs">
                This engagement streams agent output live. HITL tool approvals appear above when needed.
              </p>
              <Button type="button" variant="outline" size="sm" asChild>
                <Link href="/">New work order</Link>
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
