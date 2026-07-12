import { memo, useState } from "react"
import { CheckIcon, ChevronDownIcon, WrenchIcon, XIcon } from "lucide-react"

import { JsonPayloadView } from "@/components/json-payload-view"
import {
  Attachment,
  AttachmentContent,
  AttachmentDescription,
  AttachmentGroup,
  AttachmentMedia,
  AttachmentTitle,
} from "@/components/ui/attachment"
import { parseJsonMaybe } from "@/lib/json-display"
import type { ChatToolCall } from "@/lib/types"
import { isPlaybookSearchTool, playbookSearchQuery } from "@/lib/tool-call-display"
import { Spinner } from "@/vendor/gui/ui/spinner"
import { cn } from "@/lib/utils"

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

function playbookSummary(tool: ChatToolCall): string {
  const query = playbookSearchQuery(tool)
  const quoted = query ? `"${query}"` : "playbooks"
  if (tool.status === "started") {
    return query ? `Searching ${quoted}` : "Searching playbooks"
  }
  if (tool.status === "error") {
    return tool.error_message ?? `playbook_search failed`
  }
  const count = tool.playbook_result?.count ?? tool.playbook_result?.skills.length ?? 0
  if (count === 0) {
    return query ? `0 playbooks for ${quoted}` : "0 playbooks found"
  }
  return query ? `${count} playbooks for ${quoted}` : `${count} playbooks found`
}

function PlaybookSearchDetails({ tool }: { tool: ChatToolCall }) {
  const [expanded, setExpanded] = useState(
    (tool.playbook_result?.count ?? 0) > 0 && (tool.playbook_result?.count ?? 0) <= 3,
  )
  const skills = tool.playbook_result?.skills ?? []
  const hasMalformed =
    tool.status === "done" &&
    !tool.playbook_result &&
    Boolean(tool.output_preview?.trim().startsWith("{"))

  if (tool.status === "error") {
    return (
      <p className="text-destructive text-xs">{tool.error_message ?? "Tool failed"}</p>
    )
  }

  if (skills.length === 0 && !hasMalformed) {
    return null
  }

  return (
    <div className="mt-1 w-full space-y-1">
      {skills.length > 0 ? (
        <>
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs"
            onClick={() => setExpanded((value) => !value)}
          >
            <ChevronDownIcon className={cn("size-3 transition-transform", expanded && "rotate-180")} />
            {expanded ? "Hide matches" : `Show ${skills.length} matches`}
          </button>
          {expanded ? (
            <ul className="text-muted-foreground max-h-40 space-y-1 overflow-y-auto text-xs">
              {skills.map((skill) => (
                <li key={skill.id} className="border-border/60 border-l pl-2">
                  <span className="text-foreground font-medium">{skill.name}</span>
                  {skill.description ? (
                    <p className="text-muted-foreground line-clamp-2">{skill.description}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
      {hasMalformed && tool.output_preview ? (
        <details className="text-xs">
          <summary className="text-muted-foreground cursor-pointer">Raw output</summary>
          {(() => {
            const parsed = parseJsonMaybe(tool.output_preview)
            return parsed ? (
              <JsonPayloadView data={parsed} boxed={false} />
            ) : (
              <pre className="bg-muted overflow-auto border p-2 text-xs">{tool.output_preview}</pre>
            )
          })()}
        </details>
      ) : null}
    </div>
  )
}

function ToolCallAttachment({ tool, index }: { tool: ChatToolCall; index: number }) {
  const playbook = isPlaybookSearchTool(tool.name)
  const title = playbook ? "playbook_search" : tool.name
  const description = playbook ? playbookSummary(tool) : tool.status

  return (
    <Attachment
      size="xs"
      state={attachmentState(tool.status)}
      className="max-w-full"
    >
      <AttachmentMedia>
        <ToolStatusIcon status={tool.status} />
      </AttachmentMedia>
      <AttachmentContent className="min-w-0">
        <AttachmentTitle>{title}</AttachmentTitle>
        <AttachmentDescription className="break-words">{description}</AttachmentDescription>
        {playbook ? <PlaybookSearchDetails tool={tool} /> : null}
      </AttachmentContent>
    </Attachment>
  )
}

export const ToolCallList = memo(function ToolCallList({ tools }: { tools: ChatToolCall[] }) {
  if (!tools.length) return null

  return (
    <AttachmentGroup className="w-full max-w-full flex-wrap">
      {tools.map((tool, index) => (
        <ToolCallAttachment
          key={`${tool.name}-${tool.tool_call_id ?? index}`}
          tool={tool}
          index={index}
        />
      ))}
    </AttachmentGroup>
  )
})
