"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { postEvent } from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"
import { PageSection } from "@/components/page-section"
import { Alert, AlertDescription, AlertTitle } from "@/vendor/gui/ui/alert"
import { Button } from "@/vendor/gui/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/vendor/gui/ui/field"
import { Input } from "@/vendor/gui/ui/input"
import { Spinner } from "@/vendor/gui/ui/spinner"

export function ChatPanel() {
  const router = useRouter()
  const [goal, setGoal] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = goal.trim()
    if (!trimmed) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const correlationId = crypto.randomUUID()
      const response = await postEvent({
        event_type: "manual.investigation",
        payload: { goal: trimmed },
        correlation_id: correlationId,
      })
      const investigationId = response.event.correlation_id || correlationId
      router.push(`/investigations/${investigationId}`)
    } catch (exc) {
      setError(formatApiError(exc, "Failed to start investigation"))
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageSection>
      <CardHeader>
        <CardTitle>New investigation</CardTitle>
        <CardDescription>
          Describe the goal. Planning runs in the background — you are redirected while personas are assigned.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit}>
          <FieldGroup className="flex flex-col gap-3">
            <Field>
              <FieldLabel htmlFor="investigation-goal">Goal</FieldLabel>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="investigation-goal"
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  placeholder="Investigate suspicious login from 203.0.113.4"
                  disabled={loading}
                />
                <Button type="submit" disabled={loading || !goal.trim()}>
                  {loading ? <Spinner data-icon="inline-start" /> : null}
                  {loading ? "Starting…" : "Start"}
                </Button>
              </div>
            </Field>
          </FieldGroup>
        </form>
        {error ? (
          <Alert variant="destructive" className="mt-3">
            <AlertTitle>Could not start investigation</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </PageSection>
  )
}
