"use client"

import { MotionFadeIn } from "@/vendor/gui/motion"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/vendor/gui/ui/empty"

export function EmptyTableState({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children?: React.ReactNode
}) {
  return (
    <MotionFadeIn>
      <Empty className="border-0 py-12">
        <EmptyHeader>
          <EmptyTitle>{title}</EmptyTitle>
          {description && <EmptyDescription>{description}</EmptyDescription>}
        </EmptyHeader>
        {children && <EmptyContent>{children}</EmptyContent>}
      </Empty>
    </MotionFadeIn>
  )
}

