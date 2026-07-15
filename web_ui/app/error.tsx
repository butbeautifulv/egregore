"use client"

import { ApiErrorAlert } from "@/components/api-error-alert"

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex flex-col gap-6 p-6">
      <ApiErrorAlert
        error={error}
        title="Something went wrong"
        fallback="An unexpected error occurred on this page."
        onRetry={reset}
        retryLabel="Try again"
      />
    </div>
  )
}
