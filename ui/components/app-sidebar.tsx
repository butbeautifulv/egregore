"use client"

import { BarChart3, ClipboardCheck, GitCompare, LayoutDashboard, Library, PlayCircle, Shield, Waypoints } from "lucide-react"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"

import { listPendingApprovals } from "@/lib/api-client"
import { ShellSidebar } from "@/vendor/gui/shell/shell-sidebar"
import { Badge } from "@/vendor/gui/ui/badge"

const navItems = [
  { title: "Investigations", href: "/", icon: LayoutDashboard },
  { title: "Agent runs", href: "/runs", icon: PlayCircle },
  { title: "Approvals", href: "/approvals", icon: ClipboardCheck },
  { title: "Quality", href: "/catalog", icon: Library },
  { title: "Eval runs", href: "/eval", icon: BarChart3 },
  { title: "Traces", href: "/traces", icon: Waypoints },
  { title: "Compare", href: "/compare", icon: GitCompare },
]

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

  return (
    <ShellSidebar
      brand={{
        href: "/",
        title: "Egregore",
        subtitle: "SOC operator console",
        icon: Shield,
      }}
      groupLabel="Operations"
      navItems={navItems.map((item) => ({
        ...item,
        isActive: item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
        badge:
          item.href === "/approvals" && pendingCount > 0 ? (
            <Badge variant="destructive" className="ml-auto">
              {pendingCount}
            </Badge>
          ) : undefined,
      }))}
    />
  )
}
