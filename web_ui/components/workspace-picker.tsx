"use client"

import { useEffect, useState } from "react"

import { useWorkspaces } from "@/hooks/use-workspaces"
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
  const tenantId = getSelectedTenantId()
  const { workspaces, loading } = useWorkspaces(tenantId)
  const [selected, setSelected] = useState(() => getSelectedWorkspaceId())

  useEffect(() => {
    if (!workspaces || workspaces.length === 0 || getSelectedWorkspaceId()) return
    const defaultWs = workspaces.find((ws) => ws.id.endsWith("-default")) ?? workspaces[0]
    setSelectedWorkspaceId(defaultWs.id)
    // eslint-disable-next-line react-hooks/set-state-in-effect -- picks + persists a default workspace once the list loads, mirrors localStorage
    setSelected(defaultWs.id)
  }, [workspaces])

  if (loading && !workspaces) {
    return null
  }

  if (!workspaces || workspaces.length === 0) {
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
