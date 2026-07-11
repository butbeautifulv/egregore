"use client"

import { Suspense, useMemo } from "react"
import { useSearchParams } from "next/navigation"

import { CatalogWorkspace } from "@/components/catalog-workspace"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { CatalogWorkspaceSkeleton } from "@/components/skeletons"

function parseCatalogTab(raw: string | null): "agents" | "skills" | "tools" | "plans" | "memory" {
  if (raw === "memory" || raw === "skills" || raw === "tools" || raw === "plans") {
    return raw
  }
  return "agents"
}

function CatalogHubContent() {
  const searchParams = useSearchParams()
  const initialTab = useMemo(() => parseCatalogTab(searchParams.get("tab")), [searchParams])
  const agentFilter = searchParams.get("agent")?.trim() || undefined

  return <CatalogWorkspace embedded initialTab={initialTab} agentFilter={agentFilter} />
}

export function CatalogHub() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Catalog"
        description="Agents, runtime assets, and tenant memory."
      />
      <Suspense fallback={<CatalogWorkspaceSkeleton />}>
        <CatalogHubContent />
      </Suspense>
    </div>
  )
}
