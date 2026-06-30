"use client"

import { useMemo, useState } from "react"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/vendor/gui/ui/input-group"
import { notify } from "@/vendor/gui/lib/ui/notify"
import { cn } from "@/vendor/gui/utils"
import { Check, Copy, ExternalLink } from "lucide-react"

type ShareLinkFieldProps = {
  path: string
  className?: string
  copySuccessMessage?: string
  copyLabel?: string
  openLabel?: string
}

export function ShareLinkField({
  path,
  className,
  copySuccessMessage = "Ссылка скопирована",
  copyLabel = "Копировать ссылку",
  openLabel = "Открыть в новой вкладке",
}: ShareLinkFieldProps) {
  const [copied, setCopied] = useState(false)

  const url = useMemo(() => {
    if (typeof window === "undefined") return path
    return new URL(path, window.location.origin).toString()
  }, [path])

  function copyUrl() {
    void navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    notify.success(copySuccessMessage)
  }

  return (
    <InputGroup className={cn("h-8", className)}>
      <InputGroupInput readOnly value={url} aria-label="Ссылка" onFocus={(e) => e.target.select()} />
      <InputGroupAddon align="inline-end" className="gap-0.5">
        <InputGroupButton
          size="icon-xs"
          variant="ghost"
          onClick={copyUrl}
          aria-label={copyLabel}
        >
          {copied ? <Check /> : <Copy />}
        </InputGroupButton>
        <InputGroupButton size="icon-xs" variant="ghost" asChild>
          <a href={path} target="_blank" rel="noopener noreferrer" aria-label={openLabel}>
            <ExternalLink />
          </a>
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  )
}
