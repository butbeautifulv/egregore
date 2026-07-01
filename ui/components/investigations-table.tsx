import Link from "next/link"

import type { InvestigationSummary } from "@/lib/types"
import { Badge } from "@/vendor/gui/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/vendor/gui/ui/table"

export function InvestigationsTable({ investigations }: { investigations: InvestigationSummary[] }) {
  if (investigations.length === 0) {
    return <p className="text-muted-foreground text-xs">No investigations yet. Start one below.</p>
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Investigation</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Personas</TableHead>
          <TableHead>Goal</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {investigations.map((item) => (
          <TableRow key={item.investigation_id}>
            <TableCell>
              <Link
                href={`/investigations/${item.investigation_id}`}
                className="text-primary font-medium hover:underline"
              >
                {item.investigation_id}
              </Link>
            </TableCell>
            <TableCell>
              <Badge variant="outline">{item.status}</Badge>
            </TableCell>
            <TableCell className="text-muted-foreground">
              {item.completed_personas.length > 0 ? item.completed_personas.join(", ") : "—"}
            </TableCell>
            <TableCell className="max-w-md truncate">{item.goal || "—"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
