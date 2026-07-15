import type { JobSummary } from "@/lib/types"
import { Badge } from "@/vendor/gui/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

function langfuseHost(): string {
  return (process.env.NEXT_PUBLIC_LANGFUSE_HOST || "http://localhost:3001").replace(/\/$/, "")
}

function traceSearchUrl(job: JobSummary): string {
  const query = `job:${job.job_id}`
  return `${langfuseHost()}/traces?search=${encodeURIComponent(query)}`
}

export function JobCard({ job }: { job: JobSummary }) {
  const traceUrl = traceSearchUrl(job)
  const showTraceLink = Boolean(job.session_id)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>{job.persona}</CardTitle>
        <Badge variant="outline">{job.status}</Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <p className="text-muted-foreground">Job ID: {job.job_id}</p>
        <p className="text-muted-foreground">Session: {job.session_id || "—"}</p>
        {showTraceLink ? (
          <a className="text-primary text-xs hover:underline" href={traceUrl} rel="noreferrer" target="_blank">
            Open in Langfuse
          </a>
        ) : (
          <p className="text-muted-foreground">Trace link available when the job starts running.</p>
        )}
      </CardContent>
    </Card>
  )
}
