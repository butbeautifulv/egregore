"use client"

import { JsonPayloadView } from "@/components/json-payload-view"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/vendor/gui/ui/card"

export function WorkOrderIntakeCard({
  intake,
  profileId,
}: {
  intake?: Record<string, unknown> | null
  profileId?: string | null
}) {
  if (!intake || Object.keys(intake).length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Request context</CardTitle>
        <CardDescription>
          Structured input for the work order
          {profileId ? ` · profile ${profileId}` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <JsonPayloadView data={intake} title="Context" />
      </CardContent>
    </Card>
  )
}
