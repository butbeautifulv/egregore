import { memo } from "react"

import { FindingContent } from "@/components/engagement/finding-content"
import { JsonPayloadView } from "@/components/json-payload-view"
import { PlannerPlanView } from "@/components/planner-plan-view"
import {
  isFindingPayload,
  isPlainObject,
  isPlannerPlanPayload,
  parseJsonMaybe,
} from "@/lib/json-display"
import { cn } from "@/vendor/gui/utils"

function StructuredText({
  text,
  streaming,
  isError,
}: {
  text: string
  streaming?: boolean
  isError?: boolean
}) {
  const parsed = parseJsonMaybe(text)
  if (parsed && isPlainObject(parsed)) {
    if (isPlannerPlanPayload(parsed)) {
      return <PlannerPlanView data={parsed} />
    }
    if (isFindingPayload(parsed)) {
      return <FindingContent data={parsed} />
    }
    return <JsonPayloadView data={parsed} />
  }

  return (
    <pre
      className={cn(
        "bg-muted max-h-96 overflow-auto whitespace-pre-wrap border p-3 text-xs leading-relaxed",
        streaming && "ring-primary/40 ring-1",
        isError && "text-destructive",
      )}
    >
      {text}
      {streaming ? <span className="animate-pulse">▍</span> : null}
    </pre>
  )
}

export const ChatBubble = memo(function ChatBubble({
  text,
  streaming,
  isError,
  monospace,
}: {
  text: string
  streaming?: boolean
  isError?: boolean
  monospace?: boolean
}) {
  if (!text) {
    if (streaming) return null
    return <span className="text-muted-foreground text-xs">Waiting for agent stream…</span>
  }

  const trimmed = text.trim()
  const earlyParsed = parseJsonMaybe(trimmed)
  const looksLikeJson =
    Boolean(earlyParsed) ||
    trimmed.startsWith("{") ||
    trimmed.startsWith("[") ||
    monospace

  if (looksLikeJson) {
    return <StructuredText text={text} streaming={streaming} isError={isError} />
  }

  return (
    <p
      className={cn(
        "text-sm leading-relaxed whitespace-pre-wrap",
        streaming && "ring-primary/40 ring-1 p-2",
        isError && "text-destructive",
      )}
    >
      {text}
      {streaming ? <span className="animate-pulse">▍</span> : null}
    </p>
  )
})
