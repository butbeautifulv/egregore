"use client"

import { AppShell } from "@/vendor/gui/shell/app-shell"

import { AppSidebar } from "@/components/app-sidebar"

export function AppShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell sidebar={<AppSidebar />} breadcrumb={<span className="text-sm font-medium">Operator</span>}>
      {children}
    </AppShell>
  )
}
