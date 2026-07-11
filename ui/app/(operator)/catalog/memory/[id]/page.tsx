import { CatalogMemoryDetailView } from "@/components/catalog-memory-detail-view"

type PageProps = {
  params: Promise<{ id: string }>
  searchParams: Promise<{ agent?: string }>
}

export default async function CatalogMemoryPage({ params, searchParams }: PageProps) {
  const { id } = await params
  const { agent } = await searchParams
  return (
    <CatalogMemoryDetailView
      memoryId={decodeURIComponent(id)}
      agentHint={agent?.trim() || undefined}
    />
  )
}
