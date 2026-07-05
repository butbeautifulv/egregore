"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import { listCatalogEvaluations } from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"
import { DataTableShell } from "@/vendor/gui/layout/data-table-shell"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Alert, AlertDescription } from "@/vendor/gui/ui/alert"
import { Badge } from "@/vendor/gui/ui/badge"
import { Button } from "@/vendor/gui/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/vendor/gui/ui/table"

const LANGFUSE_HOST =
  process.env.NEXT_PUBLIC_LANGFUSE_HOST?.replace(/\/$/, "") ?? "http://localhost:3001"

export default function EvalRunsPage() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof listCatalogEvaluations>>["evaluations"]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await listCatalogEvaluations()
        if (!cancelled) {
          setRows(data.evaluations)
          setError(null)
        }
      } catch (exc) {
        if (!cancelled) {
          setError(formatApiError(exc, "Failed to load eval catalog"))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Eval runs"
        description="Catalog quality scores and Langfuse traces for offline eval suites."
        actions={
          <Button variant="outline" asChild>
            <Link href={LANGFUSE_HOST} target="_blank" rel="noreferrer">
              Open Langfuse
            </Link>
          </Button>
        }
      />

      <Alert>
        <AlertDescription>
          Local dry-run:{" "}
          <code className="text-xs">uv run python scripts/evals/egregore_eval.py --suite tiny --limit 1 --dry-run</code>
        </AlertDescription>
      </Alert>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {loading ? (
        <p className="text-muted-foreground text-sm">Loading eval catalog…</p>
      ) : rows.length === 0 && !error ? (
        <EmptyTableState
          title="No eval rows"
          description="Run catalog seed or an eval suite to populate persona quality."
        />
      ) : (
        <DataTableShell>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Persona</TableHead>
                <TableHead>Empirical trust</TableHead>
                <TableHead>Samples</TableHead>
                <TableHead>Declared</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.persona}>
                  <TableCell className="font-medium">{row.persona}</TableCell>
                  <TableCell className="tabular-nums">{(row.empirical_trust * 100).toFixed(0)}%</TableCell>
                  <TableCell className="tabular-nums">{row.sample_size}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{row.declared_trust_level}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTableShell>
      )}
    </div>
  )
}
