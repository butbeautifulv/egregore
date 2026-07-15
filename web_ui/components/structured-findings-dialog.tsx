"use client"

import { useState } from "react"
import { Maximize2Icon } from "lucide-react"

import { InvestigationFindings } from "@/components/investigation-findings"
import type { JobSummary } from "@/lib/types"
import { Button } from "@/vendor/gui/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/vendor/gui/ui/dialog"
import { ScrollArea } from "@/vendor/gui/ui/scroll-area"

export function StructuredFindingsDialog({
  findings,
  completedPersonas = [],
  jobs = [],
}: {
  findings: Record<string, unknown>[]
  completedPersonas?: string[]
  jobs?: JobSummary[]
}) {
  const [open, setOpen] = useState(false)

  if (findings.length === 0) {
    return null
  }

  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)}>
        <Maximize2Icon data-icon="inline-start" />
        Structured findings ({findings.length})
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-[calc(100%-2rem)] gap-4 sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>Structured findings</DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[min(75vh,760px)] pr-4">
            <InvestigationFindings
              findings={findings}
              completedPersonas={completedPersonas}
              jobs={jobs}
              embedded
            />
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </>
  )
}
