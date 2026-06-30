import { cn } from "@/vendor/gui/utils"

const formControlWidthRules = [
  "[&_[data-slot=card-content]_input]:w-full",
  "[&_[data-slot=card-content]_textarea]:w-full",
  "[&_[data-slot=card-content]_[data-slot=select-trigger]]:w-full",
  "[&_[data-slot=card-content]_[data-slot=select-trigger]]:max-w-none",
] as const

const formCardLayoutRules = [
  "[&>[data-slot=card]]:h-full",
  "[&_[data-slot=card-content]]:flex [&_[data-slot=card-content]]:min-h-0 [&_[data-slot=card-content]]:flex-1 [&_[data-slot=card-content]]:flex-col",
] as const

/** Width of one column in the default two-column form grid (gap-4). */
export const FORM_CARD_SINGLE_COLUMN_CLASS = "w-full lg:max-w-[calc((100%-1rem)/2)]"

/** Pin card actions (e.g. a lone button) to the bottom when the sibling card is taller. */
export function FormCardAction({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={cn("mt-auto", className)}>{children}</div>
}

/** Two-column card layout for panel forms. Controls inside cards stretch to full card width. */
export function FormCardGrid({
  children,
  className,
  singleCard = false,
}: {
  children: React.ReactNode
  className?: string
  /** One card in the left column only — use 1-col grid inside the constrained width. */
  singleCard?: boolean
}) {
  return (
    <div
      className={cn(
        "grid gap-4",
        singleCard ? "grid-cols-1" : "lg:grid-cols-2",
        formCardLayoutRules,
        formControlWidthRules,
        className
      )}
    >
      {children}
    </div>
  )
}

/**
 * Wraps form cards and actions. With `singleCard`, constrains width to the left
 * grid column so the actions bar aligns with the card's right edge.
 */
export function FormCardLayout({
  children,
  actions,
  singleCard = false,
  className,
}: {
  children: React.ReactNode
  actions?: React.ReactNode
  singleCard?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4",
        singleCard && FORM_CARD_SINGLE_COLUMN_CLASS,
        className
      )}
    >
      <FormCardGrid singleCard={singleCard}>{children}</FormCardGrid>
      {actions}
    </div>
  )
}
