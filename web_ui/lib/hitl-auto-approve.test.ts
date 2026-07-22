import { afterEach, describe, expect, test } from "bun:test"

import {
  buildAutoApprovePersonaSet,
  claimAutoApprove,
  isChatAutoApproveEnabled,
  resetAutoApproveClaimsForTests,
} from "@/lib/hitl-auto-approve"

describe("isChatAutoApproveEnabled", () => {
  const original = process.env.NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE

  afterEach(() => {
    if (original === undefined) {
      delete process.env.NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE
    } else {
      process.env.NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE = original
    }
  })

  test("disabled unless env is 1", () => {
    delete process.env.NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE
    expect(isChatAutoApproveEnabled()).toBe(false)
    process.env.NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE = "0"
    expect(isChatAutoApproveEnabled()).toBe(false)
    process.env.NEXT_PUBLIC_HITL_CHAT_AUTO_APPROVE = "1"
    expect(isChatAutoApproveEnabled()).toBe(true)
  })
})

describe("buildAutoApprovePersonaSet", () => {
  test("includes only flagged personas", () => {
    const set = buildAutoApprovePersonaSet([
      { name: "gaia_solver", hitl_auto_approve: true },
      { name: "redteam", hitl_auto_approve: false },
      { name: "consultant" },
    ])
    expect(set.has("gaia_solver")).toBe(true)
    expect(set.has("redteam")).toBe(false)
    expect(set.has("consultant")).toBe(false)
  })
})

describe("claimAutoApprove", () => {
  afterEach(() => {
    resetAutoApproveClaimsForTests()
  })

  test("dedupes second claim for same approval id", () => {
    expect(claimAutoApprove("appr-1")).toBe(true)
    expect(claimAutoApprove("appr-1")).toBe(false)
  })
})
