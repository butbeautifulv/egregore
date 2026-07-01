"use client"

import Link from "next/link"
import type { LucideIcon } from "lucide-react"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/vendor/gui/ui/sidebar"

export function ShellBrand({
  href,
  title,
  subtitle,
  subtitleTitle,
  icon: Icon,
  logo,
}: {
  href: string
  title: string
  subtitle?: string
  subtitleTitle?: string
  icon: LucideIcon
  logo?: React.ReactNode
}) {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size="lg" asChild>
          <Link href={href} className="min-w-0 overflow-hidden">
            {logo ?? (
              <div className="flex aspect-square size-8 shrink-0 items-center justify-center rounded-none bg-sidebar-primary text-sidebar-primary-foreground">
                <Icon className="size-4" />
              </div>
            )}
            <div className="grid min-w-0 flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
              <OverflowText className="w-full min-w-0 font-medium">{title}</OverflowText>
              {subtitle && (
                <span
                  className="line-clamp-2 text-xs text-muted-foreground"
                  title={subtitleTitle ?? subtitle}
                >
                  {subtitle}
                </span>
              )}
            </div>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
