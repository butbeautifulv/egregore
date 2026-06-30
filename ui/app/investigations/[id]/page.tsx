import { notFound } from "next/navigation"

import { ApiError, getInvestigation, getInvestigationJobs } from "@/lib/api-client"
import { InvestigationDetailView } from "@/components/investigation-detail-view"

type PageProps = {
  params: Promise<{ id: string }>
}

export default async function InvestigationDetailPage({ params }: PageProps) {
  const { id } = await params

  try {
    const [detail, jobsResponse] = await Promise.all([getInvestigation(id), getInvestigationJobs(id)])
    return (
      <InvestigationDetailView
        investigationId={id}
        initialDetail={detail}
        initialJobs={jobsResponse.jobs}
      />
    )
  } catch (exc) {
    if (exc instanceof ApiError && exc.status === 404) {
      notFound()
    }
    throw exc
  }
}
