"use client"

import { useEffect, useState } from "react"

import { listCatalogAgents } from "@/lib/api-client"
import { buildAutoApprovePersonaSet } from "@/lib/hitl-auto-approve"

export function useHitlAutoApproveCatalog() {
  const [autoApprovePersonas, setAutoApprovePersonas] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const response = await listCatalogAgents()
        if (cancelled) return
        setAutoApprovePersonas(buildAutoApprovePersonaSet(response.agents))
      } catch {
        if (!cancelled) setAutoApprovePersonas(new Set())
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return { autoApprovePersonas, loading }
}
