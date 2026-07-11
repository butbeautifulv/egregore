import Link from "next/link"
import { ChevronRightIcon } from "lucide-react"
import { Button } from "@/vendor/gui/ui/button"

export function DataTableRowLink({
  href,
  label = "Открыть",
}: {
  href: string
  label?: string
}) {
  return (
    <Button variant="outline" size="icon-xs" asChild>
      <Link href={href} aria-label={label}>
        <ChevronRightIcon />
      </Link>
    </Button>
  )
}
