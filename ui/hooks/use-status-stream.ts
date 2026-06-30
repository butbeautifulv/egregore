"use client"

import { useEffect, useState } from "react"

import { statusStreamUrl } from "@/lib/api-client"
import type { StatusStreamEvent } from "@/lib/types"

const INITIAL_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 15000

export function useStatusStream(onEvent?: (event: StatusStreamEvent) => void) {
  const [events, setEvents] = useState<StatusStreamEvent[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let source: EventSource | null = null
    let backoff = INITIAL_BACKOFF_MS
    let cancelled = false
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    function connect() {
      if (cancelled) {
        return
      }
      source = new EventSource(statusStreamUrl())
      source.onopen = () => {
        backoff = INITIAL_BACKOFF_MS
        setConnected(true)
      }
      source.onmessage = (message) => {
        try {
          const parsed = JSON.parse(message.data) as StatusStreamEvent
          if (parsed.kind === "heartbeat") {
            return
          }
          setEvents((current) => [...current.slice(-199), parsed])
          onEvent?.(parsed)
        } catch {
          // ignore malformed payloads
        }
      }
      source.onerror = () => {
        setConnected(false)
        source?.close()
        if (!cancelled) {
          reconnectTimer = setTimeout(() => {
            backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)
            connect()
          }, backoff)
        }
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
      }
      source?.close()
      setConnected(false)
    }
  }, [onEvent])

  return { events, connected }
}
