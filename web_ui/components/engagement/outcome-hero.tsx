"use client"

import { Badge } from "@/vendor/gui/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"
import { StructuredFieldRow } from "@/components/structured-field-row"

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map(String).filter((item) => item.trim().length > 0)
}

type OutcomeSection = {
  title: string
  body: string
  items: string[]
}

function parseOutcomeSections(value: unknown): OutcomeSection[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((section) => ({
      title: String(section.title ?? "").trim(),
      body: String(section.body ?? "").trim(),
      items: asStringList(section.items),
    }))
    .filter((section) => section.title || section.body || section.items.length > 0)
}

export function OutcomeHero({ outcome }: { outcome: Record<string, unknown> }) {
  const summary = String(outcome.summary ?? "").trim()
  const title = String(outcome.title ?? outcome.topic ?? "Work order outcome").trim()
  const kind = String(outcome.kind ?? "advisory")
  const risk = outcome.risk_level ? String(outcome.risk_level) : ""
  const recommendations = asStringList(outcome.recommendations)
  const sections = parseOutcomeSections(outcome.sections)
  const provenance = Array.isArray(outcome.provenance) ? outcome.provenance : []
  const degraded = Boolean(outcome.degraded)

  return (
    <div className="border bg-card flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold">{title}</h3>
        <Badge variant="secondary">{kind}</Badge>
        {risk ? <Badge variant="outline">{risk}</Badge> : null}
        {degraded ? <Badge variant="destructive">degraded</Badge> : null}
      </div>
      {summary ? (
        <p className="text-muted-foreground whitespace-pre-wrap text-sm leading-relaxed">{summary}</p>
      ) : null}
      {sections.length > 0
        ? sections.map((section, index) => (
            <StructuredFieldRow key={`section-${index}`} title={section.title || `Section ${index + 1}`}>
              {section.body ? (
                <p className="text-muted-foreground whitespace-pre-wrap text-sm leading-relaxed">{section.body}</p>
              ) : null}
              {section.items.length > 0 ? (
                <ul className="text-muted-foreground mt-2 list-disc space-y-1 pl-4 text-sm">
                  {section.items.map((item, itemIndex) => (
                    <li key={`section-${index}-item-${itemIndex}`}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </StructuredFieldRow>
          ))
        : null}
      {recommendations.length > 0 ? (
        <StructuredFieldRow title="Recommendations">
          <ul className="text-muted-foreground list-disc space-y-1 pl-4 text-sm">
            {recommendations.map((item, index) => (
              <li key={`rec-${index}`}>{item}</li>
            ))}
          </ul>
        </StructuredFieldRow>
      ) : null}
      {provenance.length > 0 ? (
        <Collapsible>
          <CollapsibleTrigger className="text-muted-foreground text-xs underline-offset-2 hover:underline">
            Sources ({provenance.length})
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-2">
            {provenance.map((item, index) => {
              if (!item || typeof item !== "object") return null
              const record = item as Record<string, unknown>
              return (
                <p key={`prov-${index}`} className="text-muted-foreground text-xs">
                  {String(record.persona ?? "agent")}
                  {record.job_id ? ` · ${String(record.job_id)}` : ""}
                  {record.status ? ` · ${String(record.status)}` : ""}
                </p>
              )
            })}
          </CollapsibleContent>
        </Collapsible>
      ) : null}
    </div>
  )
}

export function outcomeCopyText(outcome: Record<string, unknown>): string {
  const lines = [String(outcome.title ?? outcome.topic ?? "Work order outcome").trim()]
  const summary = String(outcome.summary ?? "").trim()
  if (summary) lines.push("", summary)
  for (const section of parseOutcomeSections(outcome.sections)) {
    if (section.title) lines.push("", section.title)
    if (section.body) lines.push(section.body)
    for (const item of section.items) lines.push(`- ${item}`)
  }
  const recommendations = asStringList(outcome.recommendations)
  if (recommendations.length) {
    lines.push("", "Recommendations:")
    for (const item of recommendations) lines.push(`- ${item}`)
  }
  return lines.join("\n")
}
