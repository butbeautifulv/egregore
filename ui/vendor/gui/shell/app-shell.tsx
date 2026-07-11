"use client"

import { usePathname } from "next/navigation"
import { ThemeToggle } from "@/vendor/gui/theme/theme-toggle"
import { MotionPageEnter } from "@/vendor/gui/motion"
import { SidebarAutoCollapse } from "@/vendor/gui/shell/sidebar-auto-collapse"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/vendor/gui/ui/sidebar"
import { Separator } from "@/vendor/gui/ui/separator"

export function AppShell({
  sidebar,
  breadcrumb,
  provider: Provider,
  children,
}: {
  sidebar: React.ReactNode
  breadcrumb: React.ReactNode
  provider?: React.ComponentType<{ children: React.ReactNode }>
  children: React.ReactNode
}) {
  const pathname = usePathname()

  const body = (
    <>
      <SidebarAutoCollapse />
      <header className="flex h-(--header-height) min-w-0 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger className="-ml-1" />
        <Separator
          orientation="vertical"
          className="mr-2 data-vertical:h-4 data-vertical:self-auto"
        />
        <div className="min-w-0 flex-1">{breadcrumb}</div>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <ThemeToggle />
        </div>
      </header>
      <MotionPageEnter pageKey={pathname} className="@container/main flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
        {children}
      </MotionPageEnter>
    </>
  )

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 88)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      {sidebar}
      <SidebarInset className="md:peer-data-[variant=inset]:m-0 md:peer-data-[variant=inset]:rounded-none md:peer-data-[variant=inset]:shadow-none md:peer-data-[variant=inset]:peer-data-[state=collapsed]:ml-0">
        {Provider ? <Provider>{body}</Provider> : body}
      </SidebarInset>
    </SidebarProvider>
  )
}
