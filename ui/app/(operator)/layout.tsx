import { AppShellLayout } from "@/components/app-shell-layout"
import { AuthGuard } from "@/components/auth-guard"

export default function OperatorLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShellLayout>{children}</AppShellLayout>
    </AuthGuard>
  )
}
