"use client"

import { StructuredAnswerContent } from "@/components/engagement/structured-answer-content"
import { formatFollowUpRoleLabel } from "@/lib/follow-up"
import type { FollowUpMessage } from "@/lib/follow-up"
import { Badge } from "@/vendor/gui/ui/badge"

function statusLabel(message: FollowUpMessage): string {
  if (message.streaming || message.status === "pending" || message.status === "queued") {
    return "streaming"
  }
  if (message.status === "failed") return "failed"
  return "completed"
}

export function AssistantFindingPanel({ message }: { message: FollowUpMessage }) {
  const persona = message.persona ?? "assistant"
  const showSpinner =
    message.streaming || message.status === "pending" || message.status === "queued"
  const roleLabel = formatFollowUpRoleLabel(message.persona, message.workKind)

  return (
    <div className="flex w-full max-w-2xl flex-col gap-2">
      <div className="flex items-center gap-2">
        <Badge variant="secondary">{persona}</Badge>
        <Badge variant={showSpinner ? "default" : "outline"} className="text-[10px]">
          {statusLabel(message)}
        </Badge>
      </div>
      <div className="bg-muted/40 border px-4 py-3">
        <StructuredAnswerContent
          text={message.text}
          finding={message.finding}
          streaming={showSpinner}
        />
        {message.status === "failed" ? (
          <p className="text-destructive mt-2 text-xs">{message.error ?? "Follow-up failed"}</p>
        ) : null}
      </div>
      <p className="text-muted-foreground text-[10px]">
        {roleLabel}
        {message.status === "completed"
          ? " · answered"
          : showSpinner
            ? " · streaming"
            : message.status === "failed"
              ? " · failed"
              : ""}
      </p>
    </div>
  )
}
