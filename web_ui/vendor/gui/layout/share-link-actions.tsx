"use client"

import { useMemo, useState } from "react"
import { Button } from "@/vendor/gui/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/vendor/gui/ui/tooltip"
import { notify } from "@/vendor/gui/lib/ui/notify"
import { Check, Copy, ExternalLink } from "lucide-react"

type ShareLinkActionsProps = {
  path: string
  copySuccessMessage?: string
  copyLabel?: string
  openLabel?: string
}

export function ShareLinkActions({
  path,
  copySuccessMessage = "Ссылка скопирована",
  copyLabel = "Копировать ссылку",
  openLabel = "Открыть в новой вкладке",
}: ShareLinkActionsProps) {
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
    <div className="flex items-center gap-1">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button size="icon-sm" variant="outline" onClick={copyUrl}>
            {copied ? <Check /> : <Copy />}
            <span className="sr-only">{copyLabel}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{copied ? "Скопировано" : copyLabel}</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <Button size="icon-sm" variant="outline" asChild>
            <a href={path} target="_blank" rel="noopener noreferrer">
              <ExternalLink />
              <span className="sr-only">{openLabel}</span>
            </a>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{openLabel}</TooltipContent>
      </Tooltip>
    </div>
  )
}
