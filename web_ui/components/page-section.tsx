import type { ReactNode } from "react"

import { Card } from "@/vendor/gui/ui/card"
import { cn } from "@/vendor/gui/utils"

export function PageSection({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <Card className={cn("ring-1 ring-foreground/10", className)}>{children}</Card>
}
