"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  ApiError,
  isNotFoundError,
  listWorkOrderFollowUps,
  sendWorkOrderFollowUp,
  type EngagementStreamEvent,
} from "@/lib/api-client"
import {
  followUpContentTypeFromPayload,
  isFollowUpJobId,
  mapFollowUpTurn,
  mergeFollowUpAnswerText,
  parseFollowUpFinding,
  type FollowUpMessage,
  type FollowUpMode,
} from "@/lib/follow-up"

function upsertMessage(current: FollowUpMessage[], next: FollowUpMessage): FollowUpMessage[] {
  const byId = current.findIndex(
    (item) =>
      item.id === next.id ||
      (item.followUpId === next.followUpId && item.role === next.role),
  )
  if (byId >= 0) {
    const copy = [...current]
    copy[byId] = { ...copy[byId], ...next }
    return copy
  }
  return [...current, next]
}

function resolveFollowUpId(
  payload: Record<string, unknown>,
  jobIdToFollowUpId: Map<string, string>,
): string {
  const fromPayload = String(payload.follow_up_id ?? "")
  if (fromPayload) return fromPayload
  const jobId = String(payload.job_id ?? "")
  if (jobId) return jobIdToFollowUpId.get(jobId) ?? ""
  return ""
}

function buildAssistantFromComplete(
  followUpId: string,
  payload: Record<string, unknown>,
  existing?: FollowUpMessage,
): FollowUpMessage {
  const finding = parseFollowUpFinding(payload)
  const text = mergeFollowUpAnswerText(
    existing?.text,
    finding ? JSON.stringify(finding, null, 2) : String(payload.text ?? ""),
  )
  return {
    id: existing?.id ?? `assistant-${followUpId}`,
    followUpId,
    role: "assistant",
    text,
    createdAt: existing?.createdAt ?? new Date().toISOString(),
    status: "completed",
    persona:
      typeof payload.persona === "string" ? payload.persona : (existing?.persona ?? null),
    jobId: typeof payload.job_id === "string" ? payload.job_id : (existing?.jobId ?? null),
    workKind:
      typeof payload.work_kind === "string" ? payload.work_kind : (existing?.workKind ?? null),
    contentType: followUpContentTypeFromPayload(payload) ?? existing?.contentType ?? null,
    finding: finding ?? existing?.finding ?? null,
    streaming: false,
  }
}

