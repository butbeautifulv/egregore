"use client"

import { useState } from "react"

import type { InteractionMode } from "@/lib/run-api"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"

type RunTimelineProps = {
  runId: string
  steps: Array<{ label: string; payload: Record<string, unknown>; ts?: string }>
  mode?: InteractionMode
}

export function RunTimeline({ runId, steps, mode }: RunTimelineProps) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  async function copyPayload(payload: Record<string, unknown>) {
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
  }

  return (
    <Card className="ring-1 ring-foreground/10">
      <CardHeader>
        <CardTitle>
          Run timeline — {runId}
          {mode === "debug" ? <span className="text-muted-foreground ml-2 text-xs font-normal">debug</span> : null}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {steps.length === 0 ? (
          <EmptyTableState title="No steps yet" description="Session steps will appear here." />
        ) : (
          <ul className="flex flex-col gap-2">
            {steps.map((step, index) => (
              <li key={`${step.label}-${index}`} className="rounded-md border p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{step.label}</span>
                  <div className="flex items-center gap-2">
                    {step.ts ? <span className="text-muted-foreground">{step.ts}</span> : null}
                    {mode === "debug" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => copyPayload(step.payload)}
                      >
                        Copy JSON
                      </Button>
                    ) : null}
                  </div>
                </div>
                {mode === "debug" ? (
                  <Collapsible
                    open={expanded[index] ?? false}
                    onOpenChange={(open) => setExpanded((prev) => ({ ...prev, [index]: open }))}
                  >
                    <CollapsibleTrigger className="text-primary mt-2 hover:underline">
                      Raw payload
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <pre className="text-muted-foreground mt-2 overflow-x-auto text-xs">
                        {JSON.stringify(step.payload, null, 2)}
                      </pre>
                    </CollapsibleContent>
                  </Collapsible>
                ) : (
                  <p className="text-muted-foreground mt-2">
                    {typeof step.payload.summary === "string"
                      ? step.payload.summary
                      : step.payload.status
                        ? String(step.payload.status)
                        : "Step completed"}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
