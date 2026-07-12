"use client"

import { useEffect, useMemo, useState } from "react"
import { BotIcon } from "lucide-react"

import { ChatBubble } from "@/components/engagement/chat-bubble"
import { FindingContent } from "@/components/engagement/finding-content"
import { MessageActions } from "@/components/engagement/message-actions"
import { ReasoningBlock } from "@/components/engagement/reasoning-block"
import { ToolCallList } from "@/components/engagement/tool-call-list"
import { Marker, MarkerContent, MarkerIcon } from "@/components/ui/marker"
import { findingEnvelope } from "@/lib/finding-display"
import { resolveEntryCopyText } from "@/lib/chat-message-text"
import { CHAT_COLUMN_CLASS } from "@/lib/chat-layout"
import type { AgentChatEntry } from "@/lib/types"
import { Badge } from "@/vendor/gui/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"
import { Spinner } from "@/vendor/gui/ui/spinner"

function statusLabel(entry: AgentChatEntry): string {
  if (entry.streaming) return "streaming"
  if (entry.jobError) return "failed"
  return "completed"
}

export function AgentMessageBlock({
  entry,
  finding,
  defaultOpen,
}: {
  entry: AgentChatEntry
  finding?: Record<string, unknown>
  defaultOpen?: boolean
}) {
  const [reasoningOpen, setReasoningOpen] = useState(
    defaultOpen ?? (entry.streaming || entry.agentExpanded),
  )
  const label = statusLabel(entry)
  const hasTools = entry.tools.length > 0
  const hasReasoning = Boolean(entry.reasoning)
  const hasTurns = entry.turns.length > 0 || Boolean(entry.buffer)
  const showStructuredFinding =
    Boolean(finding) && !entry.streaming && !entry.jobError && !entry.isControlError
  const { body, evidenceManifest } = finding ? findingEnvelope(finding) : { body: {}, evidenceManifest: undefined }
  const copyText = useMemo(() => resolveEntryCopyText(entry, finding), [entry, finding])

  useEffect(() => {
    if (entry.streaming) setReasoningOpen(true)
  }, [entry.streaming])

  return (
    <div className={`group/message ${CHAT_COLUMN_CLASS}`}>
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{entry.persona}</Badge>
          <Badge variant={entry.streaming ? "default" : "outline"} className="text-[10px]">
            {label}
          </Badge>
        </div>

        {hasTools ? <ToolCallList tools={entry.tools} /> : null}

        {hasReasoning ? (
          <Collapsible open={reasoningOpen} onOpenChange={setReasoningOpen}>
            <CollapsibleTrigger className="text-muted-foreground text-xs underline-offset-2 hover:underline">
              {reasoningOpen ? "Hide reasoning" : "Show reasoning"}
            </CollapsibleTrigger>
            <CollapsibleContent className="flex flex-col gap-2">
              <ReasoningBlock reasoning={entry.reasoning} />
            </CollapsibleContent>
          </Collapsible>
        ) : null}

        <div className="text-foreground flex flex-col gap-3 text-sm leading-7">
          {showStructuredFinding ? (
            <FindingContent data={body} evidenceManifest={evidenceManifest} />
          ) : (
            <>
              {entry.turns.map((turn, index) => (
                <ChatBubble key={`${entry.jobId}-turn-${index}`} text={turn} />
              ))}

              {entry.buffer ? (
                <ChatBubble
                  text={entry.buffer}
                  streaming={entry.streaming}
                  isError={entry.isControlError || Boolean(entry.jobError)}
                />
              ) : entry.streaming ? (
                <Marker role="status">
                  <MarkerIcon>
                    <Spinner />
                  </MarkerIcon>
                  <MarkerContent className="shimmer">
                    <span className="font-medium">{entry.persona}</span> is working…
                  </MarkerContent>
                </Marker>
              ) : !hasTurns ? (
                <Marker>
                  <MarkerIcon>
                    <BotIcon />
                  </MarkerIcon>
                  <MarkerContent>No output recorded for this agent.</MarkerContent>
                </Marker>
              ) : null}
            </>
          )}
        </div>

        {!entry.streaming && (entry.jobError || entry.isControlError) ? (
          <p className="text-destructive text-xs">{entry.jobError || "Control error"}</p>
        ) : null}

        {!entry.streaming && copyText ? <MessageActions text={copyText} /> : null}
      </div>
    </div>
  )
}
