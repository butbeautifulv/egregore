"use client"

import { useMemo, useState } from "react"
import { toast } from "sonner"

import {
  forkWorkspaceAgent,
  grantWorkspaceDatasource,
  inviteWorkspaceMember,
  listWorkspaceAgents,
  revokeWorkspaceDatasource,
  updateWorkspaceAgent,
  type WorkspaceAgentSummary,
} from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"
import { usePlatformBreadcrumbLabel } from "@/components/platform-breadcrumb"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { useApiQuery } from "@/hooks/use-api-query"
import {
  createWorkspaceAgentColumns,
  workspaceAgentGlobalFilter,
} from "@/lib/data-table/columns/workspace-columns"
import { EgregoreRouteSkeleton } from "@/components/skeletons"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { DataTable } from "@/vendor/gui/data-table/data-table"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { Input } from "@/vendor/gui/ui/input"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/vendor/gui/ui/select"
import { Spinner } from "@/vendor/gui/ui/spinner"
import { Textarea } from "@/vendor/gui/ui/textarea"

const DATASOURCES = ["siem-readonly", "veil-knowledge", "nessus"]
const FORKABLE = ["soc", "intel", "consultant"]

export function WorkspaceSettingsView({ workspaceId }: { workspaceId: string }) {
  usePlatformBreadcrumbLabel(workspaceId)

  const {
    data: agents,
    error,
    rawError,
    loading,
    refresh,
    isStale,
    setData: setAgents,
  } = useApiQuery(
    async () => (await listWorkspaceAgents(workspaceId)).agents,
    [workspaceId],
    { fallback: "Failed to load workspace agents" },
  )

  const [inviteUser, setInviteUser] = useState("")
  const [inviteRole, setInviteRole] = useState<"editor" | "viewer">("viewer")
  const [inviting, setInviting] = useState(false)

  const [pendingGrant, setPendingGrant] = useState<string | null>(null)

  const [forking, setForking] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState("")
  const [personaPrompt, setPersonaPrompt] = useState("")
  const [saving, setSaving] = useState(false)

  const columns = useMemo(() => createWorkspaceAgentColumns(), [])

  function selectAgent(agent: WorkspaceAgentSummary) {
    setSelectedAgent(agent.name)
    setPersonaPrompt(agent.persona_prompt ?? "")
  }

  async function onInvite() {
    const userId = inviteUser.trim()
    if (!userId || inviting) return
    setInviting(true)
    try {
      await inviteWorkspaceMember(workspaceId, { user_id: userId, role: inviteRole })
      toast.success(`Invited ${userId} as ${inviteRole}`)
      setInviteUser("")
    } catch (exc) {
      toast.error("Could not invite member", { description: formatApiError(exc, "Request failed") })
    } finally {
      setInviting(false)
    }
  }

  async function onGrant(datasourceId: string, action: "grant" | "revoke") {
    setPendingGrant(datasourceId)
    try {
      if (action === "grant") {
        await grantWorkspaceDatasource(workspaceId, datasourceId)
        toast.success(`Granted ${datasourceId}`)
      } else {
        await revokeWorkspaceDatasource(workspaceId, datasourceId)
        toast.success(`Revoked ${datasourceId}`)
      }
    } catch (exc) {
      toast.error(`Could not ${action} ${datasourceId}`, { description: formatApiError(exc, "Request failed") })
    } finally {
      setPendingGrant(null)
    }
  }

  async function onFork(name: string) {
    setForking(name)
    try {
      const agent = await forkWorkspaceAgent(workspaceId, name)
      toast.success(`Forked ${name}`)
      setAgents((prev) => [...(prev ?? []).filter((item) => item.name !== agent.name), agent])
      selectAgent(agent)
    } catch (exc) {
      toast.error(`Could not fork ${name}`, { description: formatApiError(exc, "Request failed") })
    } finally {
      setForking(null)
    }
  }

  async function onSavePersona() {
    if (!selectedAgent || saving) return
    setSaving(true)
    try {
      const agent = await updateWorkspaceAgent(workspaceId, selectedAgent, { persona_prompt: personaPrompt })
      toast.success("Persona saved")
      setAgents((prev) => (prev ?? []).map((item) => (item.name === agent.name ? agent : item)))
    } catch (exc) {
      toast.error("Could not save persona", { description: formatApiError(exc, "Request failed") })
    } finally {
      setSaving(false)
    }
  }

  if (loading && !agents) {
    return <EgregoreRouteSkeleton variant="workspace" />
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={workspaceId}
        description="Workspace settings"
        backHref="/workspaces"
        backLabel="Workspaces"
      />

      {error ? (
        <ApiErrorAlert error={rawError} fallback={error} onRetry={() => void refresh()} isStale={isStale} />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Invite member</CardTitle>
            <CardDescription>Grant a teammate editor or viewer access.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Input
              value={inviteUser}
              onChange={(event) => setInviteUser(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void onInvite()
              }}
              placeholder="user id"
              className="max-w-xs"
              disabled={inviting}
            />
            <Select value={inviteRole} onValueChange={(value) => setInviteRole(value as "editor" | "viewer")}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="editor">editor</SelectItem>
                <SelectItem value="viewer">viewer</SelectItem>
              </SelectContent>
            </Select>
            <Button type="button" onClick={() => void onInvite()} disabled={inviting || !inviteUser.trim()}>
              {inviting ? <Spinner data-icon="inline-start" /> : null}
              Invite
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Datasource grants</CardTitle>
            <CardDescription>Allow this workspace&apos;s agents to query a datasource.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {DATASOURCES.map((ds) => (
              <div key={ds} className="flex items-center gap-1">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={pendingGrant === ds}
                  onClick={() => void onGrant(ds, "grant")}
                >
                  {pendingGrant === ds ? <Spinner data-icon="inline-start" /> : null}
                  Grant {ds}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={pendingGrant === ds}
                  onClick={() => void onGrant(ds, "revoke")}
                >
                  Revoke
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Workspace agents</CardTitle>
          <CardDescription>
            Fork a control worker into this workspace, then customize its persona.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {FORKABLE.map((name) => (
              <Button
                key={name}
                type="button"
                size="sm"
                variant="outline"
                disabled={forking === name}
                onClick={() => void onFork(name)}
              >
                {forking === name ? <Spinner data-icon="inline-start" /> : null}
                Fork {name}
              </Button>
            ))}
          </div>

          {agents && agents.length === 0 ? (
            <EmptyTableState
              title="No workspace agents yet"
              description="Fork a worker above to customize persona prompts."
            />
          ) : (
            <DataTable
              columns={columns}
              data={agents ?? []}
              searchPlaceholder="Search agents…"
              globalFilterFn={workspaceAgentGlobalFilter}
              pageSize={10}
              onRowClick={selectAgent}
              getRowClassName={(row) => (row.name === selectedAgent ? "bg-muted/50" : undefined)}
            />
          )}

          {selectedAgent ? (
            <div className="flex flex-col gap-2 border-t pt-4">
              <p className="text-sm font-medium">
                Persona — <span className="text-muted-foreground font-normal">{selectedAgent}</span>
              </p>
              <Textarea
                value={personaPrompt}
                onChange={(event) => setPersonaPrompt(event.target.value)}
                rows={8}
                placeholder="Persona body (immutable backend rules are assembled server-side)"
                disabled={saving}
              />
              <div>
                <Button type="button" onClick={() => void onSavePersona()} disabled={saving}>
                  {saving ? <Spinner data-icon="inline-start" /> : null}
                  Save persona
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
