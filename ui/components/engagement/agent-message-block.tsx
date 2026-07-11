"use client"

import { useEffect, useState } from "react"
import { BotIcon } from "lucide-react"

import { ChatBubble } from "@/components/engagement/chat-bubble"
import { FindingContent } from "@/components/engagement/finding-content"
import { ReasoningBlock } from "@/components/engagement/reasoning-block"
import { ToolCallList } from "@/components/engagement/tool-call-list"
import { Marker, MarkerContent, MarkerIcon } from "@/components/ui/marker"
import { findingEnvelope } from "@/lib/finding-display"
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
  const [open, setOpen] = useState(defaultOpen ?? (entry.streaming || entry.agentExpanded))
  const label = statusLabel(entry)
  const hasToolsOrReasoning = Boolean(entry.reasoning || entry.tools.length > 0)
  const hasTurns = entry.turns.length > 0 || Boolean(entry.buffer)
  const showStructuredFinding =
    Boolean(finding) && !entry.streaming && !entry.jobError && !entry.isControlError
  const { body, evidenceManifest } = finding ? findingEnvelope(finding) : { body: {}, evidenceManifest: undefined }

  useEffect(() => {
    if (entry.streaming) setOpen(true)
  }, [entry.streaming])

  return (
    <div className="flex w-full max-w-2xl flex-col gap-2">
      <div className="flex items-center gap-2">
        <Badge variant="secondary">{entry.persona}</Badge>
        <Badge variant={entry.streaming ? "default" : "outline"} className="text-[10px]">
          {label}
        </Badge>
      </div>

      <div className="bg-muted/40 border px-4 py-3">
        {hasToolsOrReasoning ? (
          <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger className="text-muted-foreground mb-2 text-xs underline-offset-2 hover:underline">
              {open ? "Hide tools & reasoning" : "Show tools & reasoning"}
            </CollapsibleTrigger>
            <CollapsibleContent className="mb-3 flex flex-col gap-2">
              <ReasoningBlock reasoning={entry.reasoning} />
              <ToolCallList tools={entry.tools} />
            </CollapsibleContent>
          </Collapsible>
        ) : null}

        <div className="flex flex-col gap-2">
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
          <p className="text-destructive mt-2 text-xs">{entry.jobError || "Control error"}</p>
        ) : null}
      </div>
    </div>
  )
}
