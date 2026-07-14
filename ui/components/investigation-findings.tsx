import { FindingContent } from "@/components/engagement/finding-content"
import { dedupeFindingsByPersona, findingEnvelope } from "@/lib/finding-display"
import type { JobSummary } from "@/lib/types"
import { Badge } from "@/vendor/gui/ui/badge"
import { CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { PageSection } from "@/components/page-section"

type InvestigationFindingsProps = {
  findings: Record<string, unknown>[]
  completedPersonas?: string[]
  jobs?: JobSummary[]
  embedded?: boolean
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function FindingsBody({
  findings,
  completedPersonas = [],
  jobs = [],
}: InvestigationFindingsProps) {
  const displayFindings = dedupeFindingsByPersona(findings)

  if (displayFindings.length === 0) {
    const personasFinished = completedPersonas.length > 0
    const completedJobs = jobs.filter((job) => job.status === "completed")
    return (
      <p className="text-muted-foreground text-sm">
        {personasFinished
          ? completedJobs.length > 0
            ? "Workers finished but no structured results were stored. Check external Langfuse or raw_response."
            : "Workers finished but no structured results were stored for this work order."
          : "No findings yet. Results appear here when a worker completes."}
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {displayFindings.map((item, index) => {
        const persona = asString(item.persona) || "agent"
        const { body, evidenceManifest } = findingEnvelope(item)
        return (
          <div key={`${persona}-${index}`} className="space-y-3">
            <div className="flex items-center gap-2">
              <Badge variant="outline">{persona}</Badge>
              {asString(item.job_id) ? (
                <span className="text-muted-foreground text-xs">{asString(item.job_id)}</span>
              ) : null}
            </div>
            <FindingContent data={body} evidenceManifest={evidenceManifest} />
          </div>
        )
      })}
    </div>
  )
}

export function InvestigationFindings({
  findings,
  completedPersonas = [],
  jobs = [],
  embedded = false,
}: InvestigationFindingsProps) {
  if (embedded) {
    return <FindingsBody findings={findings} completedPersonas={completedPersonas} jobs={jobs} />
  }

  return (
    <PageSection>
      <CardHeader>
        <CardTitle>Results</CardTitle>
      </CardHeader>
      <CardContent>
        <FindingsBody findings={findings} completedPersonas={completedPersonas} jobs={jobs} />
      </CardContent>
    </PageSection>
  )
}
