"use client"

import { useEffect, useState } from "react"

import { listWorkspaces, type WorkspaceSummary } from "@/lib/api-client"
import {
  getSelectedTenantId,
  getSelectedWorkspaceId,
  setSelectedWorkspaceId,
} from "@/lib/workspace"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/vendor/gui/ui/select"

export function WorkspacePicker() {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [selected, setSelected] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const tenantId = getSelectedTenantId()
    setSelected(getSelectedWorkspaceId())
    void listWorkspaces(tenantId)
      .then((data) => {
        if (cancelled) {
          return
        }
        setWorkspaces(data.workspaces)
        const current = getSelectedWorkspaceId()
        if (!current && data.workspaces.length > 0) {
          const defaultWs =
            data.workspaces.find((ws) => ws.id.endsWith("-default")) ?? data.workspaces[0]
          setSelected(defaultWs.id)
          setSelectedWorkspaceId(defaultWs.id)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setWorkspaces([])
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading && workspaces.length === 0) {
    return null
  }

  if (workspaces.length === 0) {
    return null
  }

  return (
    <div className="px-2 py-2">
      <p className="text-muted-foreground mb-1 px-1 text-xs font-medium">Workspace</p>
      <Select
        value={selected || workspaces[0]?.id}
        onValueChange={(value) => {
          setSelected(value)
          setSelectedWorkspaceId(value)
        }}
      >
        <SelectTrigger className="h-8 w-full text-xs">
          <SelectValue placeholder="Select workspace" />
        </SelectTrigger>
        <SelectContent>
          {workspaces.map((ws) => (
            <SelectItem key={ws.id} value={ws.id}>
              {ws.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
