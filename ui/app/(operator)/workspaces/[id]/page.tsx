import { WorkspaceSettingsView } from "@/components/workspace-settings-view"

type PageProps = {
  params: Promise<{ id: string }>
}

export default async function WorkspaceDetailPage({ params }: PageProps) {
  const { id } = await params
  return <WorkspaceSettingsView workspaceId={id} />
}
