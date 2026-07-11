import { redirect } from "next/navigation"

type PageProps = {
  searchParams: Promise<{ agent?: string }>
}

export default async function MemoryPage({ searchParams }: PageProps) {
  const params = await searchParams
  const qs = new URLSearchParams({ tab: "memory" })
  if (params.agent?.trim()) {
    qs.set("agent", params.agent.trim())
  }
  redirect(`/catalog?${qs}`)
}
