"use client"

import { useCallback, useSyncExternalStore } from "react"

import { listWorkspaces, type WorkspaceSummary } from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"

type CacheEntry = {
  data?: WorkspaceSummary[]
  error: unknown
  promise?: Promise<WorkspaceSummary[]>
}

const EMPTY_ENTRY: CacheEntry = { error: null }

/**
 * Module-level cache shared across every mount (sidebar picker + workspaces
 * hub both list the same tenant). Without this each mount fired its own
 * request, so switching pages re-fetched data the picker already had.
 */
const cache = new Map<string, CacheEntry>()
const listeners = new Map<string, Set<() => void>>()

function notify(tenantId: string) {
  for (const fn of listeners.get(tenantId) ?? []) fn()
}

function subscribe(tenantId: string, onStoreChange: () => void) {
  let subs = listeners.get(tenantId)
  if (!subs) {
    subs = new Set()
    listeners.set(tenantId, subs)
  }
  subs.add(onStoreChange)
  void load(tenantId).catch(() => {})
  return () => {
    subs.delete(onStoreChange)
  }
}

function getEntry(tenantId: string): CacheEntry {
  return cache.get(tenantId) ?? EMPTY_ENTRY
}

function load(tenantId: string, { force = false } = {}): Promise<WorkspaceSummary[]> {
  const existing = getEntry(tenantId)
  if (existing.promise && !force) return existing.promise

  const promise = listWorkspaces(tenantId)
    .then((res) => {
      cache.set(tenantId, { data: res.workspaces, error: null })
      notify(tenantId)
      return res.workspaces
    })
    .catch((exc) => {
      cache.set(tenantId, { data: getEntry(tenantId).data, error: exc })
      notify(tenantId)
      throw exc
    })

  cache.set(tenantId, { ...existing, promise })
  return promise
}

/** Drop cached workspaces so the next render refetches (e.g. after create). */
export function invalidateWorkspaces(tenantId?: string) {
  if (tenantId) {
    cache.delete(tenantId)
    notify(tenantId)
    return
  }
  const tenantIds = [...cache.keys()]
  cache.clear()
  for (const id of tenantIds) notify(id)
}

export function useWorkspaces(tenantId: string) {
  const entry = useSyncExternalStore(
    useCallback((onStoreChange) => subscribe(tenantId, onStoreChange), [tenantId]),
    () => getEntry(tenantId),
    () => EMPTY_ENTRY,
  )
  const refresh = useCallback(() => load(tenantId, { force: true }), [tenantId])

  return {
    workspaces: entry.data,
    loading: entry.data === undefined && entry.error === null,
    error: entry.error ? formatApiError(entry.error, "Failed to load workspaces") : null,
    rawError: entry.error,
    refresh,
  }
}
