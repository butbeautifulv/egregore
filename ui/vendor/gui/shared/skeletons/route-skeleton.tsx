import {
  DetailCardsSkeleton,
  FormCardSkeleton,
  PageContentShell,
  PageHeaderSkeleton,
  StatCardsGridSkeleton,
  TableRowsSkeleton,
  TableToolbarSkeleton,
} from "@/vendor/gui/shared/skeletons/primitives"

export type RouteSkeletonVariant = "home" | "table" | "detail" | "form" | "runs"

export function RouteSkeleton({ variant }: { variant: RouteSkeletonVariant }) {
  return (
    <PageContentShell>
      <PageHeaderSkeleton />
      {variant === "home" ? (
        <>
          <FormCardSkeleton />
          <TableToolbarSkeleton />
          <TableRowsSkeleton />
          <StatCardsGridSkeleton />
        </>
      ) : null}
      {variant === "table" ? (
        <>
          <TableToolbarSkeleton />
          <TableRowsSkeleton />
        </>
      ) : null}
      {variant === "detail" ? <DetailCardsSkeleton /> : null}
      {variant === "form" ? (
        <>
          <FormCardSkeleton />
          <DetailCardsSkeleton count={2} />
        </>
      ) : null}
      {variant === "runs" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <FormCardSkeleton />
          <DetailCardsSkeleton count={2} />
        </div>
      ) : null}
    </PageContentShell>
  )
}
