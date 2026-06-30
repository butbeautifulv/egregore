import type { JobSummary } from "@/lib/types"
import { Badge } from "@/vendor/gui/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

const LANGFUSE_HOST = process.env.NEXT_PUBLIC_LANGFUSE_HOST ?? "http://localhost:3000"

export function JobCard({ job }: { job: JobSummary }) {
  const traceUrl = `${LANGFUSE_HOST}/traces?search=${encodeURIComponent(job.session_id)}`

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-base">{job.persona}</CardTitle>
        <Badge variant="outline">{job.status}</Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p className="text-muted-foreground">Job ID: {job.job_id}</p>
        <p className="text-muted-foreground">Session: {job.session_id}</p>
        <a className="text-primary text-xs hover:underline" href={traceUrl} rel="noreferrer" target="_blank">
          Open in Langfuse
        </a>
      </CardContent>
    </Card>
  )
}
