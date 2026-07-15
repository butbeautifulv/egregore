"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useCallback, useEffect, useRef, useState } from "react"

import { listWorkOrdersPage, resolveOperatorUnitId, type WorkOrderSummary } from "@/lib/api-client"
import { getSelectedTenantId, getSelectedWorkspaceId } from "@/lib/workspace"
import { truncateNavLabel } from "@/lib/nav-label"
import type { InvestigationSummary } from "@/lib/types"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/vendor/gui/ui/sidebar"
import { Spinner } from "@/vendor/gui/ui/spinner"

const RECENT_PAGE_SIZE = 20
const REFRESH_MS = 30_000

function RecentGroup({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SidebarSeparator className="mx-2" />
      <SidebarGroup>{children}</SidebarGroup>
    </>
  )
}

function toInvestigationSummary(item: WorkOrderSummary, tenantId: string): InvestigationSummary {
  return {
    investigation_id: resolveOperatorUnitId(item),
    tenant_id: tenantId,
    goal: item.goal ?? "",
    status: item.status,
    completed_personas: item.completed_personas ?? [],
    failed_personas: item.failed_personas ?? [],
    updated_at: item.updated_at,
  }
}

function filterByWorkspace(items: WorkOrderSummary[]): WorkOrderSummary[] {
  const workspaceId = getSelectedWorkspaceId().trim()
  if (!workspaceId) {
    return items
  }
  return items.filter((item) => (item.workspace_id ?? "") === workspaceId)
}

function mergeHeadItems(
  head: InvestigationSummary[],
  tail: InvestigationSummary[],
): InvestigationSummary[] {
  const seen = new Set(head.map((item) => item.investigation_id))
  const mergedTail = tail.filter((item) => !seen.has(item.investigation_id))
  return [...head, ...mergedTail]
}

function dedupeById(items: InvestigationSummary[]): InvestigationSummary[] {
  const seen = new Set<string>()
  const out: InvestigationSummary[] = []
  for (const item of items) {
    if (seen.has(item.investigation_id)) continue
    seen.add(item.investigation_id)
    out.push(item)
  }
  return out
}

export function SidebarRecentWorkOrders() {
  const pathname = usePathname()
  const { state, isMobile } = useSidebar()
  const [items, setItems] = useState<InvestigationSummary[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const nextCursorRef = useRef<string | null>(null)
  const loadingMoreRef = useRef(false)

  const collapsed = !isMobile && state === "collapsed"

  useEffect(() => {
    nextCursorRef.current = nextCursor
  }, [nextCursor])

  useEffect(() => {
    loadingMoreRef.current = loadingMore
  }, [loadingMore])

  const loadHead = useCallback(async () => {
    const tenantId = getSelectedTenantId()
    const page = await listWorkOrdersPage({ tenantId, limit: RECENT_PAGE_SIZE })
    const head = filterByWorkspace(page.items).map((item) => toInvestigationSummary(item, tenantId))
    setItems((previous) => mergeHeadItems(head, previous))
    setNextCursor(page.next_cursor)
    return page
  }, [])

  const loadMore = useCallback(async () => {
    const cursor = nextCursorRef.current
    if (!cursor || loadingMoreRef.current) return
    loadingMoreRef.current = true
    setLoadingMore(true)
    setLoadMoreError(null)
    try {
      const tenantId = getSelectedTenantId()
      const page = await listWorkOrdersPage({
        tenantId,
        limit: RECENT_PAGE_SIZE,
        cursor,
      })
      const appended = filterByWorkspace(page.items).map((item) =>
        toInvestigationSummary(item, tenantId),
      )
      setItems((previous) => dedupeById([...previous, ...appended]))
      setNextCursor(page.next_cursor)
    } catch {
      setLoadMoreError("Failed to load more")
    } finally {
      loadingMoreRef.current = false
      setLoadingMore(false)
    }
  }, [])

  useEffect(() => {
    if (collapsed) return
    let cancelled = false

    const bootstrap = async () => {
      try {
        const tenantId = getSelectedTenantId()
        const page = await listWorkOrdersPage({ tenantId, limit: RECENT_PAGE_SIZE })
        if (cancelled) return
        setItems(
          filterByWorkspace(page.items).map((item) => toInvestigationSummary(item, tenantId)),
        )
        setNextCursor(page.next_cursor)
      } catch {
        if (!cancelled) {
          setItems([])
          setNextCursor(null)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void bootstrap()
    const timer = setInterval(() => {
      void loadHead().catch(() => {})
    }, REFRESH_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [pathname, collapsed, loadHead])

  useEffect(() => {
    if (collapsed || !nextCursor) return
    const node = sentinelRef.current
    if (!node) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void loadMore()
        }
      },
      { rootMargin: "120px" },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [collapsed, nextCursor, loadMore])

  if (collapsed) {
    return null
  }

  if (loading) {
    return (
      <RecentGroup>
        <SidebarGroupLabel>Recent</SidebarGroupLabel>
        <SidebarGroupContent>
          <p className="text-muted-foreground px-2 text-xs">Loading…</p>
        </SidebarGroupContent>
      </RecentGroup>
    )
  }

  if (items.length === 0) {
    return (
      <RecentGroup>
        <SidebarGroupLabel>Recent</SidebarGroupLabel>
        <SidebarGroupContent>
          <p className="text-muted-foreground px-2 text-xs">No recent work orders</p>
        </SidebarGroupContent>
      </RecentGroup>
    )
  }

  return (
    <RecentGroup>
      <SidebarGroupLabel>Recent</SidebarGroupLabel>
      <SidebarGroupContent className="flex flex-col gap-2">
        <SidebarMenu>
          {items.map((item) => {
            const href = `/work-orders/${item.investigation_id}`
            const title = truncateNavLabel(item.goal) || item.investigation_id
            return (
              <SidebarMenuItem key={item.investigation_id}>
                <SidebarMenuButton asChild isActive={pathname === href} tooltip={title}>
                  <Link href={href} className="min-w-0">
                    <OverflowText className="min-w-0 flex-1">{title}</OverflowText>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
        {nextCursor ? (
          <div ref={sentinelRef} className="flex min-h-6 items-center justify-center px-2">
            {loadingMore ? (
              <Spinner className="size-4" />
            ) : loadMoreError ? (
              <button
                type="button"
                className="text-muted-foreground text-xs hover:underline"
                onClick={() => void loadMore()}
              >
                {loadMoreError} — retry
              </button>
            ) : null}
          </div>
        ) : null}
      </SidebarGroupContent>
    </RecentGroup>
  )
}
