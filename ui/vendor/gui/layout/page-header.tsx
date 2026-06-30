"use client"

import Link from "next/link"
import type { ReactNode } from "react"
import { MotionFadeIn } from "@/vendor/gui/motion"
import { TypographyH2, pageHeaderHairlineClassName } from "@/vendor/gui/ui/typography"
import { cn } from "@/vendor/gui/utils"

export function PageHeader({
  title,
  description,
  actions,
  backHref,
  backLabel = "Назад",
  className,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
  backHref?: string
  backLabel?: string
  className?: string
}) {
  return (
    <MotionFadeIn className={cn("flex flex-col gap-1", className)}>
      {backHref && (
        <Link href={backHref} className="text-sm text-muted-foreground hover:underline">
          ← {backLabel}
        </Link>
      )}
      <div
        className={cn(
          "flex flex-col gap-3 pb-3 sm:flex-row sm:items-start sm:justify-between",
          pageHeaderHairlineClassName
        )}
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <TypographyH2>{title}</TypographyH2>
          {description && (
            <div className="text-muted-foreground text-sm">{description}</div>
          )}
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-2 sm:shrink-0 sm:justify-end">
            {actions}
          </div>
        )}
      </div>
    </MotionFadeIn>
  )
}
