"use client"

import { useState } from "react"

import { resumeJob } from "@/lib/api-client"
import type { PendingApproval } from "@/lib/types"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

export function ApprovalActions({ approval }: { approval: PendingApproval }) {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function decide(decision: "approve" | "reject") {
    setLoading(true)
    setMessage(null)
    try {
      await resumeJob(approval.job_id, {
        decision,
        approval_id: approval.approval_id,
        actor: "operator-ui",
      })
      setMessage(decision === "approve" ? "Approved" : "Rejected")
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "Action failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {approval.persona} · {approval.tool_name}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-muted-foreground text-xs">Job {approval.job_id}</p>
        <pre className="bg-muted overflow-x-auto rounded-none p-2 text-xs">
          {JSON.stringify(approval.tool_args, null, 2)}
        </pre>
        <div className="flex gap-2">
          <Button disabled={loading} onClick={() => decide("approve")}>
            Approve
          </Button>
          <Button variant="outline" disabled={loading} onClick={() => decide("reject")}>
            Reject
          </Button>
        </div>
        {message ? <p className="text-xs">{message}</p> : null}
      </CardContent>
    </Card>
  )
}
