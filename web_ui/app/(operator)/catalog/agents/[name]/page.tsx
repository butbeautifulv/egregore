import { CatalogAgentDetailView } from "@/components/catalog-agent-detail-view"

type PageProps = {
  params: Promise<{ name: string }>
}

export default async function CatalogAgentPage({ params }: PageProps) {
  const { name } = await params
  return <CatalogAgentDetailView agentName={decodeURIComponent(name)} />
}
