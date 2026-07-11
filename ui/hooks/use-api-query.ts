"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { formatApiError } from "@/lib/format-api-error"

type UseApiQueryOptions<T> = {
  /** When false, skip the initial fetch (default true). */
  enabled?: boolean
  /** Fallback message for formatApiError. */
  fallback?: string
  /** Optional initial data (e.g. SSR / parent props). */
  initialData?: T
}

type UseApiQueryResult<T> = {
  data: T | undefined
  error: string | null
  rawError: unknown
  loading: boolean
  isStale: boolean
  refresh: () => Promise<void>
  setData: React.Dispatch<React.SetStateAction<T | undefined>>
}

export function useApiQuery<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: UseApiQueryOptions<T> = {},
): UseApiQueryResult<T> {
  const { enabled = true, fallback = "Request failed", initialData } = options
  const [data, setData] = useState<T | undefined>(initialData)
  const [error, setError] = useState<string | null>(null)
  const [rawError, setRawError] = useState<unknown>(null)
  const [loading, setLoading] = useState(enabled && initialData === undefined)
  const [isStale, setIsStale] = useState(false)
  const hasDataRef = useRef(initialData !== undefined)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const refresh = useCallback(async () => {
    if (!enabled) return
    const hadData = hasDataRef.current
    if (!hadData) {
      setLoading(true)
    }
    try {
      const next = await fetcherRef.current()
      setData(next)
      hasDataRef.current = true
      setError(null)
      setRawError(null)
      setIsStale(false)
    } catch (exc) {
      setRawError(exc)
      setError(formatApiError(exc, fallback))
      if (hadData) {
        setIsStale(true)
      }
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps passed by caller
  }, [enabled, fallback, ...deps])

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      const hadData = hasDataRef.current
      if (!hadData) {
        setLoading(true)
      }
      try {
        const next = await fetcherRef.current()
        if (cancelled) return
        setData(next)
        hasDataRef.current = true
        setError(null)
        setRawError(null)
        setIsStale(false)
      } catch (exc) {
        if (cancelled) return
        setRawError(exc)
        setError(formatApiError(exc, fallback))
        if (hadData) {
          setIsStale(true)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps passed by caller
  }, [enabled, fallback, ...deps])

  return { data, error, rawError, loading, isStale, refresh, setData }
}
