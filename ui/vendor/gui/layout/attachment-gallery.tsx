"use client"

import { useState } from "react"
import { DownloadIcon } from "lucide-react"
import { Dialog, DialogContent, DialogTitle } from "@/vendor/gui/ui/dialog"
import { Button } from "@/vendor/gui/ui/button"
import { OverflowText } from "@/vendor/gui/layout/overflow-text"
import { cn } from "@/vendor/gui/utils"

export type AttachmentViewItem = {
  id: number
  originalName: string
  viewUrl: string
  downloadUrl?: string
}

function getDownloadUrl(attachment: AttachmentViewItem) {
  return attachment.downloadUrl ?? `${attachment.viewUrl}?download=1`
}

export function AttachmentGallery({
  attachments,
  className,
}: {
  attachments: AttachmentViewItem[]
  className?: string
}) {
  const [preview, setPreview] = useState<AttachmentViewItem | null>(null)

  if (attachments.length === 0) return null

  return (
    <>
      <div
        className={cn(
          "grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4",
          className
        )}
      >
        {attachments.map((attachment) => (
          <div
            key={attachment.id}
            className="group relative aspect-square overflow-hidden rounded-md border bg-muted"
          >
            <button
              type="button"
              className="size-full"
              onClick={() => setPreview(attachment)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={attachment.viewUrl}
                alt={attachment.originalName}
                className="size-full object-cover transition-transform group-hover:scale-105"
              />
            </button>
            <Button
              type="button"
              size="icon"
              variant="secondary"
              className="absolute right-2 top-2 size-8 opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
              onClick={(e) => {
                e.stopPropagation()
                window.open(getDownloadUrl(attachment), "_blank", "noopener,noreferrer")
              }}
              aria-label={`Скачать ${attachment.originalName}`}
            >
              <DownloadIcon className="size-4" />
            </Button>
          </div>
        ))}
      </div>

      <Dialog
        open={preview !== null}
        onOpenChange={(open) => !open && setPreview(null)}
      >
        <DialogContent className="max-w-4xl p-2">
          <DialogTitle className="sr-only">{preview?.originalName}</DialogTitle>
          {preview && (
            <div className="flex flex-col gap-3">
              <div className="relative max-h-[80vh] w-full overflow-hidden rounded-md">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={preview.viewUrl}
                  alt={preview.originalName}
                  className="max-h-[80vh] w-full object-contain"
                />
              </div>
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 px-2 pb-2">
                <OverflowText className="min-w-0 text-sm">
                  {preview.originalName}
                </OverflowText>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    window.open(getDownloadUrl(preview), "_blank", "noopener,noreferrer")
                  }
                >
                  <DownloadIcon data-icon="inline-start" />
                  Скачать
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

