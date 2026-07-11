"use client"

import { useEffect, useState } from "react"
import { ArrowUpIcon } from "lucide-react"

import type { FollowUpMode } from "@/lib/follow-up"
import { Button } from "@/vendor/gui/ui/button"
import { Spinner } from "@/vendor/gui/ui/spinner"
import { Textarea } from "@/vendor/gui/ui/textarea"

const PLAN_ENABLED = process.env.NEXT_PUBLIC_FOLLOW_UP_PLAN !== "0"

const MODE_OPTIONS: { value: FollowUpMode; label: string; hint: string }[] = [
  ...(PLAN_ENABLED
    ? [{ value: "plan" as const, label: "Plan", hint: "Re-run planner and agents" }]
    : []),
  { value: "qa", label: "Q&A", hint: "Consultant read-only advisory" },
  { value: "auto", label: "Auto", hint: "Server picks Q&A, plan, or reinvestigation" },
]

export function FollowUpComposer({
  disabled,
  sending,
  isFirstFollowUp = false,
  onSend,
}: {
  disabled?: boolean
  sending?: boolean
  isFirstFollowUp?: boolean
  onSend: (message: string, mode: FollowUpMode) => Promise<boolean>
}) {
  const [draft, setDraft] = useState("")
  const [mode, setMode] = useState<FollowUpMode>(PLAN_ENABLED && isFirstFollowUp ? "plan" : "auto")

  useEffect(() => {
    if (isFirstFollowUp && PLAN_ENABLED) {
      setMode("plan")
    }
  }, [isFirstFollowUp])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = draft.trim()
    if (!trimmed || disabled || sending) return
    const sent = await onSend(trimmed, mode)
    if (sent) setDraft("")
  }

  const activeHint = MODE_OPTIONS.find((item) => item.value === mode)?.hint

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1">
        {MODE_OPTIONS.map((item) => (
          <Button
            key={item.value}
            type="button"
            size="sm"
            variant={mode === item.value ? "default" : "outline"}
            disabled={disabled || sending}
            onClick={() => setMode(item.value)}
          >
            {item.label}
          </Button>
        ))}
      </div>
      <Textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="Ask a follow-up or add context for the agents…"
        disabled={disabled || sending}
        className="min-h-20 resize-none"
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault()
            void handleSubmit(event)
          }
        }}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-muted-foreground text-xs">
          {activeHint ? `${activeHint}. ` : ""}
          Enter to send · Shift+Enter for a new line.
        </p>
        <Button type="submit" size="sm" disabled={disabled || sending || !draft.trim()}>
          {sending ? <Spinner data-icon="inline-start" /> : <ArrowUpIcon data-icon="inline-start" />}
          {sending ? "Sending…" : "Send follow-up"}
        </Button>
      </div>
    </form>
  )
}
