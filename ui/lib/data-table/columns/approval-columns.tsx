import type { ColumnDef } from "@tanstack/react-table"

import type { PendingApproval } from "@/lib/types"
import { ApprovalActions } from "@/components/approval-actions"
import { DataTableColumnHeader } from "@/vendor/gui/data-table/data-table-column-header"
import { FACETED_COLUMN_META, facetedFilter } from "@/vendor/gui/lib/data-table/faceted-column"
import { Badge } from "@/vendor/gui/ui/badge"

function riskVariant(risk: string): "default" | "secondary" | "destructive" | "outline" {
  const level = risk.toLowerCase()
  if (level.includes("high") || level.includes("critical")) return "destructive"
  if (level.includes("medium")) return "secondary"
  return "outline"
}

export function createApprovalColumns(): ColumnDef<PendingApproval>[] {
  return [
    {
      accessorKey: "persona",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Persona" />,
      cell: ({ row }) => <Badge variant="outline">{row.original.persona}</Badge>,
    },
    {
      accessorKey: "tool_name",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Tool" />,
      cell: ({ row }) => <span className="font-medium">{row.original.tool_name}</span>,
    },
    {
      accessorKey: "risk_level",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Risk" />,
      cell: ({ row }) => <Badge variant={riskVariant(row.original.risk_level)}>{row.original.risk_level}</Badge>,
      filterFn: facetedFilter,
      meta: { ...FACETED_COLUMN_META, title: "Risk" },
    },
    {
      accessorKey: "job_id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Job" />,
      cell: ({ row }) => <code className="text-xs">{row.original.job_id}</code>,
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => <ApprovalActions approval={row.original} compact />,
      enableSorting: false,
      meta: { role: "actions" },
    },
  ]
}
