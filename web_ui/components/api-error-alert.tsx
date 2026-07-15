"use client"

import { TriangleAlert } from "lucide-react"

import {
  formatApiError,
  getApiErrorTitle,
  isRetryableApiError,
} from "@/lib/format-api-error"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/vendor/gui/ui/alert"
import { Button } from "@/vendor/gui/ui/button"
import { MotionFadeIn } from "@/vendor/gui/motion"

export function ApiErrorAlert({
  error,
  title,
  message,
  fallback = "Request failed",
  onRetry,
  retryLabel = "Retry",
  showRetry,
  isStale,
  className,
}: {
  error?: unknown
  title?: string
  /** Explicit message; overrides formatApiError(error). */
  message?: string
  fallback?: string
  onRetry?: () => void
  retryLabel?: string
  showRetry?: boolean
  isStale?: boolean
  className?: string
}) {
  if (error == null && !message) return null

  const resolvedMessage =
    message ??
    (typeof error === "string" ? error : formatApiError(error, fallback))
  const resolvedTitle = title ?? getApiErrorTitle(error, fallback)
  const canRetry =
    showRetry ??
    (Boolean(onRetry) &&
      (error == null || typeof error === "string" || isRetryableApiError(error)))

  return (
    <MotionFadeIn variant="fade">
      <Alert variant="destructive" className={className}>
        <TriangleAlert />
        <AlertTitle>{resolvedTitle}</AlertTitle>
        <AlertDescription>
          {resolvedMessage}
          {isStale ? " Showing the last successful load." : null}
        </AlertDescription>
        {canRetry && onRetry ? (
          <AlertAction>
            <Button type="button" size="sm" variant="outline" onClick={onRetry}>
              {retryLabel}
            </Button>
          </AlertAction>
        ) : null}
      </Alert>
    </MotionFadeIn>
  )
}
