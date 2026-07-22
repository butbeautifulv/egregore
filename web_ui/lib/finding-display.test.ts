import { describe, expect, test } from "bun:test"

import { formatFindingField, isDisplayableFindingKey } from "@/lib/finding-display"

describe("formatFindingField", () => {
  test("humanizes snake_case keys", () => {
    expect(formatFindingField("recommended_actions")).toBe("Recommended Actions")
  })
})

describe("isDisplayableFindingKey", () => {
  test("allows unknown pack-specific keys", () => {
    expect(isDisplayableFindingKey("custom_pack_field")).toBe(true)
    expect(isDisplayableFindingKey("job_id")).toBe(false)
  })
})
