import Link from "next/link"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { cn } from "@/vendor/gui/utils"

export function TruncatedCell({
  text,
  className,
}: {
  text: string
  className?: string
}) {
  return <OverflowText className={cn("w-full min-w-0", className)}>{text}</OverflowText>
}

export function TextCell({
  text,
  href,
  className,
  linkClassName,
}: {
  text: string
  href?: string
  className?: string
  linkClassName?: string
}) {
  const content = <TruncatedCell text={text} className={className} />

  if (!href) return content

  return (
    <Link
      href={href}
      className={cn("block min-w-0 font-medium hover:underline", linkClassName)}
    >
      {content}
    </Link>
  )
}
