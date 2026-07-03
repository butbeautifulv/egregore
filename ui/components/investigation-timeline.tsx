"use client"

import type { StatusStreamEvent } from "@/lib/types"
import { eventSummary, matchesInvestigation } from "@/lib/status-events"
import { MotionStagger, MotionStaggerItem } from "@/vendor/gui/motion"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { PageSection } from "@/components/page-section"
import { CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

type InvestigationTimelineProps = {
  investigationId: string
  events: StatusStreamEvent[]
}

export function InvestigationTimeline({ investigationId, events }: InvestigationTimelineProps) {
  const filtered = events.filter((event) => matchesInvestigation(event, investigationId))

  return (
    <PageSection>
      <CardHeader>
        <CardTitle>Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        {filtered.length === 0 ? (
          <EmptyTableState
            title="Waiting for events"
            description="Stream events for this investigation appear here."
          />
        ) : (
          <MotionStagger className="flex flex-col gap-1">
            {filtered
              .slice()
              .reverse()
              .map((event, index) => (
                <MotionStaggerItem key={`${event.ts}-${index}`}>
                  <div className="flex items-baseline justify-between gap-3 border-b py-2 text-xs last:border-0">
                    <div className="min-w-0 flex-1">
                      <span className="font-medium">{event.kind}</span>
                      <span className="text-muted-foreground ml-2 truncate">
                        {eventSummary(event.payload)}
                      </span>
                    </div>
                    <time className="text-muted-foreground shrink-0 tabular-nums">{event.ts}</time>
                  </div>
                </MotionStaggerItem>
              ))}
          </MotionStagger>
        )}
      </CardContent>
    </PageSection>
  )
}
