import { Badge } from "@/vendor/gui/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

type InvestigationFindingsProps = {
  findings: Record<string, unknown>[]
  completedPersonas?: string[]
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0)
}

function findingBody(item: Record<string, unknown>): Record<string, unknown> {
  const nested = item.finding
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return nested as Record<string, unknown>
  }
  return item
}

function FindingContent({ data }: { data: Record<string, unknown> }) {
  const raw = asString(data.raw_response)
  if (raw) {
    return (
      <pre className="bg-muted max-h-96 overflow-auto whitespace-pre-wrap rounded-md p-3 text-xs">{raw}</pre>
    )
  }

  const summary = asString(data.summary) || asString(data.finding)
  const topic = asString(data.topic)
  const risk = asString(data.risk_level) || asString(data.severity) || asString(data.priority)
  const recommendations = asStringList(data.recommendations) || asStringList(data.recommended_actions)
  const references = asStringList(data.references)
  const confidence = typeof data.confidence === "number" ? data.confidence : null

  return (
    <div className="space-y-3 text-sm">
      {topic ? <p className="font-medium">{topic}</p> : null}
      {summary ? <p className="text-muted-foreground leading-relaxed">{summary}</p> : null}
      {risk ? (
        <p className="text-xs">
          Risk: <span className="font-medium">{risk}</span>
          {confidence !== null ? ` · confidence ${(confidence * 100).toFixed(0)}%` : null}
        </p>
      ) : null}
      {recommendations.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium">Recommendations</p>
          <ul className="text-muted-foreground list-disc space-y-1 pl-4 text-xs">
            {recommendations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {references.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium">References</p>
          <ul className="text-muted-foreground list-disc space-y-1 pl-4 text-xs">
            {references.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {!summary && !topic && recommendations.length === 0 ? (
        <pre className="bg-muted max-h-64 overflow-auto rounded-md p-3 text-xs">
          {JSON.stringify(data, null, 2)}
        </pre>
      ) : null}
    </div>
  )
}

export function InvestigationFindings({ findings, completedPersonas = [] }: InvestigationFindingsProps) {
  if (findings.length === 0) {
    const personasFinished = completedPersonas.length > 0
    return (
      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-xs">
            {personasFinished
              ? "Workers finished but no structured results were stored for this investigation. Create a new investigation to get a full consultant report."
              : "No findings yet. Results appear here when a worker completes."}
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Results</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {findings.map((item, index) => {
          const persona = asString(item.persona) || "agent"
          const body = findingBody(item)
          return (
            <div key={`${persona}-${index}`} className="space-y-2 border-t pt-4 first:border-t-0 first:pt-0">
              <div className="flex items-center gap-2">
                <Badge variant="outline">{persona}</Badge>
                {asString(item.job_id) ? (
                  <span className="text-muted-foreground text-xs">{asString(item.job_id)}</span>
                ) : null}
              </div>
              <FindingContent data={body} />
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
