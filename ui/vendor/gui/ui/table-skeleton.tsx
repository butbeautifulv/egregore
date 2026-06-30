import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/vendor/gui/ui/table"
import { Skeleton } from "@/vendor/gui/ui/skeleton"
import { cn } from "@/vendor/gui/utils"

function TableSkeletonRow({ columns }: { columns: number }) {
  return (
    <TableRow>
      {Array.from({ length: columns }).map((_, i) => (
        <TableCell key={i} className="h-10">
          <Skeleton className="h-3 w-full max-w-full" />
        </TableCell>
      ))}
    </TableRow>
  )
}

export function TableSkeleton({
  columns = 5,
  rows = 10,
  headers,
  className,
}: {
  columns?: number
  rows?: number
  headers?: string[]
  className?: string
}) {
  const columnCount = headers?.length ?? columns

  return (
    <div className={cn("min-w-0", className)}>
      <Table className="w-full table-fixed">
        <TableHeader>
          <TableRow>
            {headers
              ? headers.map((h) => <TableHead key={h}>{h}</TableHead>)
              : Array.from({ length: columnCount }).map((_, i) => (
                  <TableHead key={i}>
                    <Skeleton className="h-3 w-16 max-w-full" />
                  </TableHead>
                ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: rows }).map((_, idx) => (
            <TableSkeletonRow key={idx} columns={columnCount} />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
