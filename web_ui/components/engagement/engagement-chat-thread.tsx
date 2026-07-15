"use client"

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import { ShieldAlertIcon } from "lucide-react"

import { listPendingApprovals, type PendingApproval } from "@/lib/api-client"
import { formatPlannerError } from "@/lib/format-api-error"
import { dedupeFindingsByPersona } from "@/lib/finding-display"
import {
  formatFollowUpMarkerLabel,
  splitInitialAndFollowUpPairs,
  type FollowUpMessage,
  type FollowUpPair,
} from "@/lib/follow-up"
import type { AgentChatEntry, JobSummary } from "@/lib/types"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { ApprovalActions } from "@/components/approval-actions"
import { AgentMessageBlock } from "@/components/engagement/agent-message-block"
import { FindingContent } from "@/components/engagement/finding-content"
import { OutcomeHero, outcomeCopyText } from "@/components/engagement/outcome-hero"
import { AssistantFindingPanel } from "@/components/engagement/assistant-finding-panel"
import { EngagementProgressStrip } from "@/components/engagement/engagement-progress-strip"
import { FollowUpComposer } from "@/components/engagement/follow-up-composer"
import { FollowUpComposerDock } from "@/components/engagement/follow-up-composer-dock"
import { JsonPayloadView } from "@/components/json-payload-view"
import { StructuredFindingsDialog } from "@/components/structured-findings-dialog"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { MessageActions } from "@/components/engagement/message-actions"
import { CHAT_COLUMN_CLASS, FOLLOW_UP_DOCK_PADDING_CLASS } from "@/lib/chat-layout"
import { cn } from "@/vendor/gui/utils"
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
  const text = message.text?.trim() ?? ""
  return (
    <div className={`group/message ${CHAT_COLUMN_CLASS}`}>
      <div className="flex flex-col items-end gap-2">
        <Bubble className="max-w-[85%]" variant="tinted" align="end">
          <BubbleContent className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.text}
          </BubbleContent>
        </Bubble>
        {text ? <MessageActions text={text} align="end" /> : null}
        {message.status === "failed" ? (
          <p className="text-destructive text-xs">{message.error ?? "Failed to queue follow-up"}</p>
        ) : (
          <p className="text-muted-foreground text-[10px]">
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
    </div>
  )
}

