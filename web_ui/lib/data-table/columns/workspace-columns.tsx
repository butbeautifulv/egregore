import type { ColumnDef } from "@tanstack/react-table"

import type { WorkspaceAgentSummary, WorkspaceSummary } from "@/lib/api-client"
import { DataTableColumnHeader } from "@/vendor/gui/data-table/data-table-column-header"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { Badge } from "@/vendor/gui/ui/badge"

export function createWorkspaceColumns(): ColumnDef<WorkspaceSummary>[] {
  return [
    {
      accessorKey: "name",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Name" />,
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
    },
    {
      accessorKey: "id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="ID" />,
      cell: ({ row }) => <code className="text-muted-foreground text-xs">{row.original.id}</code>,
    },
    {
      accessorKey: "profile_id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Profile" />,
      cell: ({ row }) => <Badge variant="outline">{row.original.profile_id ?? "—"}</Badge>,
    },
  ]
}

export function workspaceGlobalFilter(row: WorkspaceSummary, _columnId: string, filterValue: string) {
  const needle = filterValue.trim().toLowerCase()
  if (!needle) return true
  return row.name.toLowerCase().includes(needle) || row.id.toLowerCase().includes(needle)
}

export function createWorkspaceAgentColumns(): ColumnDef<WorkspaceAgentSummary>[] {
  return [
    {
      accessorKey: "name",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Agent" />,
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
    },
    {
      accessorKey: "source_agent",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Source" />,
      cell: ({ row }) => <Badge variant="outline">{row.original.source_agent}</Badge>,
    },
    {
      id: "tools",
      accessorFn: (row) => (row.tools ?? []).length,
      header: ({ column }) => <DataTableColumnHeader column={column} title="Tools" />,
      cell: ({ row }) => (
        <span className="text-muted-foreground text-xs tabular-nums">{(row.original.tools ?? []).length}</span>
      ),
    },
    {
      id: "skills",
      accessorFn: (row) => (row.skills ?? []).length,
      header: ({ column }) => <DataTableColumnHeader column={column} title="Skills" />,
      cell: ({ row }) => (
        <span className="text-muted-foreground text-xs tabular-nums">{(row.original.skills ?? []).length}</span>
      ),
    },
    {
      accessorKey: "persona_prompt",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Persona preview" />,
      cell: ({ row }) => (
        <OverflowText className="text-muted-foreground max-w-md">
          {row.original.persona_prompt?.trim() || "—"}
        </OverflowText>
      ),
      enableSorting: false,
    },
  ]
}

export function workspaceAgentGlobalFilter(
  row: WorkspaceAgentSummary,
  _columnId: string,
  filterValue: string,
) {
  const needle = filterValue.trim().toLowerCase()
  if (!needle) return true
  return (
    row.name.toLowerCase().includes(needle) ||
    row.source_agent.toLowerCase().includes(needle)
  )
}
