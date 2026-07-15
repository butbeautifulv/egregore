import { afterEach, describe, expect, test } from "bun:test"

import { buildStreamUrl, streamApiBase } from "./stream-api-base"

const originalEnv = { ...process.env }

afterEach(() => {
  process.env = { ...originalEnv }
})

// Next.js augments NodeJS.ProcessEnv with a readonly NODE_ENV literal type;
// tests still need to set it to exercise each branch.
function setNodeEnv(value: string): void {
  ;(process.env as Record<string, string | undefined>).NODE_ENV = value
}

describe("streamApiBase", () => {
  test("uses NEXT_PUBLIC_STREAM_API_BASE when set", () => {
    process.env.NEXT_PUBLIC_STREAM_API_BASE = "https://gateway.example/"
    expect(streamApiBase()).toBe("https://gateway.example")
  })

  test("defaults to empty string in production", () => {
    delete process.env.NEXT_PUBLIC_STREAM_API_BASE
    setNodeEnv("production")
    expect(streamApiBase()).toBe("")
  })

  test("defaults to local API in development on the server", () => {
    delete process.env.NEXT_PUBLIC_STREAM_API_BASE
    setNodeEnv("development")
    expect(streamApiBase()).toBe("http://127.0.0.1:8080")
  })
})

describe("streamApiBase in browser", () => {
  const originalWindow = globalThis.window

  afterEach(() => {
    if (originalWindow === undefined) {
      // @ts-expect-error test cleanup
      delete globalThis.window
    } else {
      globalThis.window = originalWindow
    }
  })

  test("uses same-origin API proxy in the browser", () => {
    // @ts-expect-error minimal browser stub for streamApiBase
    globalThis.window = {}
    delete process.env.NEXT_PUBLIC_STREAM_API_BASE
    setNodeEnv("development")
    expect(streamApiBase()).toBe("/api/egregore")
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
