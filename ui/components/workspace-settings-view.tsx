"use client"

import { useEffect, useState } from "react"

import {
  forkWorkspaceAgent,
  grantWorkspaceDatasource,
  inviteWorkspaceMember,
  listWorkspaceAgents,
  revokeWorkspaceDatasource,
  updateWorkspaceAgent,
  type WorkspaceAgentSummary,
} from "@/lib/api-client"
import { usePlatformBreadcrumbLabel } from "@/components/platform-breadcrumb"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { Input } from "@/vendor/gui/ui/input"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/vendor/gui/ui/select"
import { Textarea } from "@/vendor/gui/ui/textarea"

const DATASOURCES = ["siem-readonly", "veil-knowledge", "nessus"]
const FORKABLE = ["soc", "intel", "consultant"]

export function WorkspaceSettingsView({ workspaceId }: { workspaceId: string }) {
  const [agents, setAgents] = useState<WorkspaceAgentSummary[]>([])
  const [error, setError] = useState<unknown>(null)
  const [inviteUser, setInviteUser] = useState("")
  const [inviteRole, setInviteRole] = useState<"editor" | "viewer">("viewer")
  const [selectedAgent, setSelectedAgent] = useState("")
  const [personaPrompt, setPersonaPrompt] = useState("")

  usePlatformBreadcrumbLabel(workspaceId)

  async function reloadAgents() {
    setError(null)
    try {
      const data = await listWorkspaceAgents(workspaceId)
      setAgents(data.agents)
      if (!selectedAgent && data.agents[0]) {
        setSelectedAgent(data.agents[0].name)
        setPersonaPrompt(data.agents[0].persona_prompt ?? "")
      }
    } catch (exc) {
      setError(exc)
    }
  }

  useEffect(() => {
    void reloadAgents()
  }, [workspaceId])

  useEffect(() => {
    const agent = agents.find((item) => item.name === selectedAgent)
    setPersonaPrompt(agent?.persona_prompt ?? "")
  }, [selectedAgent, agents])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={workspaceId} description="Workspace settings" backHref="/workspaces" backLabel="Workspaces" />
      {error ? <ApiErrorAlert error={error} fallback="Workspace action failed" /> : null}

      <Card>
        <CardHeader>
          <CardTitle>Invite member</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Input
            value={inviteUser}
            onChange={(event) => setInviteUser(event.target.value)}
            placeholder="user id"
            className="max-w-xs"
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
          <Button
            type="button"
            onClick={() =>
              void inviteWorkspaceMember(workspaceId, { user_id: inviteUser, role: inviteRole }).then(() =>
                setInviteUser(""),
              )
            }
          >
            Invite
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Datasource grants</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {DATASOURCES.map((ds) => (
            <div key={ds} className="flex gap-2">
              <Button type="button" size="sm" variant="outline" onClick={() => void grantWorkspaceDatasource(workspaceId, ds)}>
                Grant {ds}
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => void revokeWorkspaceDatasource(workspaceId, ds)}>
                Revoke
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Workspace agents</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {FORKABLE.map((name) => (
              <Button key={name} type="button" size="sm" variant="outline" onClick={() => void forkWorkspaceAgent(workspaceId, name).then(reloadAgents)}>
                Fork {name}
              </Button>
            ))}
          </div>
          {agents.length > 0 ? (
            <>
              <Select
                value={selectedAgent || undefined}
                onValueChange={setSelectedAgent}
              >
                <SelectTrigger className="max-w-xs">
                  <SelectValue placeholder="Select agent" />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((agent) => (
                    <SelectItem key={agent.name} value={agent.name}>
                      {agent.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Textarea
                value={personaPrompt}
                onChange={(event) => setPersonaPrompt(event.target.value)}
                rows={8}
                placeholder="Persona body (immutable backend rules are assembled server-side)"
              />
              <Button
                type="button"
                onClick={() =>
                  void updateWorkspaceAgent(workspaceId, selectedAgent, { persona_prompt: personaPrompt }).then(
                    reloadAgents,
                  )
                }
              >
                Save persona
              </Button>
            </>
          ) : (
            <p className="text-muted-foreground text-sm">Fork a worker to customize persona prompts.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
