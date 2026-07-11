import { Suspense } from "react"
import { Shield } from "lucide-react"

import { LoginFormSkeleton } from "@/components/skeletons"
import { LoginForm } from "@/components/login-form"

export default function LoginPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col items-center gap-2 text-center">
        <div className="bg-primary text-primary-foreground flex size-10 items-center justify-center rounded-lg">
          <Shield className="size-5" />
        </div>
        <h1 className="text-xl font-semibold">Egregore</h1>
        <p className="text-muted-foreground text-sm">Operator console</p>
      </div>
      <Suspense fallback={<LoginFormSkeleton />}>
        <LoginForm />
      </Suspense>
    </div>
  )
}
