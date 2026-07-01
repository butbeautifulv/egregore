import type { StatusSnapshot } from "@/lib/api-client"

import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

export function StatusCards({ status }: { status: StatusSnapshot }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>Events</CardTitle>
        </CardHeader>
        <CardContent className="text-2xl font-semibold">{status.events_count}</CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Findings</CardTitle>
        </CardHeader>
        <CardContent className="text-2xl font-semibold">{status.findings_count}</CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Latest narrative</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground text-xs">
          {status.latest_narrative || "—"}
        </CardContent>
      </Card>
    </div>
  )
}
