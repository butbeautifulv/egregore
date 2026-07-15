import { describe, expect, test } from "bun:test"

import type { EngagementStreamEvent } from "@/lib/api-client"
import {
  applyChatEvent,
  createChatEntry,
  eventDedupeKey,
  type ChatStateMap,
} from "@/lib/engagement-chat-state"
import type { ApiFeatures } from "@/lib/types"

const features: ApiFeatures = {
  streamAgentTools: true,
  streamAgentOutput: true,
}

function toolEvent(
  type: "tool_start" | "tool_done" | "tool_error",
  jobId: string,
  toolName: string,
  toolCallId: string,
  extra: Record<string, unknown> = {},
): EngagementStreamEvent {
  return {
    type,
    payload: { job_id: jobId, tool_name: toolName, tool_call_id: toolCallId, ...extra },
  }
}

function stateWithJob(jobId: string): ChatStateMap {
  const state: ChatStateMap = new Map()
  state.set(jobId, createChatEntry(jobId, "consultant"))
  return state
}

describe("applyChatEvent tool upsert", () => {
  const jobId = "job-consultant-1"
  const toolCallId = "019f61f6-b97e-75c2-975b-5e184870332b"

  test("tool_start twice with same tool_call_id keeps one row", () => {
    const state = stateWithJob(jobId)
    const start = toolEvent("tool_start", jobId, "playbook_search", toolCallId)

    expect(applyChatEvent(state, start, features, "eng-1")).toBe(true)
    expect(applyChatEvent(state, start, features, "eng-1")).toBe(true)

    const entry = state.get(jobId)!
    expect(entry.tools).toHaveLength(1)
    expect(entry.tools[0]?.tool_call_id).toBe(toolCallId)
    expect(entry.tools[0]?.status).toBe("started")
  })

  test("tool_start then tool_done yields one done row", () => {
    const state = stateWithJob(jobId)
    applyChatEvent(state, toolEvent("tool_start", jobId, "playbook_search", toolCallId), features, "eng-1")
    applyChatEvent(
      state,
      toolEvent("tool_done", jobId, "playbook_search", toolCallId, {
        ok: true,
        output_preview: '{"count":2,"skills":[]}',
      }),
      features,
      "eng-1",
    )

    const entry = state.get(jobId)!
    expect(entry.tools).toHaveLength(1)
    expect(entry.tools[0]?.status).toBe("done")
  })

  test("replayed tool_done after completion is a no-op", () => {
    const state = stateWithJob(jobId)
    const done = toolEvent("tool_done", jobId, "playbook_search", toolCallId, { ok: true })
    applyChatEvent(state, toolEvent("tool_start", jobId, "playbook_search", toolCallId), features, "eng-1")
    applyChatEvent(state, done, features, "eng-1")
    applyChatEvent(state, done, features, "eng-1")

    expect(state.get(jobId)?.tools).toHaveLength(1)
    expect(state.get(jobId)?.tools[0]?.status).toBe("done")
  })
})

describe("eventDedupeKey", () => {
  test("assistant_delta includes seq for ingress dedupe", () => {
    const base = {
      type: "assistant_delta",
      payload: { job_id: "job-1", seq: 1, delta: "hello" },
    } satisfies EngagementStreamEvent
    const next = {
      type: "assistant_delta",
      payload: { job_id: "job-1", seq: 2, delta: " world" },
    } satisfies EngagementStreamEvent

    expect(eventDedupeKey(base)).not.toBe(eventDedupeKey(next))
  })
})

describe("applyChatEvent assistant_delta", () => {
  test("skips duplicate seq on replay", () => {
    const state = stateWithJob("job-1")
    const event = {
      type: "assistant_delta",
      payload: { job_id: "job-1", seq: 3, delta: "hello" },
    } satisfies EngagementStreamEvent

    expect(applyChatEvent(state, event, features, "eng-1")).toBe(true)
    expect(applyChatEvent(state, event, features, "eng-1")).toBe(false)

    expect(state.get("job-1")?.buffer).toBe("hello")
    expect(state.get("job-1")?.lastAssistantSeq).toBe(3)
  })
})

describe("applyChatEvent assistant_snapshot", () => {
  test("skips replay when buffer already matches snapshot text", () => {
    const state = stateWithJob("job-1")
    const entry = state.get("job-1")!
    entry.buffer = "full planner json"
    entry.streaming = true

    const changed = applyChatEvent(
      state,
      {
        type: "assistant_snapshot",
        payload: { job_id: "job-1", text: "full planner json" },
      },
      features,
      "eng-1",
    )

    expect(changed).toBe(false)
    expect(entry.buffer).toBe("full planner json")
    expect(entry.streaming).toBe(false)
  })

  test("replaces partial buffer with full snapshot text", () => {
    const state = stateWithJob("job-1")
    const entry = state.get("job-1")!
    entry.buffer = "partial"
    entry.streaming = true

    const changed = applyChatEvent(
      state,
      {
        type: "assistant_snapshot",
        payload: { job_id: "job-1", text: "partial response complete" },
      },
      features,
      "eng-1",
    )

    expect(changed).toBe(true)
    expect(entry.buffer).toBe("partial response complete")
    expect(entry.streaming).toBe(false)
  })
})
