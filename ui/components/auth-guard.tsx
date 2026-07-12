"use client"

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"

import { getClientSession } from "@/lib/auth/session"

const OIDC_ENABLED = Boolean(process.env.NEXT_PUBLIC_OIDC_ISSUER)

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (!OIDC_ENABLED || pathname.startsWith("/login")) {
      return
    }
    let cancelled = false
    void getClientSession().then((session) => {
      if (!cancelled && !session.authenticated) {
        router.replace(`/login?next=${encodeURIComponent(pathname)}`)
      }
    })
    return () => {
      cancelled = true
    }
  }, [pathname, router])

  return children
}
