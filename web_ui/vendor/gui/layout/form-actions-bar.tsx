import { cn } from "@/vendor/gui/utils"
import { FormErrorSlot } from "@/vendor/gui/layout/form-error-slot"

export function FormActionsBar({
  error,
  children,
  className,
}: {
  error?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <FormErrorSlot error={error} />
      <div className="flex gap-2 sm:ml-auto">{children}</div>
    </div>
  )
}