function OperatorTurnBlock({
  pair,
  followUpChildEntries,
  findingsByJobId,
}: {
  pair: FollowUpPair
  followUpChildEntries: Map<string, AgentChatEntry[]>
  findingsByJobId: Map<string, Record<string, unknown>>
}) {
  const childEntries = followUpChildEntries.get(pair.followUpId) ?? []
  return (
    <div className="flex flex-col gap-6">
      <div className={CHAT_COLUMN_CLASS}>
        <Marker variant="separator">
          <MarkerContent>
            {formatFollowUpMarkerLabel(
              pair.assistant?.workKind ?? pair.operator.workKind,
              pair.assistant?.persona ?? pair.operator.persona,
              pair.followUpId,
            )}
          </MarkerContent>
        </Marker>
      </div>
      {pair.operator.text ? <FollowUpOperatorBubble message={pair.operator} /> : null}
      {pair.assistant ? <AssistantFindingPanel message={pair.assistant} /> : null}
      {childEntries.length > 0 ? (
        <Collapsible className={CHAT_COLUMN_CLASS}>
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
}

export function EngagementChatThread({
  className,
  entries,
  jobs,
  findings = [],
  completedPersonas = [],
  intake,
  profileId,
  finalReport,
  plannerError,
  followUps = [],
  followUpChildEntries = new Map(),
  followUpSending = false,
  onSendFollowUp,
  composerDisabled = false,
  isFirstFollowUp = false,
  isTerminal = false,
}: {
  className?: string
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
  const followUpTailRef = useRef<HTMLDivElement>(null)
  const stickToBottomRef = useRef(false)
  const prevFollowUpSendingRef = useRef(false)
  const prevFollowUpsLengthRef = useRef(followUps.length)
  const jobIds = useMemo(() => new Set(jobs.map((j) => j.job_id)), [jobs])
  const { initialPair, followUpPairs } = useMemo(
    () => splitInitialAndFollowUpPairs(followUps),
    [followUps],
  )
  const hasInitialOperatorTurn = Boolean(initialPair?.operator.text?.trim())
  const isStreaming = entries.some((entry) => entry.streaming)
  const hasIntake = Boolean(intake && Object.keys(intake).length > 0)
  const hasFinalReport = Boolean(finalReport && Object.keys(finalReport).length > 0)

  const displayFindings = useMemo(() => dedupeFindingsByPersona(findings), [findings])

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
    const updateStickToBottom = () => {
      const threshold = 150
      stickToBottomRef.current =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - threshold
    }
    updateStickToBottom()
    window.addEventListener("scroll", updateStickToBottom, { passive: true })
    window.addEventListener("resize", updateStickToBottom, { passive: true })
    return () => {
      window.removeEventListener("scroll", updateStickToBottom)
      window.removeEventListener("resize", updateStickToBottom)
    }
  }, [])

  useEffect(() => {
    if (followUpSending && !prevFollowUpSendingRef.current) {
      stickToBottomRef.current = true
      requestAnimationFrame(() => {
        followUpTailRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
      })
    }
    prevFollowUpSendingRef.current = followUpSending
  }, [followUpSending])

  useEffect(() => {
    if (!isStreaming || !stickToBottomRef.current) return
    requestAnimationFrame(() => {
      if (!stickToBottomRef.current) return
      followUpTailRef.current?.scrollIntoView({ behavior: "auto", block: "end" })
    })
  }, [entries, isStreaming])

  useEffect(() => {
    if (followUps.length > prevFollowUpsLengthRef.current) {
      if (stickToBottomRef.current) {
        requestAnimationFrame(() => {
          followUpTailRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
        })
      }
    }
    prevFollowUpsLengthRef.current = followUps.length
  }, [followUps.length])

  const hitlForThread = approvals

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="border">
        <div className="bg-muted/20 flex flex-col gap-2 border-b px-4 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium">Work order chat</p>
            {displayFindings.length > 0 ? (
              <StructuredFindingsDialog
                findings={displayFindings}
                completedPersonas={completedPersonas}
                jobs={jobs}
              />
            ) : null}
          </div>
          <EngagementProgressStrip completedPersonas={completedPersonas} jobs={jobs} />
        </div>

        <div
          className={cn(
            "flex flex-col gap-8 py-6",
            onSendFollowUp ? FOLLOW_UP_DOCK_PADDING_CLASS : undefined,
          )}
          aria-busy={isStreaming || followUpSending}
        >
          {initialPair ? (
            <OperatorTurnBlock
              pair={initialPair}
              followUpChildEntries={followUpChildEntries}
              findingsByJobId={findingsByJobId}
            />
          ) : null}

          {hasIntake ? (
            <Collapsible className={CHAT_COLUMN_CLASS}>
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
            <div className={CHAT_COLUMN_CLASS}>
              <ApiErrorAlert title="Planner failed" message={formatPlannerError(plannerError)} />
            </div>
          ) : null}

          {hitlForThread.map((approval) => (
            <div key={approval.approval_id} className={`${CHAT_COLUMN_CLASS} space-y-3`}>
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

          {entries.length === 0 && !plannerError && !isTerminal && !hasInitialOperatorTurn ? (
            <div className={CHAT_COLUMN_CLASS}>
              <Marker role="status">
                <MarkerIcon>
                  <Spinner />
                </MarkerIcon>
                <MarkerContent className="shimmer">Waiting for agents…</MarkerContent>
              </Marker>
            </div>
          ) : (
            entries.map((entry) => {
              if (
                (entry.persona === "critic" || entry.persona === "coordinator") &&
                !entry.buffer.trim() &&
                !entry.jobError
              ) {
                return null
              }
              const isOutcomeJob = entry.jobId.endsWith("-synth")
              return (
                <AgentMessageBlock
                  key={entry.jobId}
                  entry={entry}
                  finding={findingsByJobId.get(entry.jobId)}
                  defaultOpen={entry.streaming || isOutcomeJob}
                />
              )
            })
          )}

          {hasFinalReport ? (
            <div className={`group/message ${CHAT_COLUMN_CLASS}`}>
              <div className="flex flex-col gap-3">
                <Marker variant="separator">
                  <MarkerContent>Final outcome</MarkerContent>
                </Marker>
                {finalReport && typeof finalReport === "object" && "kind" in finalReport ? (
                  <OutcomeHero outcome={finalReport as Record<string, unknown>} />
                ) : (
                  <div className="text-sm leading-7">
                    <FindingContent data={finalReport ?? {}} />
                  </div>
                )}
                <MessageActions
                  text={
                    finalReport && typeof finalReport === "object" && "summary" in finalReport
                      ? outcomeCopyText(finalReport as Record<string, unknown>)
                      : JSON.stringify(finalReport ?? {}, null, 2)
                  }
                />
              </div>
            </div>
          ) : null}

          {followUpPairs.map((pair) => (
            <OperatorTurnBlock
              key={pair.followUpId}
              pair={pair}
              followUpChildEntries={followUpChildEntries}
              findingsByJobId={findingsByJobId}
            />
          ))}
          <div ref={followUpTailRef} />
        </div>
      </div>

      {onSendFollowUp ? (
        <FollowUpComposerDock>
          <FollowUpComposer
            disabled={composerDisabled}
            sending={followUpSending}
            isFirstFollowUp={isFirstFollowUp}
            onSend={onSendFollowUp}
          />
        </FollowUpComposerDock>
      ) : (
        <div className="border px-4 py-4">
          <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center justify-between gap-2">
            <p className="text-muted-foreground text-xs">
              This engagement streams agent output live. HITL tool approvals appear above when needed.
            </p>
            <Button type="button" variant="outline" size="sm" asChild>
              <Link href="/">New work order</Link>
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