export function useFollowUpMessages(investigationId: string) {
  const [messages, setMessages] = useState<FollowUpMessage[]>([])
  const [sending, setSending] = useState(false)
  const jobIdToFollowUpIdRef = useRef(new Map<string, string>())

  const reloadFollowUps = useCallback(async () => {
    if (!investigationId) return
    try {
      const data = await listWorkOrderFollowUps(investigationId)
      const fromApi = data.turns.map(mapFollowUpTurn)
      for (const turn of data.turns) {
        if (turn.job_id && turn.follow_up_id) {
          jobIdToFollowUpIdRef.current.set(turn.job_id, turn.follow_up_id)
        }
      }
      setMessages((current) => {
        let merged = [...current]
        for (const message of fromApi) {
          merged = upsertMessage(merged, message)
        }
        return merged
      })
    } catch {
      setMessages([])
    }
  }, [investigationId])

  useEffect(() => {
    jobIdToFollowUpIdRef.current = new Map()
    const stored = sessionStorage.getItem(`wo-initial-fu:${investigationId}`)
    if (stored) {
      jobIdToFollowUpIdRef.current.set("", stored)
    }
    void (async () => {
      await reloadFollowUps()
    })()
  }, [investigationId, reloadFollowUps])

  const upsertAssistantStream = useCallback(
    (
      followUpId: string,
      updater: (current: FollowUpMessage | undefined) => FollowUpMessage,
    ) => {
      setMessages((current) => {
        const existing = current.find(
          (item) => item.followUpId === followUpId && item.role === "assistant",
        )
        return upsertMessage(current, updater(existing))
      })
    },
    [],
  )

  const handleStreamEvent = useCallback(
    (event: EngagementStreamEvent) => {
      const payload = event.payload ?? {}
      const type = event.type ?? ""
      const jobId = String(payload.job_id ?? "")

      if (type === "follow_up_queued" || type === "follow_up_plan_started") {
        const followUpId = resolveFollowUpId(payload, jobIdToFollowUpIdRef.current)
        if (!followUpId) return
        if (jobId) jobIdToFollowUpIdRef.current.set(jobId, followUpId)
        upsertAssistantStream(followUpId, (existing) => ({
          id: existing?.id ?? `assistant-${followUpId}`,
          followUpId,
          role: "assistant",
          text: existing?.text ?? "",
          createdAt: existing?.createdAt ?? new Date().toISOString(),
          status: "pending",
          persona: typeof payload.persona === "string" ? payload.persona : existing?.persona ?? null,
          jobId: jobId || existing?.jobId || null,
          workKind:
            typeof payload.work_kind === "string" ? payload.work_kind : existing?.workKind ?? null,
          streaming: true,
        }))
        return
      }

      if (
        (type === "assistant_delta" || type === "assistant_snapshot" || type === "assistant_done") &&
        jobId &&
        isFollowUpJobId(jobId)
      ) {
        const followUpId = resolveFollowUpId(payload, jobIdToFollowUpIdRef.current)
        if (!followUpId) return
        if (type === "assistant_delta") {
          const delta = String(payload.delta ?? "")
          upsertAssistantStream(followUpId, (existing) => ({
            id: existing?.id ?? `assistant-${followUpId}`,
            followUpId,
            role: "assistant",
            text: `${existing?.text ?? ""}${delta}`,
            createdAt: existing?.createdAt ?? new Date().toISOString(),
            status: "pending",
            persona: typeof payload.persona === "string" ? payload.persona : existing?.persona ?? null,
            jobId,
            workKind: existing?.workKind ?? null,
            streaming: true,
          }))
          return
        }
        if (type === "assistant_snapshot") {
          const text = String(payload.text ?? "")
          const finding = parseFollowUpFinding({ text })
          upsertAssistantStream(followUpId, (existing) => {
            const mergedText = text || existing?.text || ""
            if (existing?.text === mergedText) {
              return { ...existing, streaming: false }
            }
            return {
              id: existing?.id ?? `assistant-${followUpId}`,
              followUpId,
              role: "assistant",
              text: mergedText,
              createdAt: existing?.createdAt ?? new Date().toISOString(),
              status: "pending",
              persona:
                typeof payload.persona === "string" ? payload.persona : existing?.persona ?? null,
              jobId,
              workKind: existing?.workKind ?? "follow_up_plan",
              contentType: finding ? "plan" : existing?.contentType ?? null,
              finding: finding ?? existing?.finding ?? null,
              streaming: true,
            }
          })
          return
        }
        if (type === "assistant_done") {
          upsertAssistantStream(followUpId, (existing) => ({
            id: existing?.id ?? `assistant-${followUpId}`,
            followUpId,
            role: "assistant",
            text: existing?.text ?? "",
            createdAt: existing?.createdAt ?? new Date().toISOString(),
            status: existing?.status === "completed" ? "completed" : "pending",
            persona: typeof payload.persona === "string" ? payload.persona : existing?.persona ?? null,
            jobId,
            workKind: existing?.workKind ?? null,
            streaming: false,
          }))
          return
        }
      }

      if (type === "status" && event.phase === "job_finished" && jobId && isFollowUpJobId(jobId)) {
        const followUpId = resolveFollowUpId(payload, jobIdToFollowUpIdRef.current)
        if (!followUpId) return
        if (payload.success === false) {
          const err = String(payload.error ?? "Follow-up failed")
          setMessages((current) =>
            current.map((item) =>
              item.followUpId === followUpId && item.role === "operator"
                ? { ...item, status: "failed", error: err }
                : item,
            ),
          )
          upsertAssistantStream(followUpId, (existing) => ({
            id: existing?.id ?? `assistant-${followUpId}`,
            followUpId,
            role: "assistant",
            text: existing?.text ?? "",
            createdAt: existing?.createdAt ?? new Date().toISOString(),
            status: "failed",
            persona: existing?.persona ?? null,
            jobId,
            workKind: existing?.workKind ?? null,
            streaming: false,
            error: err,
          }))
        }
        return
      }

      if (
        type !== "follow_up_complete" &&
        type !== "follow_up_failed" &&
        type !== "follow_up_plan_complete"
      ) {
        return
      }

      const followUpId = String(payload.follow_up_id ?? "")
      const text = String(payload.text ?? payload.error ?? "")
      if (!followUpId) return

      if (type === "follow_up_complete" || type === "follow_up_plan_complete") {
        setMessages((current) => {
          const existing = current.find(
            (item) => item.followUpId === followUpId && item.role === "assistant",
          )
          return upsertMessage(current, buildAssistantFromComplete(followUpId, payload, existing))
        })
        setMessages((current) =>
          current.map((item) =>
            item.followUpId === followUpId && item.role === "operator"
              ? { ...item, status: "completed" }
              : item,
          ),
        )
        void reloadFollowUps()
        return
      }

      setMessages((current) =>
        current.map((item) =>
          item.followUpId === followUpId && item.role === "operator"
            ? { ...item, status: "failed", error: text || "Follow-up failed" }
            : item,
        ),
      )
    },
    [reloadFollowUps, upsertAssistantStream],
  )

  const sendFollowUp = useCallback(
    async (text: string, mode: FollowUpMode = "auto") => {
      const trimmed = text.trim()
      if (!trimmed || sending) return false

      setSending(true)
      const optimisticId = `followup-local-${Date.now().toString(36)}`
      const optimistic: FollowUpMessage = {
        id: optimisticId,
        followUpId: optimisticId,
        role: "operator",
        text: trimmed,
        createdAt: new Date().toISOString(),
        status: "queued",
        mode,
      }
      setMessages((current) => [...current, optimistic])

      try {
        const result = await sendWorkOrderFollowUp(investigationId, { message: trimmed, mode })
        if (result.job_id) {
          jobIdToFollowUpIdRef.current.set(result.job_id, result.follow_up_id)
        }
        setMessages((current) =>
          current.map((item) =>
            item.id === optimisticId
              ? {
                  ...item,
                  followUpId: result.follow_up_id,
                  status: result.status === "pending" ? "pending" : "queued",
                  jobId: result.job_id ?? null,
                  workKind: result.work_kind,
                  mode,
                }
              : item,
          ),
        )
        if (result.status !== "pending" && result.job_id) {
          upsertAssistantStream(result.follow_up_id, () => ({
            id: `assistant-${result.follow_up_id}`,
            followUpId: result.follow_up_id,
            role: "assistant",
            text: "",
            createdAt: new Date().toISOString(),
            status: "pending",
            persona: null,
            jobId: result.job_id ?? null,
            workKind: result.work_kind,
            streaming: true,
          }))
        }
        toast.success("Follow-up queued", {
          description:
            result.status === "pending"
              ? "Another follow-up is running — yours is queued."
              : result.work_kind === "follow_up_plan"
                ? "Planner will re-run agents for this work order."
                : "Agents will respond in this thread.",
        })
        return true
      } catch (exc) {
        const error =
          exc instanceof ApiError && isNotFoundError(exc)
            ? "Follow-up API unavailable. Restart: cd projects/egregore && ./scripts/dev.sh"
            : exc instanceof Error
              ? exc.message
              : "Failed to queue follow-up"
        setMessages((current) =>
          current.map((item) =>
            item.id === optimisticId ? { ...item, status: "failed", error } : item,
          ),
        )
        toast.error("Could not queue follow-up", { description: error })
        return false
      } finally {
        setSending(false)
      }
    },
    [investigationId, sending, upsertAssistantStream],
  )

  return { messages, sending, sendFollowUp, handleStreamEvent }
}
