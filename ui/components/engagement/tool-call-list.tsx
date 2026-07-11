import { memo } from "react"
import { CheckIcon, WrenchIcon, XIcon } from "lucide-react"

import {
  Attachment,
  AttachmentContent,
  AttachmentDescription,
  AttachmentGroup,
  AttachmentMedia,
  AttachmentTitle,
} from "@/components/ui/attachment"
import type { ChatToolCall } from "@/lib/types"
import { Spinner } from "@/vendor/gui/ui/spinner"

function attachmentState(
  status: ChatToolCall["status"],
): "done" | "processing" | "error" {
  if (status === "error") return "error"
  if (status === "started") return "processing"
  return "done"
}

function ToolStatusIcon({ status }: { status: ChatToolCall["status"] }) {
  if (status === "started") return <Spinner />
  if (status === "error") return <XIcon />
  if (status === "done") return <CheckIcon />
  return <WrenchIcon />
}

export const ToolCallList = memo(function ToolCallList({ tools }: { tools: ChatToolCall[] }) {
  if (!tools.length) return null

  return (
    <AttachmentGroup className="w-full max-w-full">
      {tools.map((tool, index) => (
        <Attachment
          key={`${tool.name}-${tool.tool_call_id ?? index}`}
          size="xs"
          state={attachmentState(tool.status)}
          className="w-56"
        >
          <AttachmentMedia>
            <ToolStatusIcon status={tool.status} />
          </AttachmentMedia>
          <AttachmentContent>
            <AttachmentTitle>{tool.name}</AttachmentTitle>
            <AttachmentDescription>{tool.status}</AttachmentDescription>
          </AttachmentContent>
        </Attachment>
      ))}
    </AttachmentGroup>
  )
})
