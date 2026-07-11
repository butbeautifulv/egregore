"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import {
  getCatalogAgent,
  getCatalogSkill,
  listCatalogTools,
  listTenantMemory,
  type CatalogAgentDetail,
  type CatalogSkill,
  type CatalogTool,
  type MemoryEntry,
} from "@/lib/api-client"
import { CatalogToolList, catalogToolMap } from "@/components/catalog-tool-list"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { MemoryEntriesList } from "@/components/memory-entries-list"
import { usePlatformBreadcrumbLabel } from "@/components/platform-breadcrumb"
import { EgregoreRouteSkeleton } from "@/components/skeletons"
import { Badge } from "@/vendor/gui/ui/badge"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Spinner } from "@/vendor/gui/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/vendor/gui/ui/tabs"

function SkillRow({ skillId }: { skillId: string }) {
  const [open, setOpen] = useState(false)
  const [skill, setSkill] = useState<CatalogSkill | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open || skill) return
    let cancelled = false
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const data = await getCatalogSkill(skillId)
        if (!cancelled) setSkill(data)
      } catch (exc) {
        if (!cancelled) setError(exc)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, skill, skillId])

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="hover:bg-muted flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm">
        <code className="text-xs">{skillId}</code>
        <span className="text-muted-foreground text-xs">{open ? "Hide" : "Show"}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 px-1">
        {loading ? <Spinner className="size-4" /> : null}
        {error ? <ApiErrorAlert error={error} fallback="Failed to load skill" /> : null}
        {skill ? (
          <div className="flex flex-col gap-2">
            {skill.name ? <p className="text-sm font-medium">{skill.name}</p> : null}
            {skill.description ? (
              <p className="text-muted-foreground text-xs">{skill.description}</p>
            ) : null}
            <pre className="bg-muted max-h-64 overflow-auto whitespace-pre-wrap rounded-md p-3 text-xs">
              {skill.body?.trim() || "No skill body."}
            </pre>
          </div>
        ) : null}
      </CollapsibleContent>
    </Collapsible>
  )
}

export function CatalogAgentDetailView({ agentName }: { agentName: string }) {
  const [agent, setAgent] = useState<CatalogAgentDetail | null>(null)
  const [toolById, setToolById] = useState<Map<string, CatalogTool>>(() => new Map())
  const [memory, setMemory] = useState<MemoryEntry[]>([])
  const [error, setError] = useState<unknown>(null)
  const [memoryError, setMemoryError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)

  usePlatformBreadcrumbLabel(agent?.name ?? agentName)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setMemoryError(null)
    setAgent(null)
    setToolById(new Map())
    setMemory([])
    ;(async () => {
      try {
        const [detail, mem, tools] = await Promise.all([
          getCatalogAgent(agentName),
          listTenantMemory({ agent: agentName, limit: 50 }),
          listCatalogTools(),
        ])
        if (cancelled) return
        setAgent(detail)
        setToolById(catalogToolMap(tools.tools))
        setMemory(mem.entries)
      } catch (exc) {
        if (cancelled) return
        setError(exc)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [agentName])

  async function reloadMemory() {
    setMemoryError(null)
    try {
      const mem = await listTenantMemory({ agent: agentName, limit: 50 })
      setMemory(mem.entries)
    } catch (exc) {
      setMemoryError(exc)
    }
  }

  if (loading) {
    return <EgregoreRouteSkeleton variant="catalog-agent" />
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title={agentName} backHref="/catalog" backLabel="Catalog" />
        <ApiErrorAlert error={error} fallback="Failed to load agent" />
      </div>
    )
  }

  if (!agent) {
    return null
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={agent.name}
        description={agent.role ? `${agent.role} · runtime agent` : "Runtime agent"}
        backHref="/catalog"
        backLabel="Catalog"
        actions={
          <div className="flex flex-wrap gap-2">
            <Badge variant={agent.enabled ? "default" : "outline"}>
              {agent.enabled ? "enabled" : "disabled"}
            </Badge>
            {agent.empirical_trust != null ? (
              <Badge variant="secondary">trust {(agent.empirical_trust * 100).toFixed(0)}%</Badge>
            ) : null}
            {agent.version_tag ? <Badge variant="outline">{agent.version_tag}</Badge> : null}
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div>
              <span className="text-muted-foreground">Role: </span>
              {agent.role || "—"}
            </div>
            <div>
              <span className="text-muted-foreground">Skills: </span>
              {(agent.skills ?? []).length}
            </div>
            <div>
              <span className="text-muted-foreground">Tools: </span>
              {(agent.tools ?? []).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Memory</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => void reloadMemory()}>
              Reload
            </Button>
            <Button type="button" size="sm" variant="ghost" asChild>
              <Link href={`/catalog?tab=memory&agent=${encodeURIComponent(agent.name)}`}>
                View all in Catalog
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="prompt">
        <TabsList variant="line">
          <TabsTrigger value="prompt">Prompt</TabsTrigger>
          <TabsTrigger value="skills">Skills</TabsTrigger>
          <TabsTrigger value="tools">Tools</TabsTrigger>
          <TabsTrigger value="memory">Memory</TabsTrigger>
        </TabsList>

        <TabsContent value="prompt" className="mt-4">
          <pre className="bg-muted max-h-[min(60vh,480px)] overflow-auto whitespace-pre-wrap rounded-md p-3 text-xs">
            {agent.system_prompt?.trim() || "No system prompt stored."}
          </pre>
        </TabsContent>

        <TabsContent value="skills" className="mt-4">
          {(agent.skills ?? []).length === 0 ? (
            <p className="text-muted-foreground text-sm">No skills attached.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {(agent.skills ?? []).map((skillId) => (
                <SkillRow key={skillId} skillId={skillId} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="tools" className="mt-4">
          <CatalogToolList toolIds={agent.tools ?? []} toolById={toolById} />
        </TabsContent>

        <TabsContent value="memory" className="mt-4">
          {memoryError ? (
            <ApiErrorAlert
              error={memoryError}
              fallback="Failed to load memory"
              onRetry={() => void reloadMemory()}
            />
          ) : null}
          <MemoryEntriesList
            entries={memory}
            emptyTitle="No memory for this agent"
            emptyDescription="Tenant memory filtered by source_agent is empty."
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
