"use client"

import Link from "next/link"

import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Alert, AlertDescription } from "@/vendor/gui/ui/alert"
import { Button } from "@/vendor/gui/ui/button"
import { PageSection } from "@/components/page-section"

const LANGFUSE_HOST =
  process.env.NEXT_PUBLIC_LANGFUSE_HOST?.replace(/\/$/, "") ?? "http://localhost:3001"

export default function TraceViewerPage() {
  const tracesUrl = `${LANGFUSE_HOST}/project/default/traces`

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Trace viewer"
        description="Inspect Langfuse traces for agent runs, tool calls, and eval observations."
        actions={
          <Button variant="outline" asChild>
            <Link href={tracesUrl} target="_blank" rel="noreferrer">
              Open in Langfuse
            </Link>
          </Button>
        }
      />

      <Alert>
        <AlertDescription>
          Local forensic report:{" "}
          <code className="text-xs">
            LANGFUSE_BASE_URL=http://localhost:3001 ./scripts/k8s/langfuse-benchmark-report.sh
          </code>
        </AlertDescription>
      </Alert>

      <PageSection className="overflow-hidden p-0">
        <iframe
          title="Langfuse traces"
          src={tracesUrl}
          className="bg-background h-[min(70vh,720px)] w-full border-0"
          sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
        />
      </PageSection>
    </div>
  )
}
