"use client"

import { useEffect, useState } from "react"

import { listInvestigations, type InvestigationSummary } from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"

import { ChatPanel } from "@/components/chat-panel"
import { InvestigationsTable } from "@/components/investigations-table"
import { RouteSkeleton } from "@/vendor/gui/shared/skeletons"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Alert, AlertDescription } from "@/vendor/gui/ui/alert"

export default function HomePage() {
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const response = await listInvestigations()
        if (cancelled) return
        setInvestigations(response.investigations)
        setError(null)
      } catch (exc) {
        if (cancelled) return
        setError(formatApiError(exc, "Failed to load investigations"))
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <RouteSkeleton variant="home" />
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Investigations" description="Start and track SOC investigations." />

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <ChatPanel />
      <InvestigationsTable investigations={investigations} />
    </div>
  )
}
