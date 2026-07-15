"use client"

import { formatJsonLabel, isPlainObject, jsonPreview } from "@/lib/json-display"
import { Badge } from "@/vendor/gui/ui/badge"
import { cn } from "@/vendor/gui/utils"

const MAX_DEPTH = 6

function PrimitiveValue({ value }: { value: string | number | boolean | null }) {
  if (value === null) {
    return <span className="text-muted-foreground italic">null</span>
  }
  if (typeof value === "boolean") {
    return <Badge variant="outline">{value ? "true" : "false"}</Badge>
  }
  if (typeof value === "number") {
    return <code className="text-xs">{value}</code>
  }
  return <p className="text-sm leading-relaxed whitespace-pre-wrap">{value}</p>
}

function JsonNode({
  label,
  value,
  depth = 0,
  boxed = true,
}: {
  label?: string
  value: unknown
  depth?: number
  boxed?: boolean
}) {
  if (depth > MAX_DEPTH) {
    return (
      <div className="text-muted-foreground text-xs">
        {label ? <span className="font-medium">{formatJsonLabel(label)}: </span> : null}
        {jsonPreview(value)}
      </div>
    )
  }

  if (value === null || value === undefined) {
    return (
      <div className="space-y-1">
        {label ? <p className="text-xs font-medium">{formatJsonLabel(label)}</p> : null}
        <PrimitiveValue value={null} />
      </div>
    )
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return (
      <div className="space-y-1">
        {label ? <p className="text-xs font-medium">{formatJsonLabel(label)}</p> : null}
        <PrimitiveValue value={value} />
      </div>
    )
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <div className="space-y-1">
          {label ? <p className="text-xs font-medium">{formatJsonLabel(label)}</p> : null}
          <p className="text-muted-foreground text-xs">Empty list</p>
        </div>
      )
    }

    const primitiveItems = value.every(
      (item) =>
        item === null ||
        typeof item === "string" ||
        typeof item === "number" ||
        typeof item === "boolean",
    )

    return (
      <div className="space-y-2">
        {label ? (
          <p className="text-xs font-medium">
            {formatJsonLabel(label)}{" "}
            <span className="text-muted-foreground font-normal">({value.length})</span>
          </p>
        ) : null}
        {primitiveItems ? (
          <ul className="text-muted-foreground list-disc space-y-1 pl-4 text-sm">
            {value.map((item, index) => (
              <li key={`${label ?? "item"}-${index}`}>
                {item === null ? "null" : String(item)}
              </li>
            ))}
          </ul>
        ) : (
          <div className="space-y-2">
            {value.map((item, index) => (
              <div key={`${label ?? "item"}-${index}`} className={cn(boxed && depth === 0 && "border p-3")}>
                <JsonNode
                  label={`Item ${index + 1}`}
                  value={item}
                  depth={depth + 1}
                  boxed={boxed}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  if (isPlainObject(value)) {
    const entries = Object.entries(value).filter(([, entryValue]) => entryValue !== undefined)
    if (entries.length === 0) {
      return (
        <div className="space-y-1">
          {label ? <p className="text-xs font-medium">{formatJsonLabel(label)}</p> : null}
          <p className="text-muted-foreground text-xs">Empty object</p>
        </div>
      )
    }

    return (
      <div className="space-y-3">
        {label ? <p className="text-xs font-medium">{formatJsonLabel(label)}</p> : null}
        <div className="grid gap-3">
          {entries.map(([key, entryValue]) => (
            <div key={key} className={cn(boxed && depth === 0 && "border p-3")}>
              <JsonNode label={key} value={entryValue} depth={depth + 1} boxed={boxed} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {label ? <p className="text-xs font-medium">{formatJsonLabel(label)}</p> : null}
      <pre className="bg-muted overflow-auto border p-2 text-xs">{jsonPreview(value, 4000)}</pre>
    </div>
  )
}

export function JsonPayloadView({
  data,
  title,
  className,
  boxed = true,
}: {
  data: unknown
  title?: string
  className?: string
  boxed?: boolean
}) {
  return (
    <div className={cn("space-y-3", className)}>
      {title ? <p className="text-sm font-medium">{title}</p> : null}
      <JsonNode value={data} boxed={boxed} />
    </div>
  )
}
