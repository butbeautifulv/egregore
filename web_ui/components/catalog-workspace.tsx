"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import type { ColumnDef } from "@tanstack/react-table"

import {
  listCatalogAgents,
  listCatalogPlans,
  listCatalogSkills,
  listCatalogTools,
  reloadCatalog,
  type CatalogAgent,
  type CatalogPlan,
  type CatalogSkill,
  type CatalogTool,
} from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"
import {
  createCatalogAgentColumns,
  createCatalogPlanColumns,
  createCatalogSkillColumns,
  createCatalogToolColumns,
} from "@/lib/data-table/columns/catalog-columns"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { CatalogMemoryFeed } from "@/components/catalog-memory-feed"
import { useApiQuery } from "@/hooks/use-api-query"
import { CatalogWorkspaceSkeleton, MemoryFeedSkeleton } from "@/components/skeletons"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { DataTable } from "@/vendor/gui/data-table/data-table"
import { Button } from "@/vendor/gui/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/vendor/gui/ui/tabs"
import { Spinner } from "@/vendor/gui/ui/spinner"

type CatalogKind = "agents" | "skills" | "tools" | "plans" | "memory"
type CatalogTableKind = Exclude<CatalogKind, "memory">

type CatalogBundle = {
  agents: CatalogAgent[]
  skills: CatalogSkill[]
  tools: CatalogTool[]
  plans: CatalogPlan[]
}

const TABLE_KINDS: CatalogTableKind[] = ["agents", "tools", "skills", "plans"]

export function CatalogWorkspace({
  embedded = false,
  initialTab = "agents",
  agentFilter,
}: {
  embedded?: boolean
  initialTab?: CatalogKind
  agentFilter?: string
}) {
  const router = useRouter()
  const [kind, setKind] = useState<CatalogKind>(initialTab)
  const [reloading, setReloading] = useState(false)
  const [actionError, setActionError] = useState<unknown>(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncs the active tab when the URL's ?tab= changes externally (e.g. browser back/forward)
    setKind(initialTab)
  }, [initialTab])

  const fetcher = useCallback(async (): Promise<CatalogBundle> => {
    const [agentRes, skillRes, toolRes, planRes] = await Promise.all([
      listCatalogAgents(),
      listCatalogSkills(),
      listCatalogTools(),
      listCatalogPlans(),
    ])
    return {
      agents: agentRes.agents,
      skills: skillRes.skills,
      tools: toolRes.tools,
      plans: planRes.plans,
    }
  }, [])

  const { data, rawError, loading, refresh, isStale } = useApiQuery(fetcher, [], {
    fallback: "Failed to load catalog",
    enabled: kind !== "memory",
  })

  function onTabChange(next: string) {
    const tab = next as CatalogKind
    setKind(tab)
    const params = new URLSearchParams()
    if (tab !== "agents") {
      params.set("tab", tab)
    }
    if (tab === "memory" && agentFilter) {
      params.set("agent", agentFilter)
    }
    const qs = params.toString()
    router.replace(qs ? `/catalog?${qs}` : "/catalog", { scroll: false })
  }

  async function onReload() {
    setReloading(true)
    setActionError(null)
    try {
      await reloadCatalog()
      await refresh()
    } catch (exc) {
      setActionError(exc)
    } finally {
      setReloading(false)
    }
  }

  const columnMap = useMemo(
    (): Record<CatalogTableKind, ColumnDef<unknown>[]> => ({
      agents: createCatalogAgentColumns() as ColumnDef<unknown>[],
      skills: createCatalogSkillColumns() as ColumnDef<unknown>[],
      tools: createCatalogToolColumns() as ColumnDef<unknown>[],
      plans: createCatalogPlanColumns() as ColumnDef<unknown>[],
    }),
    [],
  )

  const displayError = actionError ?? rawError

  if (loading && !data && kind !== "memory") {
    return <CatalogWorkspaceSkeleton />
  }

  return (
    <div className="flex flex-col gap-6">
      {!embedded ? (
        <PageHeader
          title="Runtime catalog"
          description="Agents, tools, skills, plans, and tenant memory."
          actions={
            kind !== "memory" ? (
              <Button type="button" variant="outline" disabled={reloading} onClick={() => void onReload()}>
                {reloading ? <Spinner data-icon="inline-start" /> : null}
                Reload catalog
              </Button>
            ) : undefined
          }
        />
      ) : kind !== "memory" ? (
        <div className="flex justify-end">
          <Button type="button" variant="outline" size="sm" disabled={reloading} onClick={() => void onReload()}>
            {reloading ? <Spinner data-icon="inline-start" /> : null}
            Reload catalog
          </Button>
        </div>
      ) : null}

      {displayError && kind !== "memory" ? (
        <ApiErrorAlert
          error={displayError}
          fallback={formatApiError(displayError, "Failed to load catalog")}
          onRetry={() => {
            setActionError(null)
            void refresh()
          }}
          isStale={isStale}
        />
      ) : null}

      <Tabs value={kind} onValueChange={onTabChange}>
        <TabsList>
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="tools">Tools</TabsTrigger>
          <TabsTrigger value="skills">Skills</TabsTrigger>
          <TabsTrigger value="plans">Plans</TabsTrigger>
          <TabsTrigger value="memory">Memory</TabsTrigger>
        </TabsList>
        <TabsContent value="memory" className="mt-4">
          <Suspense fallback={<MemoryFeedSkeleton />}>
            <CatalogMemoryFeed />
          </Suspense>
        </TabsContent>
        {TABLE_KINDS.map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-4">
            <DataTable
              columns={columnMap[tab]}
              data={data?.[tab] ?? []}
              searchPlaceholder="Search catalog…"
              pageSize={20}
              onRowClick={
                tab === "agents"
                  ? (row) => router.push(`/catalog/agents/${encodeURIComponent((row as CatalogAgent).name)}`)
                  : undefined
              }
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
