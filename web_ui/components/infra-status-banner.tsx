"use client"

import { useEffect, useState } from "react"

import { getHealthInfra, type InfraHealthResponse } from "@/lib/api-client"
import { Alert, AlertDescription, AlertTitle } from "@/vendor/gui/ui/alert"

export function InfraStatusBanner() {
  const [infra, setInfra] = useState<InfraHealthResponse | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const response = await getHealthInfra()
        if (!cancelled) setInfra(response)
      } catch {
        if (!cancelled) setInfra(null)
      }
    }
    void load()
    const timer = setInterval(load, 20000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  if (!infra) return null

  if (infra.workers_hint === "backlog") {
    return (
      <Alert variant="destructive">
        <AlertTitle>No worker consumer</AlertTitle>
        <AlertDescription>
          Queue depth {infra.queue.depth ?? 0} with {infra.running_jobs} running jobs. Start workers:{" "}
          <code className="text-xs">uv run egregore worker --daemon</code>
        </AlertDescription>
      </Alert>
    )
  }

  if (infra.workers_hint === "processing" && (infra.queue.depth ?? 0) > 5) {
    return (
      <Alert>
        <AlertTitle>Queue backlog</AlertTitle>
        <AlertDescription>
          {infra.queue.depth} jobs queued, {infra.running_jobs} running.
        </AlertDescription>
      </Alert>
    )
  }

  return null
}
