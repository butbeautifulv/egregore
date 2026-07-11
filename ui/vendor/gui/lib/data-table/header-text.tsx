import type { ReactNode } from "react"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { cn } from "@/vendor/gui/utils"

export function TableHeaderText({
  text,
  className,
}: {
  text: string
  className?: string
}) {
  return (
    <OverflowText className={cn("w-full min-w-0", className)}>{text}</OverflowText>
  )
}

export function wrapTableHeaderContent(content: ReactNode): ReactNode {
  if (typeof content === "string" || typeof content === "number") {
    return <TableHeaderText text={String(content)} />
  }

  return content
}
