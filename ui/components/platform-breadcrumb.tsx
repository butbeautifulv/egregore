"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Fragment,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/vendor/gui/ui/breadcrumb"

export type PlatformCrumb = { label: string; href?: string }

type BreadcrumbContextValue = {
  dynamicLabel: string | null
  setDynamicLabel: (label: string | null) => void
  middleCrumbs: PlatformCrumb[]
  setMiddleCrumbs: (crumbs: PlatformCrumb[]) => void
}

const BreadcrumbContext = createContext<BreadcrumbContextValue | null>(null)

function useBreadcrumbContext() {
  const ctx = useContext(BreadcrumbContext)
  if (!ctx) {
    throw new Error("Platform breadcrumb hooks must be used within PlatformBreadcrumbProvider")
  }
  return ctx
}

export function PlatformBreadcrumbProvider({ children }: { children: ReactNode }) {
  const [dynamicLabel, setDynamicLabel] = useState<string | null>(null)
  const [middleCrumbs, setMiddleCrumbs] = useState<PlatformCrumb[]>([])

  const value = useMemo(
    () => ({ dynamicLabel, setDynamicLabel, middleCrumbs, setMiddleCrumbs }),
    [dynamicLabel, middleCrumbs],
  )

  return <BreadcrumbContext.Provider value={value}>{children}</BreadcrumbContext.Provider>
}

export function usePlatformBreadcrumbLabel(label: string | null) {
  const { setDynamicLabel } = useBreadcrumbContext()
  useEffect(() => {
    setDynamicLabel(label)
    return () => setDynamicLabel(null)
  }, [label, setDynamicLabel])
}

export function usePlatformBreadcrumbMiddle(crumbs: PlatformCrumb[]) {
  const { setMiddleCrumbs } = useBreadcrumbContext()
  useEffect(() => {
    setMiddleCrumbs(crumbs)
    return () => setMiddleCrumbs([])
  }, [crumbs, setMiddleCrumbs])
}

function buildCrumbs(
  pathname: string,
  dynamicLabel: string | null,
  middleCrumbs: PlatformCrumb[],
): PlatformCrumb[] {
  const crumbs: PlatformCrumb[] = [{ label: "Operator", href: "/" }]

  if (pathname === "/") {
    crumbs.push({ label: "Work orders" })
    return crumbs
  }

  if (pathname.startsWith("/work-orders/")) {
    crumbs.push({ label: "Work orders", href: "/" })
    crumbs.push({ label: dynamicLabel ?? "Detail" })
    return crumbs
  }

  if (pathname.startsWith("/catalog/agents/")) {
    crumbs.push({ label: "Catalog", href: "/catalog" })
    crumbs.push(...middleCrumbs)
    crumbs.push({ label: dynamicLabel ?? "Agent" })
    return crumbs
  }

  if (pathname.startsWith("/catalog/memory/")) {
    crumbs.push({ label: "Catalog", href: "/catalog" })
    crumbs.push({ label: "Memory", href: "/catalog?tab=memory" })
    crumbs.push({ label: dynamicLabel ?? "Entry" })
    return crumbs
  }

  if (pathname.startsWith("/catalog")) {
    crumbs.push({ label: "Catalog" })
    return crumbs
  }

  if (pathname.startsWith("/approvals")) {
    crumbs.push({ label: "Approvals" })
    return crumbs
  }

  crumbs.push({ label: pathname.split("/").filter(Boolean).join(" / ") || "Page" })
  return crumbs
}

export function PlatformBreadcrumb() {
  const pathname = usePathname()
  const { dynamicLabel, middleCrumbs } = useBreadcrumbContext()
  const crumbs = buildCrumbs(pathname, dynamicLabel, middleCrumbs)

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1
          return (
            <Fragment key={`${crumb.label}-${index}`}>
              {index > 0 ? <BreadcrumbSeparator /> : null}
              <BreadcrumbItem>
                {isLast || !crumb.href ? (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <Link href={crumb.href}>{crumb.label}</Link>
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
