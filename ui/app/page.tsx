import { getStatus, listInvestigations } from "@/lib/api-client"

import { ChatPanel } from "@/components/chat-panel"
import { InvestigationsTable } from "@/components/investigations-table"
import { StatusCards } from "@/components/status-cards"

export default async function HomePage() {
  let investigations: Awaited<ReturnType<typeof listInvestigations>>["investigations"] = []
  let status = null
  let error: string | null = null

  try {
    const [investigationResponse, statusResponse] = await Promise.all([
      listInvestigations(),
      getStatus(),
    ])
    investigations = investigationResponse.investigations
    status = statusResponse
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Failed to load investigations"
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Investigations</h1>
        <p className="text-muted-foreground text-sm">SOC investigations and platform health.</p>
      </div>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}

      <ChatPanel />
      <InvestigationsTable investigations={investigations} />
      {status ? <StatusCards status={status} /> : null}
    </div>
  )
}
