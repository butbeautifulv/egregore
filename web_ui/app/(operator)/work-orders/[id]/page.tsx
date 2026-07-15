import { InvestigationDetailView } from "@/components/investigation-detail-view"

type PageProps = {
  params: Promise<{ id: string }>
}

export default async function WorkOrderDetailPage({ params }: PageProps) {
  const { id } = await params
  return <InvestigationDetailView investigationId={id} />
}
