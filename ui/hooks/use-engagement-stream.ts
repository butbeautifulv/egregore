"use client"

import { useEffect, useRef, useState } from "react"

import {
  createApiConnectTimeout,
  engagementStreamUrl,
  mergeAbortSignals,
  streamRequestHeaders,
  type EngagementStreamEvent,
} from "@/lib/api-client"

const INITIAL_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 30000

export type StreamStatus = "connecting" | "open" | "closed" | "error"

function parseSseChunk(chunk: string, onData: (data: string) => void) {
  for (const line of chunk.split("\n")) {
    if (line.startsWith("data:")) {
      onData(line.slice(5).trim())
    }
  }
}

export function useEngagementStream(
  engagementId: string,
  onEvent?: (event: EngagementStreamEvent) => void,
  enabled = true,
  tenantId = "default",
) {
  const [status, setStatus] = useState<StreamStatus>("connecting")
  const onEventRef = useRef(onEvent)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!enabled || !engagementId) {
      setStatus("closed")
      return
    }

    let cancelled = false
    let backoff = INITIAL_BACKOFF_MS
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let abortController: AbortController | null = null

    async function connect() {
      if (cancelled) return
      abortController?.abort()
      abortController = new AbortController()
      const connectTimeout = createApiConnectTimeout()
      setStatus("connecting")

      try {
        const response = await fetch(engagementStreamUrl(engagementId, tenantId), {
          headers: {
            Accept: "text/event-stream",
            ...streamRequestHeaders(),
          },
          credentials: "include",
          cache: "no-store",
          signal: mergeAbortSignals([abortController.signal, connectTimeout.signal]),
        })
        connectTimeout.clear()

        if (!response.ok || !response.body) {
          throw new Error(`SSE HTTP ${response.status}`)
        }

        backoff = INITIAL_BACKOFF_MS
        setStatus("open")

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""

        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split("\n\n")
          buffer = parts.pop() ?? ""
          for (const part of parts) {
            parseSseChunk(part, (data) => {
              try {
                const parsed = JSON.parse(data) as EngagementStreamEvent
                onEventRef.current?.(parsed)
              } catch {
                // ignore malformed payloads
              }
            })
          }
        }

        if (!cancelled) {
          setStatus("error")
          reconnectTimer = setTimeout(() => {
            backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)
            void connect()
          }, backoff)
        }
      } catch (exc) {
        connectTimeout.clear()
        if (cancelled || (exc instanceof DOMException && exc.name === "AbortError")) {
          return
        }
        setStatus("error")
        reconnectTimer = setTimeout(() => {
          backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)
          void connect()
        }, backoff)
      }
    }

    void connect()

    return () => {
      cancelled = true
      setStatus("closed")
      if (reconnectTimer) clearTimeout(reconnectTimer)
      abortController?.abort()
    }
  }, [engagementId, enabled, tenantId])

  return { status, connected: status === "open" }
}
