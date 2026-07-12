"use client"

import { useEffect, useState } from "react"
import { ArrowUpIcon } from "lucide-react"

import type { FollowUpMode } from "@/lib/follow-up"
import { Button } from "@/vendor/gui/ui/button"
import { Spinner } from "@/vendor/gui/ui/spinner"
import { Textarea } from "@/vendor/gui/ui/textarea"

const PLAN_ENABLED = process.env.NEXT_PUBLIC_FOLLOW_UP_PLAN !== "0"

const CREATE_MODE_OPTIONS: { value: FollowUpMode; label: string; hint: string }[] = [
  { value: "qa", label: "Ask", hint: "Quick advisory answer (consultant only)" },
  ...(PLAN_ENABLED
    ? [
        {
          value: "plan" as const,
          label: "Plan",
          hint: "Fixed multi-agent plan → specialists → synthesis",
        },
      ]
    : []),
  { value: "auto", label: "Auto", hint: "Server picks Ask or full plan" },
]

const FOLLOW_UP_MODE_OPTIONS: { value: FollowUpMode; label: string; hint: string }[] = [
  ...(PLAN_ENABLED
    ? [
        {
          value: "plan" as const,
          label: "Plan",
          hint: "New fixed plan → re-run all specialists → synthesis",
        },
      ]
    : []),
  { value: "qa", label: "Ask", hint: "Consultant read-only advisory" },
  {
    value: "orchestrate",
    label: "Reinvestigate",
    hint: "Dynamic follow-up: conductor spawns specialists step by step (no fixed plan)",
  },
  { value: "auto", label: "Auto", hint: "Server picks Ask, plan, or reinvestigation" },
]

export type OperatorMessageComposerProps = {
  variant: "create" | "follow_up"
  disabled?: boolean
  sending?: boolean
  defaultMode?: FollowUpMode
  isFirstFollowUp?: boolean
  onSend: (message: string, mode: FollowUpMode) => Promise<boolean>
}

export function OperatorMessageComposer({
  variant,
  disabled,
  sending,
  defaultMode,
  isFirstFollowUp = false,
  onSend,
}: OperatorMessageComposerProps) {
  const modeOptions = variant === "create" ? CREATE_MODE_OPTIONS : FOLLOW_UP_MODE_OPTIONS
  const initialMode: FollowUpMode =
    defaultMode ??
    (variant === "create"
      ? PLAN_ENABLED
        ? "plan"
        : "auto"
      : PLAN_ENABLED && isFirstFollowUp
        ? "plan"
        : "auto")
  const [draft, setDraft] = useState("")
  const [mode, setMode] = useState<FollowUpMode>(initialMode)

  useEffect(() => {
    if (variant === "create" && PLAN_ENABLED) {
      setMode("plan")
      return
    }
    if (isFirstFollowUp && PLAN_ENABLED) {
      setMode("plan")
    }
  }, [isFirstFollowUp, variant])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = draft.trim()
    if (!trimmed || disabled || sending) return
    const sent = await onSend(trimmed, mode)
    if (sent) setDraft("")
  }

  const activeHint = modeOptions.find((item) => item.value === mode)?.hint
  const placeholder =
    variant === "create"
      ? "Describe what the agents should accomplish…"
      : "Ask a follow-up or add context for the agents…"
  const submitLabel = sending
    ? "Sending…"
    : variant === "create"
      ? "Start work order"
      : "Send follow-up"

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1">
        {modeOptions.map((item) => (
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
        placeholder={placeholder}
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
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
