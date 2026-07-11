"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { createWorkOrder, DEFAULT_PROFILE_ID } from "@/lib/api-client"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { Button } from "@/vendor/gui/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/vendor/gui/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/vendor/gui/ui/field"
import { Spinner } from "@/vendor/gui/ui/spinner"
import { Textarea } from "@/vendor/gui/ui/textarea"
import { cn } from "@/vendor/gui/utils"

export function ChatPanel({ className }: { className?: string }) {
  const router = useRouter()
  const [goal, setGoal] = useState("")
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedGoal = goal.trim()
    if (!trimmedGoal) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await createWorkOrder({
        goal: trimmedGoal,
        profile_id: DEFAULT_PROFILE_ID,
        plan_strategy: "meta_llm",
        mode: "async",
      })
      const id = response.work_order_id ?? response.engagement_id
      router.push(`/work-orders/${id}`)
    } catch (exc) {
      setError(exc)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>Start work order</CardTitle>
        <CardDescription>
          Describe what the agents should accomplish. The catalog planner assigns personas from the
          active profile.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form id="start-work-order-form" onSubmit={onSubmit}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="work-order-goal">Goal</FieldLabel>
              <Textarea
                id="work-order-goal"
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                placeholder="Describe what the agents should accomplish…"
                disabled={loading}
                className="min-h-20 resize-none"
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault()
                    event.currentTarget.form?.requestSubmit()
                  }
                }}
              />
            </Field>
          </FieldGroup>
        </form>
        {error ? (
          <div className="mt-3">
            <ApiErrorAlert
              error={error}
              title="Could not start work order"
              fallback="Failed to start work order"
              onRetry={() => {
                const form = document.getElementById("start-work-order-form") as HTMLFormElement | null
                form?.requestSubmit()
              }}
            />
          </div>
        ) : null}
      </CardContent>
      <CardFooter>
        <Button
          type="submit"
          form="start-work-order-form"
          disabled={loading || !goal.trim()}
          className="w-full"
        >
          {loading ? <Spinner data-icon="inline-start" /> : null}
          {loading ? "Starting…" : "Start work order"}
        </Button>
      </CardFooter>
    </Card>
  )
}
