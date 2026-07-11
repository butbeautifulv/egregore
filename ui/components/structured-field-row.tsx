import { cn } from "@/vendor/gui/utils"

export function StructuredFieldRow({
  title,
  action,
  children,
  className,
}: {
  title?: string
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("border p-3", className)}>
      {title || action ? (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          {title ? <p className="text-xs font-medium">{title}</p> : null}
          {action}
        </div>
      ) : null}
      {children}
    </div>
  )
}
