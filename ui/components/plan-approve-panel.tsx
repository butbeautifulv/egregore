"use client"

import type { WorkPlan } from "@/lib/run-api"
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
import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import { Spinner } from "@/vendor/gui/ui/spinner"

type PlanApprovePanelProps = {
  plan: WorkPlan
  loading?: boolean
  onApprove: () => void
  onReject: () => void
}

export function PlanApprovePanel({ plan, loading, onApprove, onReject }: PlanApprovePanelProps) {
  return (
    <Card className="ring-1 ring-foreground/10">
      <CardHeader>
        <CardTitle>Work plan review</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {plan.rationale ? <p className="text-sm">{plan.rationale}</p> : null}
        {plan.proposed_workers?.length ? (
          <div>
            <p className="text-muted-foreground mb-1 text-xs font-medium">Proposed workers</p>
            <p className="text-sm">{plan.proposed_workers.join(", ")}</p>
          </div>
        ) : null}
        {plan.todos?.length ? (
          <div>
            <p className="text-muted-foreground mb-2 text-xs font-medium">Steps</p>
            <ol className="flex flex-col gap-2">
              {plan.todos.map((todo, index) => (
                <li key={todo.id} className="rounded-md border px-3 py-2 text-sm">
                  <span className="text-muted-foreground mr-2">{index + 1}.</span>
                  {todo.content}
                </li>
              ))}
            </ol>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="button" disabled={loading} onClick={onApprove}>
            {loading ? <Spinner data-icon="inline-start" /> : null}
            Approve
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button type="button" variant="outline" disabled={loading}>
                Reject
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Reject work plan?</AlertDialogTitle>
                <AlertDialogDescription>
                  The conductor will not proceed with the proposed plan until a new one is generated.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={onReject}>Reject plan</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  )
}
