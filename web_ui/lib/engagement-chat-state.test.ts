import { describe, expect, test } from "bun:test"

import type { EngagementStreamEvent } from "@/lib/api-client"
import {
  applyChatEvent,
  createChatEntry,
  eventDedupeKey,
  formatJobFailure,
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

describe("formatJobFailure", () => {
  test("schema_invalid maps empty_finding without duplicate raw code in buffer path", () => {
    expect(
      formatJobFailure({ error: "empty_finding", reason: "schema_invalid" }),
    ).toBe("Agent finished without a valid structured result.")
    expect(
      formatJobFailure({ error: "empty_finding:missing_summary", reason: "schema_invalid" }),
    ).toBe("Agent finished without a valid structured result (missing: missing_summary).")
  })

  test.each([
    ["grounding_rejected", "ungrounded_finding:missing_evidence", "Result failed evidence or grounding checks: missing_evidence"],
    ["llm_error", "model_refusal:policy", "Model refused: policy"],
    ["tool_error", "tools_not_executed:playbook_search", "Tools were planned but never executed. playbook_search"],
    ["tool_invalid_args", "bad_args", "A tool was called with invalid arguments."],
    ["timeout", "deadline", "The agent run timed out before completing."],
    ["budget_exceeded", "tokens", "The agent run exceeded its cost or token budget."],
    ["sandbox_error", "sandbox", "The execution sandbox failed."],
    ["security_violation", "blocked", "The run was blocked by a security policy."],
    ["cancelled", "hitl_rejected", "The agent run was cancelled."],
  ] as const)("reason %s maps to operator copy", (reason, error, expected) => {
    expect(formatJobFailure({ error, reason })).toBe(expected)
  })
})

describe("applyChatEvent job_finished", () => {
  test("failed job_finished sets formatted buffer once using reason", () => {
    const state = stateWithJob("job-1")
    applyChatEvent(
      state,
      {
        type: "status",
        phase: "job_finished",
        payload: {
          job_id: "job-1",
          success: false,
          error: "empty_finding",
          reason: "schema_invalid",
        },
      },
      features,
      "eng-1",
    )
    const entry = state.get("job-1")!
    expect(entry.buffer).toBe("Agent finished without a valid structured result.")
    expect(entry.jobError).toBe("empty_finding")
  })
})

describe("applyChatEvent hitl", () => {
  test("hitl_pending attaches to job entry", () => {
    const state = stateWithJob("job-soc-1")
    applyChatEvent(
      state,
      {
        type: "hitl_pending",
        payload: {
          job_id: "job-soc-1",
          approval_id: "appr-1",
          tool_name: "run_active_scan",
          tool_args: { target: "lab" },
          risk_level: "high",
        },
      },
      features,
      "eng-1",
    )
    const entry = state.get("job-soc-1")!
    expect(entry.hitl?.status).toBe("pending")
    expect(entry.hitl?.toolName).toBe("run_active_scan")
    expect(entry.streaming).toBe(false)
  })

  test("hitl_resolved reject marks failure", () => {
    const state = stateWithJob("job-soc-1")
    applyChatEvent(
      state,
      {
        type: "hitl_pending",
        payload: {
          job_id: "job-soc-1",
          approval_id: "appr-1",
          tool_name: "run_active_scan",
        },
      },
      features,
      "eng-1",
    )
    applyChatEvent(
      state,
      {
        type: "hitl_resolved",
        payload: { job_id: "job-soc-1", approval_id: "appr-1", decision: "reject" },
      },
      features,
      "eng-1",
    )
    const entry = state.get("job-soc-1")!
    expect(entry.hitl?.status).toBe("rejected")
    expect(entry.buffer).toContain("cancelled")
  })
})

describe("applyChatEvent job_started", () => {
  test("sets streaming and expands agent block", () => {
    const state: ChatStateMap = new Map()
    applyChatEvent(
      state,
      {
        type: "status",
        phase: "job_started",
        payload: { job_id: "job-soc-1", persona: "soc" },
      },
      features,
      "eng-1",
    )
    const entry = state.get("job-soc-1")!
    expect(entry.persona).toBe("soc")
    expect(entry.streaming).toBe(true)
    expect(entry.agentExpanded).toBe(true)
  })
})

describe("applyChatEvent outcome events", () => {
  test("outcome_ready fills buffer from summary", () => {
    const state = stateWithJob("job-synth-1")
    applyChatEvent(
      state,
      {
        type: "outcome_ready",
        payload: {
          job_id: "job-synth-1",
          outcome: { kind: "synthesis", summary: "Deploy MFA everywhere" },
        },
      },
      features,
      "eng-1",
    )
    expect(state.get("job-synth-1")?.buffer).toBe("Deploy MFA everywhere")
    expect(state.get("job-synth-1")?.streaming).toBe(false)
  })

  test("final_report fills buffer from report summary", () => {
    const state = stateWithJob("job-synth-1")
    applyChatEvent(
      state,
      {
        type: "status",
        phase: "final_report",
        payload: {
          job_id: "job-synth-1",
          report: { kind: "synthesis", summary: "Final outcome text" },
        },
      },
      features,
      "eng-1",
    )
    expect(state.get("job-synth-1")?.buffer).toBe("Final outcome text")
    expect(state.get("job-synth-1")?.streaming).toBe(false)
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
