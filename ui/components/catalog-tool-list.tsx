"use client"

import type { CatalogTool } from "@/lib/api-client"
import { Badge } from "@/vendor/gui/ui/badge"
import { cn } from "@/vendor/gui/utils"

function riskBadgeVariant(tier?: string): "default" | "secondary" | "destructive" | "outline" {
  const normalized = tier?.toLowerCase()
  if (normalized === "high" || normalized === "critical") {
    return "destructive"
  }
  if (normalized === "medium") {
    return "secondary"
  }
  return "outline"
}

export function catalogToolMap(tools: CatalogTool[]): Map<string, CatalogTool> {
  return new Map(tools.map((tool) => [tool.tool_id, tool]))
}

function CatalogToolRow({
  toolId,
  tool,
  compact = false,
}: {
  toolId: string
  tool?: CatalogTool
  compact?: boolean
}) {
  const displayName = tool?.name?.trim() || toolId
  const description = tool?.description?.trim()

  return (
    <li className="rounded-md border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{displayName}</p>
          {displayName !== toolId ? (
            <code className="text-muted-foreground mt-0.5 block text-xs">{toolId}</code>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-1">
          {tool?.risk_tier ? (
            <Badge variant={riskBadgeVariant(tool.risk_tier)}>{tool.risk_tier}</Badge>
          ) : null}
          {tool?.enabled === false ? <Badge variant="outline">disabled</Badge> : null}
        </div>
      </div>
      {description ? (
        <p className={cn("text-muted-foreground mt-2 text-sm", compact && "line-clamp-2")}>
          {description}
        </p>
      ) : (
        <p className="text-muted-foreground mt-2 text-xs italic">No description in catalog.</p>
      )}
    </li>
  )
}

export function CatalogToolList({
  toolIds,
  toolById,
  compact = false,
  emptyTitle = "No tools attached.",
}: {
  toolIds: string[]
  toolById: Map<string, CatalogTool>
  compact?: boolean
  emptyTitle?: string
}) {
  if (toolIds.length === 0) {
    return <p className="text-muted-foreground text-sm">{emptyTitle}</p>
  }

  return (
    <ul className="flex flex-col gap-3">
      {toolIds.map((toolId) => (
        <CatalogToolRow key={toolId} toolId={toolId} tool={toolById.get(toolId)} compact={compact} />
      ))}
    </ul>
  )
}
