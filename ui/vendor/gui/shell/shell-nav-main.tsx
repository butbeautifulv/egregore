"use client"

import Link from "next/link"
import type { LucideIcon } from "lucide-react"
import { ChevronRightIcon } from "lucide-react"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/vendor/gui/ui/sidebar"

export type ShellNavMainChild = {
  title: string
  href: string
  badge?: React.ReactNode
  isActive?: boolean
}

export type ShellNavMainItem = {
  title: string
  href?: string
  icon?: LucideIcon
  isActive?: boolean
  defaultOpen?: boolean
  badge?: React.ReactNode
  children?: ShellNavMainChild[]
}

function NavMainItem({ item }: { item: ShellNavMainItem }) {
  const Icon = item.icon
  const hasChildren = item.children && item.children.length > 0

  if (!hasChildren && item.href) {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton asChild isActive={item.isActive} tooltip={item.title}>
          <Link href={item.href} className="min-w-0">
            {Icon && <Icon className="shrink-0" />}
            <OverflowText className="min-w-0 flex-1">{item.title}</OverflowText>
            {item.badge}
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    )
  }

  if (!hasChildren) return null

  return (
    <Collapsible
      asChild
      defaultOpen={item.defaultOpen ?? item.isActive}
      className="group/collapsible"
    >
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton tooltip={item.title} className="min-w-0">
            {Icon && <Icon className="shrink-0" />}
            <OverflowText className="min-w-0 flex-1">{item.title}</OverflowText>
            {item.badge}
            <ChevronRightIcon className="ml-auto size-4 shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarMenuSub className="mx-2 px-2">
            {item.children!.map((child) => (
              <SidebarMenuSubItem key={child.href}>
                <SidebarMenuSubButton
                  asChild
                  isActive={child.isActive}
                  className={
                    child.badge
                      ? "h-auto min-h-7 items-start overflow-hidden py-1.5 [&>span:nth-child(2)]:shrink-0 [&>span:nth-child(2)]:overflow-visible [&>span:nth-child(2)]:whitespace-nowrap"
                      : "overflow-hidden"
                  }
                >
                  <Link
                    href={child.href}
                    className={
                      child.badge
                        ? "flex w-full min-w-0 flex-col gap-1 overflow-hidden"
                        : "block w-full min-w-0 overflow-hidden"
                    }
                  >
                    <OverflowText className="w-full min-w-0">{child.title}</OverflowText>
                    {child.badge}
                  </Link>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}

export function ShellNavMain({
  groupLabel,
  items,
}: {
  groupLabel: string
  items: ShellNavMainItem[]
}) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>{groupLabel}</SidebarGroupLabel>
      <SidebarGroupContent className="flex flex-col gap-2">
        <SidebarMenu>
          {items.map((item) => (
            <NavMainItem key={item.href ?? item.title} item={item} />
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
