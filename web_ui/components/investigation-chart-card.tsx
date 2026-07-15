"use client"

import { useState, type ReactNode } from "react"
import { Maximize2Icon } from "lucide-react"

import { Button } from "@/vendor/gui/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/vendor/gui/ui/dialog"
import { cn } from "@/vendor/gui/utils"

export function InvestigationChartCard({
  title,
  className,
  expandable = true,
  children,
  renderExpanded,
}: {
  title: string
  className?: string
  expandable?: boolean
  children: ReactNode
  renderExpanded: () => ReactNode
}) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Card className={cn("flex h-full flex-col", className)}>
        <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
          <CardTitle className="text-sm">{title}</CardTitle>
          {expandable ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setOpen(true)}
              aria-label={`Expand chart: ${title}`}
            >
              <Maximize2Icon />
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="flex flex-1 flex-col pt-0">{children}</CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-[calc(100%-2rem)] gap-4 sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className={cn("w-full min-w-0", expandable && "min-h-[420px]")}>
            {renderExpanded()}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
