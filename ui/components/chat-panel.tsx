"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { postEvent } from "@/lib/api-client"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { Input } from "@/vendor/gui/ui/input"

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
      setError(exc instanceof Error ? exc.message : "Failed to start investigation")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>New investigation</CardTitle>
        <CardDescription>
          Describe the investigation goal. Planning runs in the background — you will be redirected
          immediately while the LLM planner assigns personas.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form className="flex gap-2" onSubmit={onSubmit}>
          <Input
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder="Investigate suspicious login from 203.0.113.4"
            disabled={loading}
          />
          <Button type="submit" disabled={loading || !goal.trim()}>
            {loading ? "Starting…" : "Start"}
          </Button>
        </form>
        {error ? <p className="text-destructive text-xs">{error}</p> : null}
      </CardContent>
    </Card>
  )
}
