import { FindingContent } from "@/components/engagement/finding-content"
import { PageSection } from "@/components/page-section"
import { CardContent, CardHeader, CardTitle } from "@/vendor/gui/ui/card"

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
