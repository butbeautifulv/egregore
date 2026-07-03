"use client"

import { useMemo, useState } from "react"
import Link from "next/link"

import type { InvestigationSummary } from "@/lib/types"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { DataTableShell } from "@/vendor/gui/layout/data-table-shell"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { Badge } from "@/vendor/gui/ui/badge"
import { Input } from "@/vendor/gui/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/vendor/gui/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/vendor/gui/ui/table"

export function InvestigationsTable({ investigations }: { investigations: InvestigationSummary[] }) {
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")

  const statuses = useMemo(
    () => [...new Set(investigations.map((item) => item.status).filter(Boolean))],
    [investigations],
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return investigations.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) {
        return false
      }
      if (!needle) {
        return true
      }
      return (
        item.investigation_id.toLowerCase().includes(needle) ||
        (item.goal ?? "").toLowerCase().includes(needle)
      )
    })
  }, [investigations, query, statusFilter])

  if (investigations.length === 0) {
    return (
      <EmptyTableState
        title="No investigations yet"
        description="Start a new investigation below to populate this list."
      />
    )
  }

  return (
    <DataTableShell
      toolbar={
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by id or goal…"
            className="max-w-lg"
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-44">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {statuses.map((status) => (
                <SelectItem key={status} value={status}>
                  {status}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      }
    >
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
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground text-center text-xs">
                  No investigations match your filters.
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((item) => (
                <TableRow key={item.investigation_id}>
                  <TableCell className="max-w-[12rem]">
                    <Link
                      href={`/investigations/${item.investigation_id}`}
                      className="text-primary font-medium hover:underline"
                    >
                      <OverflowText>{item.investigation_id}</OverflowText>
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{item.status}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground max-w-[10rem]">
                    <OverflowText>
                      {item.completed_personas.length > 0 ? item.completed_personas.join(", ") : "—"}
                    </OverflowText>
                  </TableCell>
                  <TableCell className="max-w-md">
                    <OverflowText>{item.goal || "—"}</OverflowText>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
    </DataTableShell>
  )
}
