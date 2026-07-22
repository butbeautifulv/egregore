"use client"

import { useState } from "react"

import { resumeHitlApproval, formatHitlResumeError } from "@/lib/hitl-resume"
import type { PendingApproval } from "@/lib/types"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/vendor/gui/ui/alert-dialog"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { Badge } from "@/vendor/gui/ui/badge"
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"
import { Spinner } from "@/vendor/gui/ui/spinner"

function riskVariant(risk: string): "default" | "secondary" | "destructive" | "outline" {
  const level = risk.toLowerCase()
  if (level.includes("high") || level.includes("critical")) {
    return "destructive"
  }
  if (level.includes("medium")) {
    return "secondary"
  }
  return "outline"
}

export function ApprovalActions({
  approval,
  compact = false,
}: {
  approval: PendingApproval
  compact?: boolean
}) {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function decide(decision: "approve" | "reject") {
    setLoading(true)
    setMessage(null)
    setError(null)
    try {
      await resumeHitlApproval(approval, decision, "operator-ui")
      setMessage(decision === "approve" ? "Approved" : "Rejected")
    } catch (exc) {
      setError(formatHitlResumeError(exc, "Action failed"))
    } finally {
      setLoading(false)
    }
  }

  if (compact) {
    return (
      <div className="flex flex-wrap gap-1">
        <Button size="sm" disabled={loading} onClick={() => void decide("approve")}>
          Approve
        </Button>
        <Button size="sm" variant="outline" disabled={loading} onClick={() => void decide("reject")}>
          Reject
        </Button>
        {message ? <span className="text-primary self-center text-xs">{message}</span> : null}
        {error ? <span className="text-destructive self-center text-xs">{error}</span> : null}
      </div>
    )
  }

  return (
    <Card className="ring-1 ring-foreground/10">
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <CardTitle className="text-base">
          {approval.persona} · {approval.tool_name}
        </CardTitle>
        <Badge variant={riskVariant(approval.risk_level)}>{approval.risk_level}</Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-muted-foreground text-xs">Job {approval.job_id}</p>
        <Collapsible>
          <CollapsibleTrigger className="text-primary text-xs hover:underline">
            Tool arguments
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="bg-muted mt-2 overflow-x-auto rounded-md p-2 text-xs">
              {JSON.stringify(approval.tool_args, null, 2)}
            </pre>
          </CollapsibleContent>
        </Collapsible>
        <div className="flex flex-wrap gap-2">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button disabled={loading}>
                {loading ? <Spinner data-icon="inline-start" /> : null}
                Approve
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Approve tool execution?</AlertDialogTitle>
                <AlertDialogDescription>
                  Allow {approval.persona} to run {approval.tool_name} with the configured arguments.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => decide("approve")}>Approve</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" disabled={loading}>
                Reject
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Reject tool execution?</AlertDialogTitle>
                <AlertDialogDescription>
                  The job will resume without running {approval.tool_name}.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => decide("reject")}>Reject</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
        {message ? <p className="text-xs text-primary">{message}</p> : null}
        {error ? <ApiErrorAlert error={error} fallback="Action failed" /> : null}
      </CardContent>
    </Card>
  )
}
