"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import type { EngagementStreamEvent } from "@/lib/api-client"
import {
  applyChatEvent,
  CHAT_THROTTLE_MS,
  createChatEntry,
  hydrateChatFromDetail,
  type ChatStateMap,
} from "@/lib/engagement-chat-state"
import type { AgentChatEntry, ApiFeatures } from "@/lib/types"

function cloneChatState(state: ChatStateMap): AgentChatEntry[] {
  return [...state.values()].map((entry) => ({
    ...entry,
    turns: [...entry.turns],
    tools: [...entry.tools],
    reasoning: entry.reasoning ? { ...entry.reasoning, reasoning_steps: [...entry.reasoning.reasoning_steps] } : null,
  }))
}

export function useEngagementChatState(
  engagementId: string,
  features: ApiFeatures,
  detail?: {
    findings_summary: Record<string, unknown>[]
    planner_plan: string[] | null
    planner_rationale: string
    planner_sub_goals?: Record<string, string>
    planner_depends_on?: Record<string, string[]>
    execution_mode?: string | null
    synthesis_persona?: string | null
  },
) {
  const stateRef = useRef<ChatStateMap>(new Map())
  const [entries, setEntries] = useState<AgentChatEntry[]>([])
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const versionRef = useRef(0)

  const scheduleFlush = useCallback(() => {
    if (flushTimerRef.current) return
    flushTimerRef.current = setTimeout(() => {
      flushTimerRef.current = null
      setEntries(cloneChatState(stateRef.current))
    }, CHAT_THROTTLE_MS)
  }, [])

  const flushNow = useCallback(() => {
    if (flushTimerRef.current) {
      clearTimeout(flushTimerRef.current)
      flushTimerRef.current = null
    }
    setEntries(cloneChatState(stateRef.current))
  }, [])

  useEffect(() => {
    stateRef.current = new Map()
    versionRef.current += 1
    if (detail) {
      hydrateChatFromDetail(
        stateRef.current,
        engagementId,
        detail.findings_summary,
        detail.planner_plan,
        detail.planner_rationale ?? "",
        {
          planner_sub_goals: detail.planner_sub_goals,
          planner_depends_on: detail.planner_depends_on,
          execution_mode: detail.execution_mode,
          synthesis_persona: detail.synthesis_persona,
        },
      )
      flushNow()
    } else {
      setEntries([])
    }
  }, [engagementId, detail, flushNow])

  const handleEvent = useCallback(
    (event: EngagementStreamEvent) => {
      const changed = applyChatEvent(stateRef.current, event, features, engagementId)
      if (changed) scheduleFlush()
    },
    [engagementId, features, scheduleFlush],
  )

  const setExpanded = useCallback(
    (jobId: string, expanded: boolean) => {
      const entry = stateRef.current.get(jobId) ?? createChatEntry(jobId)
      entry.agentExpanded = expanded
      stateRef.current.set(jobId, entry)
      flushNow()
    },
    [flushNow],
  )

  useEffect(() => {
    return () => {
      if (flushTimerRef.current) clearTimeout(flushTimerRef.current)
    }
  }, [])

  return { entries, handleEvent, setExpanded, flushNow }
}
