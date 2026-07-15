import Link from "next/link"

export default function ForbiddenPage() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-2xl font-semibold">Access denied</h1>
      <p className="text-muted-foreground max-w-md text-sm">
        You do not have permission to view this resource. Ask a workspace owner or organization
        admin for access.
      </p>
      <Link href="/workspaces" className="text-primary text-sm underline">
        Back to workspaces
      </Link>
    </div>
  )
}
