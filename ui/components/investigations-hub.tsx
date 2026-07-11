"use client"

import { InvestigationsAsyncPanel } from "@/components/investigations-async-panel"
import { PageHeader } from "@/vendor/gui/layout/page-header"

export function InvestigationsHub() {
  return (
    <div className="@container/main flex flex-col gap-6">
      <PageHeader
        title="Work orders"
        description="Start and track agent work orders."
      />
      <InvestigationsAsyncPanel />
    </div>
  )
}
