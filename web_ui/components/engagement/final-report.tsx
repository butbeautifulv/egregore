import { FindingContent } from "@/components/engagement/finding-content"
import { PageSection } from "@/components/page-section"
import { CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

function findingBody(item: Record<string, unknown>): Record<string, unknown> {
  const nested = item.finding
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return nested as Record<string, unknown>
  }
  return item
}

export function FinalReportSection({ report }: { report: Record<string, unknown> | null | undefined }) {
  if (!report || !Object.keys(report).length) return null
  return (
    <PageSection>
      <CardHeader>
        <CardTitle>Final report</CardTitle>
      </CardHeader>
      <CardContent>
        <FindingContent data={report} />
      </CardContent>
    </PageSection>
  )
}
