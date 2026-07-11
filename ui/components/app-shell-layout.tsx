"use client"

import { AppShell } from "@/vendor/gui/shell/app-shell"

import { AppSidebar } from "@/components/app-sidebar"
import {
  PlatformBreadcrumb,
  PlatformBreadcrumbProvider,
} from "@/components/platform-breadcrumb"

export function AppShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell
      sidebar={<AppSidebar />}
      breadcrumb={<PlatformBreadcrumb />}
      provider={PlatformBreadcrumbProvider}
    >
      {children}
    </AppShell>
  )
}
