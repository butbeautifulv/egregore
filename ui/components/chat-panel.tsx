"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { createWorkOrder, DEFAULT_PROFILE_ID } from "@/lib/api-client"
import type { FollowUpMode } from "@/lib/follow-up"
import { getSelectedWorkspaceId } from "@/lib/workspace"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { OperatorMessageComposer } from "@/components/engagement/operator-message-composer"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/vendor/gui/ui/card"
import { cn } from "@/vendor/gui/utils"

export function ChatPanel({ className }: { className?: string }) {
  const router = useRouter()
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)

  async function onSend(message: string, mode: FollowUpMode): Promise<boolean> {
    setLoading(true)
    setError(null)
    try {
      const workspaceId = getSelectedWorkspaceId()
      const response = await createWorkOrder({
        goal: message,
        profile_id: DEFAULT_PROFILE_ID,
        plan_strategy: "meta_llm",
        mode: "async",
        intent_mode: mode,
        ...(workspaceId ? { workspace_id: workspaceId } : {}),
      })
      const id = response.work_order_id ?? response.engagement_id
      const initialFollowUpId =
        "initial_follow_up_id" in response && response.initial_follow_up_id
          ? response.initial_follow_up_id
          : id
            ? `wo-${id}`
            : ""
      if (initialFollowUpId && id) {
        sessionStorage.setItem(`wo-initial-fu:${id}`, initialFollowUpId)
      }
      router.push(`/work-orders/${id}`)
      return true
    } catch (exc) {
      setError(exc)
      return false
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>Start work order</CardTitle>
        <CardDescription>
          Describe what the agents should accomplish. Modes: Plan (multi-agent run), Ask (quick answer), Auto.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <OperatorMessageComposer variant="create" disabled={loading} sending={loading} onSend={onSend} />
        {error ? (
          <div className="mt-3">
            <ApiErrorAlert
              error={error}
              title="Could not start work order"
              fallback="Failed to start work order"
            />
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
