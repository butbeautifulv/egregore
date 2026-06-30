"use client"

import type { StatusStreamEvent } from "@/lib/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

type InvestigationTimelineProps = {
  investigationId: string
  events: StatusStreamEvent[]
}

function matchesInvestigation(event: StatusStreamEvent, investigationId: string): boolean {
  const payload = event.payload
  const candidates = [
    payload.correlation_id,
    payload.investigation_id,
    (payload.event as Record<string, unknown> | undefined)?.correlation_id,
  ]
  return candidates.some((value) => typeof value === "string" && value === investigationId)
}

export function InvestigationTimeline({ investigationId, events }: InvestigationTimelineProps) {
  const filtered = events.filter((event) => matchesInvestigation(event, investigationId))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Live timeline</CardTitle>
      </CardHeader>
      <CardContent>
        {filtered.length === 0 ? (
          <p className="text-muted-foreground text-sm">Waiting for stream events…</p>
        ) : (
          <ul className="space-y-2">
            {filtered
              .slice()
              .reverse()
              .map((event, index) => (
                <li key={`${event.ts}-${index}`} className="rounded-md border p-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{event.kind}</span>
                    <span className="text-muted-foreground text-xs">{event.ts}</span>
                  </div>
                  <pre className="text-muted-foreground mt-1 overflow-x-auto text-xs">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </li>
              ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
