"use client"

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/vendor/gui/ui/breadcrumb"

export type ShellCrumb = { label: string; href?: string }

function serializeCrumbs(crumbs: ShellCrumb[]) {
  return JSON.stringify(crumbs)
}

const ShellBreadcrumbContext = createContext<{
  dynamicLabel: string | null
  setDynamicLabel: (label: string | null) => void
  middleCrumbs: ShellCrumb[]
  setMiddleCrumbs: (crumbs: ShellCrumb[]) => void
} | null>(null)

export function ShellBreadcrumbProvider({ children }: { children: ReactNode }) {
  const [dynamicLabel, setDynamicLabel] = useState<string | null>(null)
  const [middleCrumbs, setMiddleCrumbs] = useState<ShellCrumb[]>([])
  const value = useMemo(
    () => ({ dynamicLabel, setDynamicLabel, middleCrumbs, setMiddleCrumbs }),
    [dynamicLabel, middleCrumbs]
  )
  return (
    <ShellBreadcrumbContext.Provider value={value}>
      {children}
    </ShellBreadcrumbContext.Provider>
  )
}

export function useShellBreadcrumbLabel(label: string | null) {
  const ctx = useContext(ShellBreadcrumbContext)
  const setDynamicLabel = ctx?.setDynamicLabel

  useEffect(() => {
    if (!setDynamicLabel) return
    setDynamicLabel(label)
    return () => setDynamicLabel(null)
  }, [label, setDynamicLabel])
}

export function useShellBreadcrumbMiddle(crumbs: ShellCrumb[]) {
  const ctx = useContext(ShellBreadcrumbContext)
  const setMiddleCrumbs = ctx?.setMiddleCrumbs
  const crumbsKey = serializeCrumbs(crumbs)

  useEffect(() => {
    if (!setMiddleCrumbs) return
    setMiddleCrumbs(JSON.parse(crumbsKey) as ShellCrumb[])
    return () => setMiddleCrumbs([])
  }, [crumbsKey, setMiddleCrumbs])
}

export function ShellBreadcrumb({
  buildCrumbs,
}: {
  buildCrumbs: (
    pathname: string,
    dynamicLabel: string | null,
    middleCrumbs: ShellCrumb[]
  ) => ShellCrumb[]
}) {
  const pathname = usePathname()
  const ctx = useContext(ShellBreadcrumbContext)
  const crumbs = buildCrumbs(
    pathname,
    ctx?.dynamicLabel ?? null,
    ctx?.middleCrumbs ?? []
  )

  const items: ReactNode[] = []
  crumbs.forEach((crumb, index) => {
    if (index > 0) {
      items.push(
        <BreadcrumbSeparator key={`sep-${index}`} className="hidden md:block" />
      )
    }
    const isLast = index === crumbs.length - 1
    items.push(
      <BreadcrumbItem
        key={`${crumb.label}-${index}`}
        className={index === 0 ? "hidden md:block" : undefined}
      >
        {isLast || !crumb.href ? (
          <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
        ) : (
          <BreadcrumbLink asChild>
            <Link href={crumb.href}>{crumb.label}</Link>
          </BreadcrumbLink>
        )}
      </BreadcrumbItem>
    )
  })

  return (
    <Breadcrumb>
      <BreadcrumbList>{items}</BreadcrumbList>
    </Breadcrumb>
  )
}
