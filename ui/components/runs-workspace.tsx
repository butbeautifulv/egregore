"use client"

import { useState } from "react"

import { PageSection } from "@/components/page-section"
import { ModeSwitcher } from "@/components/mode-switcher"
import { PlanApprovePanel } from "@/components/plan-approve-panel"
import { RunTimeline } from "@/components/run-timeline"
import {
  approvePlan,
  createSession,
  runStep,
  type InteractionMode,
  type RunResponse,
  type WorkPlan,
} from "@/lib/run-api"
import { formatApiError, isRetryableSessionError, sessionErrorTitle } from "@/lib/format-api-error"
import { Alert, AlertDescription, AlertTitle } from "@/vendor/gui/ui/alert"
import { Button } from "@/vendor/gui/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/vendor/gui/ui/field"
import { Input } from "@/vendor/gui/ui/input"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Spinner } from "@/vendor/gui/ui/spinner"

export function RunsWorkspace() {
  const [goal, setGoal] = useState("")
  const [mode, setMode] = useState<InteractionMode>("plan")
  const [message, setMessage] = useState("")
  const [active, setActive] = useState<RunResponse | null>(null)
  const [steps, setSteps] = useState<Array<{ label: string; payload: Record<string, unknown> }>>([])
  const [error, setError] = useState<string | null>(null)
  const [lastError, setLastError] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)

  const plan = (active?.result?.plan as WorkPlan | undefined) ?? null
  const runId = active?.run_context.context_id ?? ""

  async function startSession() {
    const trimmed = goal.trim()
    if (!trimmed) return
    setLoading(true)
    setError(null)
    setLastError(null)
    try {
      const response = await createSession({ goal: trimmed, message: trimmed, mode })
      setActive(response)
      setSteps([{ label: "session started", payload: response.result }])
    } catch (exc) {
      setLastError(exc)
      setError(formatApiError(exc, "Failed to start session"))
    } finally {
      setLoading(false)
    }
  }

  async function sendStep() {
    if (!active || !message.trim()) return
    setLoading(true)
    setError(null)
    setLastError(null)
    try {
      const response = await runStep(runId, { message: message.trim(), mode })
      setActive(response)
      setSteps((prev) => [...prev, { label: `step (${mode})`, payload: response.result }])
      setMessage("")
    } catch (exc) {
      setLastError(exc)
      setError(formatApiError(exc, "Step failed"))
    } finally {
      setLoading(false)
    }
  }

  async function onApprove(decision: "approve" | "reject") {
    if (!active) return
    setLoading(true)
    setError(null)
    try {
      const response = await approvePlan(runId, { decision })
      setActive(response)
      setSteps((prev) => [...prev, { label: `plan ${decision}`, payload: response.result }])
    } catch (exc) {
      setError(formatApiError(exc, "Plan action failed"))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Agent runs"
        description="Interactive conductor sessions with plan / ask / agent / debug modes."
        actions={<ModeSwitcher value={mode} onChange={setMode} disabled={loading} />}
      />

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>{sessionErrorTitle(lastError)}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2">
            <span>{error}</span>
            {isRetryableSessionError(lastError) ? (
              <Button type="button" size="sm" variant="outline" onClick={startSession} disabled={loading}>
                Retry
              </Button>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <PageSection>
          <CardHeader>
            <CardTitle>New session</CardTitle>
            <CardDescription>Start a conductor session in {mode} mode.</CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup className="flex flex-col gap-3">
              <Field>
                <FieldLabel htmlFor="session-goal">Investigation goal</FieldLabel>
                <Input
                  id="session-goal"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  placeholder="Investigation goal"
                  disabled={loading}
                />
              </Field>
              <Button type="button" disabled={loading || !goal.trim()} onClick={startSession}>
                {loading ? <Spinner data-icon="inline-start" /> : null}
                Start session
              </Button>
            </FieldGroup>
          </CardContent>
        </PageSection>

        {active ? (
          <PageSection>
            <CardHeader>
              <CardTitle>Run {runId}</CardTitle>
            </CardHeader>
            <CardContent>
              <FieldGroup className="flex flex-col gap-3">
                <Field>
                  <FieldLabel htmlFor="session-message">Next message</FieldLabel>
                  <Input
                    id="session-message"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Next message"
                    disabled={loading}
                  />
                </Field>
                <Button type="button" disabled={loading || !message.trim()} onClick={sendStep}>
                  Send step
                </Button>
              </FieldGroup>
            </CardContent>
          </PageSection>
        ) : (
          <PageSection>
            <CardHeader>
              <CardTitle>Active session</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-xs">Start a session to see plan review and timeline.</p>
            </CardContent>
          </PageSection>
        )}
      </div>

      {active && plan ? (
        <PlanApprovePanel
          plan={plan}
          loading={loading}
          onApprove={() => onApprove("approve")}
          onReject={() => onApprove("reject")}
        />
      ) : null}

      {active ? <RunTimeline runId={runId} steps={steps} mode={mode} /> : null}
    </div>
  )
}
