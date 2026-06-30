import type { StatusSnapshot } from "@/lib/api-client"

import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

export function StatusCards({ status }: { status: StatusSnapshot }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Events</CardTitle>
        </CardHeader>
        <CardContent className="text-2xl font-semibold">{status.events_count}</CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Findings</CardTitle>
        </CardHeader>
        <CardContent className="text-2xl font-semibold">{status.findings_count}</CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Latest narrative</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm">
          {status.latest_narrative || "—"}
        </CardContent>
      </Card>
    </div>
  )
}
