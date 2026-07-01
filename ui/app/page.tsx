import { getStatus, listInvestigations } from "@/lib/api-client"

import { ChatPanel } from "@/components/chat-panel"
import { InvestigationsTable } from "@/components/investigations-table"
import { StatusCards } from "@/components/status-cards"
import { PageHeader } from "@/vendor/gui/layout/page-header"

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
      <PageHeader
        title="Investigations"
        description="SOC investigations and platform health."
      />

      {error ? <p className="text-destructive text-xs">{error}</p> : null}

      <ChatPanel />
      <InvestigationsTable investigations={investigations} />
      {status ? <StatusCards status={status} /> : null}
    </div>
  )
}
