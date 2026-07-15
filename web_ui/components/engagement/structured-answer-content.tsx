"use client"

import { FindingContent } from "@/components/engagement/finding-content"
import { MarkdownContent } from "@/components/engagement/markdown-content"
import { JsonPayloadView } from "@/components/json-payload-view"
import { PlannerPlanView } from "@/components/planner-plan-view"
import { findingEnvelope } from "@/lib/finding-display"
import {
  isFindingPayload,
  isPlainObject,
  isPlannerPlanPayload,
  parseJsonMaybe,
} from "@/lib/json-display"
import { Spinner } from "@/vendor/gui/ui/spinner"

function ComposingAnswer() {
  return (
    <div className="text-foreground flex items-center gap-2 text-sm">
      <Spinner className="size-4" />
      <span className="shimmer">Composing answer…</span>
    </div>
  )
}

export function StructuredAnswerContent({
  text,
  finding,
  streaming,
}: {
  text: string
  finding?: Record<string, unknown> | null
  streaming?: boolean
}) {
  if (finding && isPlainObject(finding)) {
    const { body, evidenceManifest } = findingEnvelope(finding)
    if (isPlannerPlanPayload(body)) {
      return <PlannerPlanView data={body} />
    }
    if (isFindingPayload(body)) {
      return <FindingContent data={body} evidenceManifest={evidenceManifest} />
    }
    return <JsonPayloadView data={body} />
  }

  const trimmed = text.trim()
  if (!trimmed) {
    return streaming ? <ComposingAnswer /> : null
  }

  const parsed = parseJsonMaybe(trimmed)
  if (parsed && isPlainObject(parsed)) {
    const { body, evidenceManifest } = findingEnvelope(parsed)
    if (isPlannerPlanPayload(body)) {
      return <PlannerPlanView data={body} />
    }
    if (isFindingPayload(body)) {
      return <FindingContent data={body} evidenceManifest={evidenceManifest} />
    }
    return <JsonPayloadView data={parsed} />
  }

  return <MarkdownContent>{text}</MarkdownContent>
}
