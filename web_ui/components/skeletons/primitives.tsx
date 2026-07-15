import { Skeleton } from "@/vendor/gui/ui/skeleton"
import { cn } from "@/vendor/gui/utils"

export {
  ChartCardsGridSkeleton,
  DetailCardsSkeleton,
  FormCardSkeleton,
  PageContentShell,
  PageHeaderSkeleton,
  StatCardsGridSkeleton,
  TableRowsSkeleton,
  TableToolbarSkeleton,
} from "@/vendor/gui/shared/skeletons/primitives"

export function PageHeaderWithActionsSkeleton() {
  return (
    <div className="flex flex-col gap-3 pb-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-56 max-w-full" />
        <Skeleton className="h-4 w-40 max-w-full" />
      </div>
      <div className="flex flex-wrap gap-2">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-6 w-28" />
      </div>
    </div>
  )
}

export function InfraBannerSkeleton() {
  return <Skeleton className="h-10 w-full" />
}

export function ChatFormCardSkeleton() {
  return (
    <div className="flex flex-col gap-3 border p-4">
      <Skeleton className="h-5 w-44" />
      <Skeleton className="h-4 w-80 max-w-full" />
      <Skeleton className="min-h-24 w-full" />
      <Skeleton className="h-9 w-full" />
    </div>
  )
}

export function TabsListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="flex flex-wrap gap-2 border-b pb-2">
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton key={index} className="h-8 w-20" />
      ))}
    </div>
  )
}

export function TwoColumnCardsSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {Array.from({ length: 2 }).map((_, index) => (
        <div key={index} className="flex flex-col gap-3 border p-4">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ))}
    </div>
  )
}

export function CodeBlockSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col gap-2 border p-3", className)}>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-5/6" />
      <Skeleton className="h-3 w-4/6" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}

export function FindingCardSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-4 w-32" />
      </div>
      <div className="bg-muted/40 space-y-3 border p-4">
        <div className="flex flex-wrap gap-2">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-5 w-28" />
        </div>
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
      </div>
    </div>
  )
}

export function AgentChatBlockSkeleton() {
  return (
    <div className="flex w-full max-w-2xl flex-col gap-2">
      <div className="flex items-center gap-2">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-5 w-14" />
      </div>
      <div className="bg-muted/40 space-y-3 border px-4 py-3">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-20 w-full" />
      </div>
    </div>
  )
}

export function ChatThreadSkeleton() {
  return (
    <div className="border">
      <div className="flex flex-col gap-5 p-4">
        <div className="flex justify-end">
          <Skeleton className="h-16 w-full max-w-md" />
        </div>
        <AgentChatBlockSkeleton />
        <AgentChatBlockSkeleton />
      </div>
      <div className="space-y-2 border-t p-4">
        <Skeleton className="min-h-20 w-full" />
        <div className="flex justify-between gap-2">
          <Skeleton className="h-3 w-64 max-w-[70%]" />
          <Skeleton className="h-8 w-32" />
        </div>
      </div>
    </div>
  )
}

export function MemoryEntrySkeleton() {
  return (
    <div className="space-y-2 border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-4 w-32" />
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-5/6" />
    </div>
  )
}

export function MemoryFeedSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:max-w-2xl">
        <div className="space-y-2">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-9 w-full" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-9 w-full" />
        </div>
      </div>
      <div className="flex flex-col gap-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <MemoryEntrySkeleton key={index} />
        ))}
      </div>
    </div>
  )
}

export function LoginFormSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-9 w-full" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-9 w-full" />
      </div>
      <Skeleton className="h-9 w-full" />
    </div>
  )
}
