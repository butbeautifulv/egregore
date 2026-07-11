import { Skeleton } from "@/vendor/gui/ui/skeleton"
import { cn } from "@/vendor/gui/utils"

export function PageContentShell({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={cn("flex flex-col gap-4 md:gap-6", className)}>{children}</div>
}

export function PageHeaderSkeleton() {
  return (
    <div className="flex flex-col gap-3 pb-3">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-72 max-w-full" />
    </div>
  )
}

export function StatCardsGridSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton key={index} className="h-24 w-full" />
      ))}
    </div>
  )
}

export function ChartCardsGridSkeleton({ count = 2 }: { count?: number }) {
  return (
    <div className="grid gap-4 @2xl/main:grid-cols-2">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="flex flex-col border">
          <div className="flex items-center justify-between gap-2 border-b p-4">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="size-8" />
          </div>
          <div className="p-4">
            <Skeleton className="h-72 w-full" />
            <Skeleton className="mt-4 h-14 w-full" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function TableToolbarSkeleton() {
  return <Skeleton className="h-9 w-full max-w-lg" />
}

export function TableRowsSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  )
}

export function DetailCardsSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-4">
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton key={index} className="h-32 w-full" />
      ))}
    </div>
  )
}

export function FormCardSkeleton() {
  return (
    <div className="flex flex-col gap-3 border p-4">
      <Skeleton className="h-5 w-40" />
      <Skeleton className="h-4 w-64 max-w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-28" />
    </div>
  )
}
