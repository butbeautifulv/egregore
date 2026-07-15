"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"

import { setClientSessionToken } from "@/lib/auth/session"
import { Alert, AlertDescription } from "@/vendor/gui/ui/alert"
import { Button } from "@/vendor/gui/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/vendor/gui/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/vendor/gui/ui/field"
import { Input } from "@/vendor/gui/ui/input"
import { Spinner } from "@/vendor/gui/ui/spinner"
import { cn } from "@/vendor/gui/utils"

export function LoginForm({ className, ...props }: React.ComponentProps<"div">) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [email, setEmail] = useState("operator@egregore.local")
  const [password, setPassword] = useState("demo")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError("")

    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })

    setLoading(false)

    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      setError(data.error ?? "Sign-in failed")
      return
    }

    const data = await response.json().catch(() => ({}))
    if (typeof data.token === "string") {
      setClientSessionToken(data.token)
    }

    const next = searchParams.get("next") ?? "/"
    router.push(next)
    router.refresh()
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Sign in</CardTitle>
          <CardDescription>Egregore operator console</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </Field>
              {error ? (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
              <Field>
                <Button type="submit" disabled={loading} className="w-full">
                  {loading ? <Spinner data-icon="inline-start" /> : null}
                  {loading ? "Signing in…" : "Sign in"}
                </Button>
              </Field>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
