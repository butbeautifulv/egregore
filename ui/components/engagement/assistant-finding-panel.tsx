"use client"

import { StructuredAnswerContent } from "@/components/engagement/structured-answer-content"
import { MessageActions } from "@/components/engagement/message-actions"
import { formatFollowUpRoleLabel } from "@/lib/follow-up"
import { CHAT_COLUMN_CLASS } from "@/lib/chat-layout"
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
  const roleLabel = formatFollowUpRoleLabel(message.persona, message.workKind, message.followUpId)
  const copyText = message.text?.trim() ?? ""

  return (
    <div className={`group/message ${CHAT_COLUMN_CLASS}`}>
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{persona}</Badge>
          <Badge variant={showSpinner ? "default" : "outline"} className="text-[10px]">
            {statusLabel(message)}
          </Badge>
        </div>
        <div className="text-foreground text-sm leading-7">
          <StructuredAnswerContent
            text={message.text}
            finding={message.finding}
            streaming={showSpinner}
          />
        </div>
        {message.status === "failed" ? (
          <p className="text-destructive text-xs">{message.error ?? "Follow-up failed"}</p>
        ) : null}
        {!showSpinner && copyText ? <MessageActions text={copyText} /> : null}
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
    </div>
  )
}
