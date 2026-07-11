"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"

import type { MemoryEntry } from "@/lib/api-client"
import { FindingContent } from "@/components/engagement/finding-content"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { Badge } from "@/vendor/gui/ui/badge"
import { cn } from "@/vendor/gui/utils"

function memoryPreview(entry: MemoryEntry): string {
  if (entry.content_parsed && typeof entry.content_parsed.summary === "string") {
    return entry.content_parsed.summary
  }
  const text = entry.content.trim()
  if (text.length <= 160) {
    return text
  }
  return `${text.slice(0, 160)}…`
}

export function MemoryEntriesList({
  entries,
  emptyTitle = "No memory entries",
  emptyDescription = "Nothing stored for this scope yet.",
  variant = "full",
  onEntryClick,
  linkAgents = false,
}: {
  entries: MemoryEntry[]
  emptyTitle?: string
  emptyDescription?: string
  variant?: "full" | "feed"
  onEntryClick?: (entry: MemoryEntry) => void
  linkAgents?: boolean
}) {
  const router = useRouter()

  if (entries.length === 0) {
    return <EmptyTableState title={emptyTitle} description={emptyDescription} />
  }

  return (
    <ul className="flex flex-col gap-3">
      {entries.map((entry) => {
        const clickable = Boolean(onEntryClick) || variant === "feed"
        const handleClick = () => {
          if (onEntryClick) {
            onEntryClick(entry)
            return
          }
          router.push(`/catalog/memory/${encodeURIComponent(entry.id)}`)
        }

        return (
          <li
            key={entry.id}
            className={cn(
              "rounded-md border p-3",
              clickable && "hover:bg-muted/40 cursor-pointer transition-colors",
            )}
            onClick={clickable ? handleClick : undefined}
            onKeyDown={
              clickable
                ? (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      handleClick()
                    }
                  }
                : undefined
            }
            role={clickable ? "button" : undefined}
            tabIndex={clickable ? 0 : undefined}
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge variant="outline">{entry.memory_type}</Badge>
              {linkAgents ? (
                <Link
                  href={`/catalog/agents/${encodeURIComponent(entry.source_agent)}`}
                  className="inline-flex"
                  onClick={(event) => event.stopPropagation()}
                >
                  <Badge variant="secondary">{entry.source_agent}</Badge>
                </Link>
              ) : (
                <Badge variant="secondary">{entry.source_agent}</Badge>
              )}
              {entry.investigation_id ? (
                <Link
                  href={`/work-orders/${entry.investigation_id}`}
                  className="text-muted-foreground text-xs underline-offset-2 hover:underline"
                  onClick={(event) => event.stopPropagation()}
                >
                  {entry.investigation_id}
                </Link>
              ) : null}
              <span className="text-muted-foreground ml-auto text-[10px]">
                {new Date(entry.created_at).toLocaleString()}
              </span>
            </div>
            {variant === "feed" ? (
              <p className="text-muted-foreground line-clamp-3 text-sm">{memoryPreview(entry)}</p>
            ) : entry.content_parsed ? (
              <FindingContent data={entry.content_parsed} />
            ) : (
              <pre className="bg-muted max-h-48 overflow-auto whitespace-pre-wrap rounded-md p-2 text-xs">
                {entry.content}
              </pre>
            )}
          </li>
        )
      })}
    </ul>
  )
}
