import type { ColumnDef } from "@tanstack/react-table"

import type { CatalogAgent, CatalogPlan, CatalogSkill, CatalogTool } from "@/lib/api-client"
import { DataTableColumnHeader } from "@/vendor/gui/data-table/data-table-column-header"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { Badge } from "@/vendor/gui/ui/badge"

export function createCatalogAgentColumns(): ColumnDef<CatalogAgent>[] {
  return [
    {
      accessorKey: "name",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Agent" />,
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
    },
    {
      accessorKey: "role",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Role" />,
    },
    {
      accessorKey: "enabled",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Enabled" />,
      cell: ({ row }) => (
        <Badge variant={row.original.enabled ? "default" : "outline"}>
          {row.original.enabled ? "yes" : "no"}
        </Badge>
      ),
    },
    {
      accessorKey: "empirical_trust",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Trust" />,
      cell: ({ row }) =>
        row.original.empirical_trust != null ? row.original.empirical_trust.toFixed(2) : "—",
    },
  ]
}

export function createCatalogSkillColumns(): ColumnDef<CatalogSkill>[] {
  return [
    {
      accessorKey: "skill_id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Skill" />,
      cell: ({ row }) => <code className="text-xs">{row.original.skill_id}</code>,
    },
    {
      accessorKey: "name",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Name" />,
    },
    {
      accessorKey: "approval_status",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Approval" />,
      cell: ({ row }) => <Badge variant="outline">{row.original.approval_status ?? "—"}</Badge>,
    },
  ]
}

export function createCatalogToolColumns(): ColumnDef<CatalogTool>[] {
  return [
    {
      accessorKey: "tool_id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Tool" />,
      cell: ({ row }) => <code className="text-xs">{row.original.tool_id}</code>,
    },
    {
      accessorKey: "name",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Name" />,
    },
    {
      accessorKey: "description",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Description" />,
      cell: ({ row }) => (
        <OverflowText className="text-muted-foreground max-w-md">
          {row.original.description?.trim() || "—"}
        </OverflowText>
      ),
    },
    {
      accessorKey: "risk_tier",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Risk" />,
      cell: ({ row }) => <Badge variant="outline">{row.original.risk_tier ?? "—"}</Badge>,
    },
  ]
}

export function createCatalogPlanColumns(): ColumnDef<CatalogPlan>[] {
  return [
    {
      accessorKey: "plan_id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Plan" />,
      cell: ({ row }) => <code className="text-xs">{row.original.plan_id}</code>,
    },
    {
      accessorKey: "name",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Name" />,
    },
    {
      id: "personas",
      accessorFn: (row) => (row.personas ?? []).join(", "),
      header: ({ column }) => <DataTableColumnHeader column={column} title="Personas" />,
    },
    {
      accessorKey: "active",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Active" />,
      cell: ({ row }) => (
        <Badge variant={row.original.active ? "default" : "outline"}>
          {row.original.active ? "yes" : "no"}
        </Badge>
      ),
    },
  ]
}
