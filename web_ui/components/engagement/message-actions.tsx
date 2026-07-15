"use client"

import { useState } from "react"
import { CheckIcon, CopyIcon, Share2Icon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/vendor/gui/ui/button"
import { cn } from "@/vendor/gui/utils"

export function MessageActions({
  text,
  shareUrl,
  align = "start",
  className,
}: {
  text: string
  shareUrl?: string
  align?: "start" | "end"
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const trimmed = text.trim()
  if (!trimmed) return null

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(trimmed)
      setCopied(true)
      toast.success("Copied to clipboard")
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error("Could not copy")
    }
  }

  const share = async () => {
    const url = shareUrl ?? (typeof window !== "undefined" ? window.location.href : "")
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({
          title: "Egregore work order",
          text: trimmed.length > 500 ? `${trimmed.slice(0, 500)}…` : trimmed,
          url,
        })
        return
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return
      }
    }
    try {
      const payload = url ? `${trimmed}\n\n${url}` : trimmed
      await navigator.clipboard.writeText(payload)
      toast.success("Message and link copied")
    } catch {
      toast.error("Could not share")
    }
  }

  return (
    <div
      className={cn(
        "flex items-center gap-0.5 opacity-70 transition-opacity md:opacity-0 md:group-hover/message:opacity-100 md:group-focus-within/message:opacity-100",
        align === "end" ? "justify-end" : "justify-start",
        className,
      )}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        onClick={() => void copy()}
        title="Copy"
        aria-label="Copy message"
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        onClick={() => void share()}
        title="Share"
        aria-label="Share message"
      >
        <Share2Icon />
      </Button>
    </div>
  )
}
