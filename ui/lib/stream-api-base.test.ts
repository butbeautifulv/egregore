import { afterEach, describe, expect, test } from "bun:test"

import { buildStreamUrl, streamApiBase } from "./stream-api-base"

const originalEnv = { ...process.env }

afterEach(() => {
  process.env = { ...originalEnv }
})

describe("streamApiBase", () => {
  test("uses NEXT_PUBLIC_STREAM_API_BASE when set", () => {
    process.env.NEXT_PUBLIC_STREAM_API_BASE = "https://gateway.example/"
    expect(streamApiBase()).toBe("https://gateway.example")
  })

  test("defaults to empty string in production", () => {
    delete process.env.NEXT_PUBLIC_STREAM_API_BASE
    process.env.NODE_ENV = "production"
    expect(streamApiBase()).toBe("")
  })

  test("defaults to local API in development", () => {
    delete process.env.NEXT_PUBLIC_STREAM_API_BASE
    process.env.NODE_ENV = "development"
    expect(streamApiBase()).toBe("http://127.0.0.1:8080")
  })
})

describe("buildStreamUrl", () => {
  test("returns same-origin path when base is empty", () => {
    process.env.NEXT_PUBLIC_STREAM_API_BASE = ""
    expect(buildStreamUrl("/v1/engagements/eng-1/stream?tenant_id=default")).toBe(
      "/v1/engagements/eng-1/stream?tenant_id=default",
    )
  })

  test("prefixes gateway base when configured", () => {
    process.env.NEXT_PUBLIC_STREAM_API_BASE = "https://gateway.example"
    expect(buildStreamUrl("/status/stream")).toBe("https://gateway.example/status/stream")
  })
})
