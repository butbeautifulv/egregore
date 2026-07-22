"use client"

import { useEffect, useState } from "react"
import { ShieldAlertIcon } from "lucide-react"

import { claimAutoApprove, isChatAutoApproveEnabled } from "@/lib/hitl-auto-approve"
import { formatHitlResumeError, resumeHitlApproval } from "@/lib/hitl-resume"
import type { AgentChatEntry } from "@/lib/types"
import { ApiErrorAlert } from "@/components/api-error-alert"
import { Badge } from "@/vendor/gui/ui/badge"
import { Button } from "@/vendor/gui/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"
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
import { Spinner } from "@/vendor/gui/ui/spinner"

function riskVariant(risk: string): "default" | "secondary" | "destructive" | "outline" {
  const level = risk.toLowerCase()
  if (level.includes("high") || level.includes("critical")) return "destructive"
  if (level.includes("medium")) return "secondary"
  return "outline"
}

export function HitlApprovalBlock({
  entry,
  autoApprove = false,
  onResolved,
}: {
  entry: AgentChatEntry
  autoApprove?: boolean
  onResolved?: (status: "approved" | "rejected") => void
}) {
  const hitl = entry.hitl
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const shouldAutoApprove =
    autoApprove && isChatAutoApproveEnabled() && hitl?.status === "pending"

  useEffect(() => {
    if (!shouldAutoApprove || !hitl || done || loading) return
    if (!claimAutoApprove(hitl.approvalId)) return

    let cancelled = false
    setLoading(true)
    setMessage("Auto-approving…")
    void resumeHitlApproval(
      { job_id: entry.jobId, approval_id: hitl.approvalId },
      "approve",
      "chat-auto-approve",
    )
      .then(() => {
        if (cancelled) return
        hitl.status = "approved"
        setMessage("Auto-approved — agent resuming")
        setDone(true)
        onResolved?.("approved")
      })
      .catch((exc) => {
        if (cancelled) return
        setError(formatHitlResumeError(exc))
        setMessage(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [shouldAutoApprove, hitl?.approvalId, hitl?.status, done, loading, entry.jobId, onResolved])

  if (done || !hitl || hitl.status !== "pending") {
    return null
  }

  async function decide(decision: "approve" | "reject") {
    if (!hitl || !claimAutoApprove(hitl.approvalId)) return
    setLoading(true)
    setMessage(null)
    setError(null)
    try {
      await resumeHitlApproval(
        { job_id: entry.jobId, approval_id: hitl.approvalId },
        decision,
      )
      hitl.status = decision === "approve" ? "approved" : "rejected"
      setMessage(decision === "approve" ? "Approved — agent resuming" : "Rejected")
      setDone(true)
      onResolved?.(hitl.status)
    } catch (exc) {
      setError(formatHitlResumeError(exc))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-muted/40 space-y-3 border border-destructive/30 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <ShieldAlertIcon className="text-destructive size-4" />
        <span className="text-sm font-medium">
          {shouldAutoApprove ? "Auto-approval" : "Approval required"}
        </span>
        <Badge variant={riskVariant(hitl.riskLevel)}>{hitl.riskLevel || "risk"}</Badge>
      </div>
      <p className="text-muted-foreground text-xs">
        Allow <span className="text-foreground font-medium">{entry.persona}</span> to run{" "}
        <span className="text-foreground font-medium">{hitl.toolName}</span>?
      </p>
      <Collapsible>
        <CollapsibleTrigger className="text-primary text-xs hover:underline">Tool arguments</CollapsibleTrigger>
        <CollapsibleContent>
          <pre className="bg-muted mt-2 overflow-x-auto rounded-md p-2 text-xs">
            {JSON.stringify(hitl.toolArgs, null, 2)}
          </pre>
        </CollapsibleContent>
      </Collapsible>
      {shouldAutoApprove ? (
        <div className="flex items-center gap-2 text-xs">
          {loading ? <Spinner className="size-3" /> : null}
          <span className="text-muted-foreground">{message ?? "Waiting to auto-approve…"}</span>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" disabled={loading}>
                {loading ? <Spinner data-icon="inline-start" /> : null}
                Approve
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Approve tool execution?</AlertDialogTitle>
                <AlertDialogDescription>
                  Allow {entry.persona} to run {hitl.toolName} with the configured arguments.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => void decide("approve")}>Approve</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" variant="outline" disabled={loading}>
                Reject
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Reject tool execution?</AlertDialogTitle>
                <AlertDialogDescription>
                  The agent will continue without running {hitl.toolName}.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => void decide("reject")}>Reject</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      )}
      {message && !shouldAutoApprove ? <p className="text-primary text-xs">{message}</p> : null}
      {error ? <ApiErrorAlert error={error} fallback="Action failed" /> : null}
    </div>
  )
}
