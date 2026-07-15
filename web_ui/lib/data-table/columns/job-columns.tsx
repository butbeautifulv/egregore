import type { ColumnDef } from "@tanstack/react-table"

import type { JobSummary } from "@/lib/types"
import { DataTableColumnHeader } from "@/vendor/gui/data-table/data-table-column-header"
import { Badge } from "@/vendor/gui/ui/badge"

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  const normalized = status.toLowerCase()
  if (normalized === "completed") return "default"
  if (normalized === "failed") return "destructive"
  if (normalized === "running" || normalized === "in_progress") return "secondary"
  return "outline"
}

export function createJobColumns(langfuseHost?: string): ColumnDef<JobSummary>[] {
  return [
    {
      accessorKey: "persona",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Persona" />,
      cell: ({ row }) => <Badge variant="outline">{row.original.persona}</Badge>,
    },
    {
      accessorKey: "status",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
      cell: ({ row }) => <Badge variant={statusVariant(row.original.status)}>{row.original.status}</Badge>,
    },
    {
      accessorKey: "job_id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Job" />,
      cell: ({ row }) => <code className="text-xs">{row.original.job_id}</code>,
    },
    {
      id: "trace",
      header: "Trace",
      cell: ({ row }) =>
        langfuseHost && row.original.session_id ? (
          <a
            href={`${langfuseHost}/project/default/sessions/${row.original.session_id}`}
            target="_blank"
            rel="noreferrer"
            className="text-primary text-xs hover:underline"
          >
            Langfuse
          </a>
        ) : (
          <span className="text-muted-foreground text-xs">—</span>
        ),
      enableSorting: false,
    },
  ]
}
