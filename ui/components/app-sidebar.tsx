"use client"

import { ClipboardCheck, LayoutDashboard, Library, Shield } from "lucide-react"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"

import { listPendingApprovals } from "@/lib/api-client"
import { NavUser } from "@/components/nav-user"
import { ShellSidebar } from "@/vendor/gui/shell/shell-sidebar"
import { ShellNavMain } from "@/vendor/gui/shell/shell-nav-main"
import { Badge } from "@/vendor/gui/ui/badge"

export function AppSidebar() {
  const pathname = usePathname()
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const response = await listPendingApprovals()
        if (!cancelled) {
          setPendingCount(response.count)
        }
      } catch {
        if (!cancelled) {
          setPendingCount(0)
        }
      }
    }
    void load()
    const timer = setInterval(load, 15000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  const opsItems = [
    {
      title: "Work orders",
      href: "/",
      icon: LayoutDashboard,
      isActive: pathname === "/" || pathname.startsWith("/work-orders"),
    },
    {
      title: "Approvals",
      href: "/approvals",
      icon: ClipboardCheck,
      isActive: pathname.startsWith("/approvals"),
      badge:
        pendingCount > 0 ? (
          <Badge variant="destructive" className="ml-auto">
            {pendingCount}
          </Badge>
        ) : undefined,
    },
  ]

  const catalogItems = [
    {
      title: "Catalog",
      href: "/catalog",
      icon: Library,
      isActive: pathname.startsWith("/catalog") || pathname.startsWith("/eval") || pathname.startsWith("/compare"),
    },
  ]

  return (
    <ShellSidebar
      brand={{
        href: "/",
        title: "Egregore",
        subtitle: "Operator console",
        icon: Shield,
      }}
      groupLabel="Operations"
      footer={<NavUser />}
      navContent={
        <>
          <ShellNavMain groupLabel="Operations" items={opsItems} />
          <ShellNavMain groupLabel="Catalog" items={catalogItems} />
        </>
      }
    />
  )
}
