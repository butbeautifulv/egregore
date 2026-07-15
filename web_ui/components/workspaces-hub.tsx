"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import {
  createWorkspace,
  listWorkspaces,
  type WorkspaceSummary,
} from "@/lib/api-client"
import { getSelectedTenantId } from "@/lib/workspace"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { Input } from "@/vendor/gui/ui/input"
import { PageHeader } from "@/vendor/gui/layout/page-header"

export function WorkspacesHub() {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [name, setName] = useState("")
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)

  async function reload() {
    setLoading(true)
    setError(null)
    try {
      const data = await listWorkspaces(getSelectedTenantId())
      setWorkspaces(data.workspaces)
    } catch (exc) {
      setError(exc)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void reload()
  }, [])

  async function onCreate() {
    if (!name.trim()) return
    setError(null)
    try {
      await createWorkspace({ name: name.trim(), tenant_id: getSelectedTenantId() })
      setName("")
      await reload()
    } catch (exc) {
      setError(exc)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Workspaces" description="Team sandboxes for custom worker personas" />
      {error ? <ApiErrorAlert error={error} fallback="Failed to load workspaces" /> : null}
      <Card>
        <CardHeader>
          <CardTitle>Create workspace</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Blue Team"
            className="max-w-sm"
          />
          <Button type="button" onClick={() => void onCreate()}>
            Create
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>My workspaces</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {loading ? <p className="text-muted-foreground text-sm">Loading…</p> : null}
          {!loading && workspaces.length === 0 ? (
            <p className="text-muted-foreground text-sm">No workspaces yet.</p>
          ) : null}
          {workspaces.map((ws) => (
            <Link
              key={ws.id}
              href={`/workspaces/${ws.id}`}
              className="hover:bg-muted rounded-md border px-3 py-2 text-sm"
            >
              <div className="font-medium">{ws.name}</div>
              <div className="text-muted-foreground text-xs">{ws.id}</div>
            </Link>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
