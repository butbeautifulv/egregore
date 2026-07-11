"use client"

import { useCallback, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"

import { listTenantMemory, type MemoryEntry } from "@/lib/api-client"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { MemoryEntriesList } from "@/components/memory-entries-list"
import { useApiQuery } from "@/hooks/use-api-query"
import { MemoryFeedSkeleton } from "@/components/skeletons"
import { Input } from "@/vendor/gui/ui/input"
import { Label } from "@/vendor/gui/ui/label"

export function CatalogMemoryFeed() {
  const searchParams = useSearchParams()
  const agentFromUrl = searchParams.get("agent")?.trim() || ""
  const [typeFilter, setTypeFilter] = useState("")
  const [search, setSearch] = useState("")

  const fetcher = useCallback(async () => {
    const response = await listTenantMemory({
      limit: 200,
      agent: agentFromUrl || undefined,
    })
    return response.entries
  }, [agentFromUrl])

  const { data, error, loading, refresh, isStale } = useApiQuery(fetcher, [agentFromUrl], {
    fallback: "Failed to load memory",
  })

  const filtered = useMemo(() => {
    const entries = data ?? []
    const query = search.trim().toLowerCase()
    const type = typeFilter.trim().toLowerCase()
    return entries.filter((entry) => {
      if (type && entry.memory_type.toLowerCase() !== type) {
        return false
      }
      if (!query) {
        return true
      }
      return (
        entry.source_agent.toLowerCase().includes(query) ||
        entry.memory_type.toLowerCase().includes(query) ||
        entry.investigation_id.toLowerCase().includes(query) ||
        entry.content.toLowerCase().includes(query)
      )
    })
  }, [data, search, typeFilter])

  const memoryTypes = useMemo(() => {
    const types = new Set((data ?? []).map((entry) => entry.memory_type))
    return [...types].sort()
  }, [data])

  if (loading && !data) {
    return <MemoryFeedSkeleton />
  }

  return (
    <div className="flex flex-col gap-4">
      {agentFromUrl ? (
        <p className="text-muted-foreground text-sm">
          Filtered by agent <span className="font-medium">{agentFromUrl}</span>.
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:max-w-2xl">
        <div className="flex flex-col gap-2">
          <Label htmlFor="memory-search">Search</Label>
          <Input
            id="memory-search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Agent, type, work order, content…"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="memory-type">Type</Label>
          <Input
            id="memory-type"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
            placeholder={memoryTypes[0] ? `e.g. ${memoryTypes[0]}` : "memory type"}
            list="memory-type-options"
          />
          <datalist id="memory-type-options">
            {memoryTypes.map((type) => (
              <option key={type} value={type} />
            ))}
          </datalist>
        </div>
      </div>

      {error ? (
        <ApiErrorAlert
          error={error}
          fallback="Failed to load memory"
          onRetry={() => void refresh()}
          isStale={isStale}
        />
      ) : null}

      <MemoryEntriesList
        entries={filtered}
        variant="feed"
        linkAgents
        emptyTitle={agentFromUrl ? "No memory for this agent" : "No memory entries"}
        emptyDescription="Tenant episodic memory will appear here when agents store findings."
      />
    </div>
  )
}
