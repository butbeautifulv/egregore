import { isActionsColumn } from "@/vendor/gui/lib/data-table/column-meta"

const TAILWIND_WIDTH_PX: Record<string, number> = {
  "w-10": 40,
  "w-12": 48,
  "w-16": 64,
  "w-24": 96,
  "w-28": 112,
  "w-32": 128,
  "w-40": 160,
  "w-48": 192,
}

const ACTIONS_COLUMN_WIDTH_PX = 64

export function parsePercentWeight(cellClassName?: string): number | null {
  const match = cellClassName?.match(/\bw-\[(\d+)%\]/)
  return match ? Number(match[1]) : null
}

export function parseFixedWidthPx(cellClassName?: string): number {
  if (!cellClassName) return 0

  for (const [twClass, px] of Object.entries(TAILWIND_WIDTH_PX)) {
    if (new RegExp(`\\b${twClass}\\b`).test(cellClassName)) return px
  }

  return 0
}

export function stripPercentWidthClass(cellClassName?: string): string | undefined {
  if (!cellClassName) return undefined

  const stripped = cellClassName.replace(/\bw-\[\d+%\]\s*/g, "").trim()
  return stripped || undefined
}

type VisibleColumn = {
  id: string
  meta?: { cellClassName?: string; role?: string }
}

export function buildVisibleColumnWidths(
  visibleColumns: VisibleColumn[]
): Map<string, string | undefined> {
  const widths = new Map<string, string | undefined>()
  let fixedTotalPx = 0
  let flexWeightTotal = 0
  const flexCols: { id: string; weight: number }[] = []

  for (const column of visibleColumns) {
    if (isActionsColumn(column.id, column.meta)) {
      fixedTotalPx += ACTIONS_COLUMN_WIDTH_PX
      widths.set(column.id, `${ACTIONS_COLUMN_WIDTH_PX}px`)
      continue
    }

    const className = column.meta?.cellClassName
    const weight = parsePercentWeight(className)
    const fixedPx = parseFixedWidthPx(className)

    if (weight) {
      flexCols.push({ id: column.id, weight })
      flexWeightTotal += weight
      continue
    }

    if (fixedPx > 0) {
      fixedTotalPx += fixedPx
      widths.set(column.id, `${fixedPx}px`)
    }
  }

  for (const { id, weight } of flexCols) {
    if (flexWeightTotal === 0) continue

    const ratio = weight / flexWeightTotal
    widths.set(
      id,
      fixedTotalPx > 0
        ? `max(2rem, calc((100% - ${fixedTotalPx}px) * ${ratio}))`
        : `${ratio * 100}%`
    )
  }

  return widths
}
