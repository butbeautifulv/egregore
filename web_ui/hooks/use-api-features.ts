"use client"

import { useEffect, useState } from "react"

import { getHealth } from "@/lib/api-client"
import type { ApiFeatures } from "@/lib/types"

const DEFAULT_FEATURES: ApiFeatures = {
  streamAgentOutput: false,
  streamAgentTools: false,
}

export function useApiFeatures() {
  const [features, setFeatures] = useState<ApiFeatures>(DEFAULT_FEATURES)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const health = await getHealth()
        if (cancelled) return
        setFeatures({
          streamAgentOutput: Boolean(health.features?.stream_agent_output),
          streamAgentTools: Boolean(health.features?.stream_agent_tools),
        })
      } catch {
        if (!cancelled) setFeatures(DEFAULT_FEATURES)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return { features, loading }
}
