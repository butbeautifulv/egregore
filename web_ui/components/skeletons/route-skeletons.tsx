import { Skeleton } from "@/vendor/gui/ui/skeleton"

import {
  AgentChatBlockSkeleton,
  ChartCardsGridSkeleton,
  ChatFormCardSkeleton,
  ChatThreadSkeleton,
  CodeBlockSkeleton,
  FindingCardSkeleton,
  InfraBannerSkeleton,
  LoginFormSkeleton,
  MemoryFeedSkeleton,
  PageContentShell,
  PageHeaderSkeleton,
  PageHeaderWithActionsSkeleton,
  TableRowsSkeleton,
  TableToolbarSkeleton,
  TabsListSkeleton,
  TwoColumnCardsSkeleton,
} from "@/components/skeletons/primitives"

export type EgregoreRouteSkeletonVariant =
  | "home"
  | "investigation"
  | "catalog"
  | "catalog-agent"
  | "catalog-memory"
  | "catalog-memory-feed"
  | "table"
  | "login"

export function EgregoreRouteSkeleton({ variant }: { variant: EgregoreRouteSkeletonVariant }) {
  return (
    <PageContentShell>
      {variant === "login" ? (
        <LoginFormSkeleton />
      ) : (
        <>
          {variant === "investigation" || variant === "catalog-agent" || variant === "catalog-memory" ? (
            <PageHeaderWithActionsSkeleton />
          ) : (
            <PageHeaderSkeleton />
          )}

          {variant === "home" ? (
            <>
              <InfraBannerSkeleton />
              <ChatFormCardSkeleton />
              <ChartCardsGridSkeleton />
              <TableToolbarSkeleton />
              <TableRowsSkeleton rows={8} />
            </>
          ) : null}

          {variant === "investigation" ? (
            <>
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between gap-2">
                  <Skeleton className="h-4 w-36" />
                  <Skeleton className="h-8 w-40" />
                </div>
                <FindingCardSkeleton />
                <FindingCardSkeleton />
              </div>
              <ChatThreadSkeleton />
              <div className="border p-4">
                <Skeleton className="mb-3 h-5 w-28" />
                <CodeBlockSkeleton />
              </div>
            </>
          ) : null}

          {variant === "catalog" ? (
            <>
              <TabsListSkeleton />
              <TableToolbarSkeleton />
              <TableRowsSkeleton rows={10} />
            </>
          ) : null}

          {variant === "catalog-agent" ? (
            <>
              <TwoColumnCardsSkeleton />
              <TabsListSkeleton count={4} />
              <CodeBlockSkeleton className="min-h-64" />
            </>
          ) : null}

          {variant === "catalog-memory" ? (
            <>
              <div className="flex flex-wrap gap-2">
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-6 w-20" />
              </div>
              <div className="flex flex-wrap gap-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 w-48" />
              </div>
              <CodeBlockSkeleton className="min-h-48" />
            </>
          ) : null}

          {variant === "catalog-memory-feed" ? <MemoryFeedSkeleton /> : null}

          {variant === "table" ? (
            <>
              <TableToolbarSkeleton />
              <TableRowsSkeleton rows={8} />
            </>
          ) : null}
        </>
      )}
    </PageContentShell>
  )
}

/** Catalog workspace body only (no page header). */
export function CatalogWorkspaceSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-end">
        <Skeleton className="h-8 w-32" />
      </div>
      <TabsListSkeleton />
      <TableToolbarSkeleton />
      <TableRowsSkeleton rows={10} />
    </div>
  )
}

/** Home async panel body (no page header). */
export function InvestigationsPanelSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <InfraBannerSkeleton />
      <ChatFormCardSkeleton />
      <ChartCardsGridSkeleton />
      <TableToolbarSkeleton />
      <TableRowsSkeleton rows={8} />
    </div>
  )
}
