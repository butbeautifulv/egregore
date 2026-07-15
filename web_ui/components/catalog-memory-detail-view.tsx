"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import { listTenantMemory, type MemoryEntry } from "@/lib/api-client"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { FindingContent } from "@/components/engagement/finding-content"
import { usePlatformBreadcrumbLabel, usePlatformBreadcrumbMiddle } from "@/components/platform-breadcrumb"
import { EgregoreRouteSkeleton } from "@/components/skeletons"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Badge } from "@/vendor/gui/ui/badge"
import { Button } from "@/vendor/gui/ui/button"

export function CatalogMemoryDetailView({
  memoryId,
  agentHint,
}: {
  memoryId: string
  agentHint?: string
}) {
  const [entry, setEntry] = useState<MemoryEntry | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)

  usePlatformBreadcrumbMiddle([{ label: "Memory", href: "/catalog?tab=memory" }])
  usePlatformBreadcrumbLabel(entry?.memory_type ?? memoryId)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setEntry(null)
    ;(async () => {
      try {
        const response = await listTenantMemory({
          limit: 200,
          agent: agentHint || undefined,
        })
        if (cancelled) return
        const found = response.entries.find((item) => item.id === memoryId) ?? null
        if (!found && !agentHint) {
          const full = await listTenantMemory({ limit: 200 })
          if (cancelled) return
          setEntry(full.entries.find((item) => item.id === memoryId) ?? null)
        } else {
          setEntry(found)
        }
      } catch (exc) {
        if (!cancelled) setError(exc)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [memoryId, agentHint])

  if (loading) {
    return <EgregoreRouteSkeleton variant="catalog-memory" />
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Memory" backHref="/catalog?tab=memory" backLabel="Catalog memory" />
        <ApiErrorAlert error={error} fallback="Failed to load memory entry" />
      </div>
    )
  }

  if (!entry) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Memory" backHref="/catalog?tab=memory" backLabel="Catalog memory" />
        <ApiErrorAlert
          title="Entry not found"
          message="This memory entry is missing or outside the current fetch window."
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={entry.memory_type}
        description={entry.id}
        backHref="/catalog?tab=memory"
        backLabel="Catalog memory"
        actions={
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{entry.memory_type}</Badge>
            <Badge variant="secondary">{entry.source_agent}</Badge>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Button type="button" variant="outline" size="sm" asChild>
          <Link href={`/catalog/agents/${encodeURIComponent(entry.source_agent)}`}>Open agent</Link>
        </Button>
        {entry.investigation_id ? (
          <Button type="button" variant="ghost" size="sm" asChild>
            <Link href={`/work-orders/${entry.investigation_id}`}>{entry.investigation_id}</Link>
          </Button>
        ) : null}
        <span className="text-muted-foreground ml-auto text-xs">
          {new Date(entry.created_at).toLocaleString()}
        </span>
      </div>

      {entry.content_parsed ? (
        <FindingContent data={entry.content_parsed} />
      ) : (
        <pre className="bg-muted overflow-auto whitespace-pre-wrap rounded-md p-4 text-sm">
          {entry.content}
        </pre>
      )}
    </div>
  )
}
