import { FACETED_COLUMN_META } from "@/vendor/gui/lib/data-table/faceted-column"
import { cn } from "@/vendor/gui/utils"

export const ACTIONS_COLUMN_ID = "actions"

export const ACTIONS_COLUMN_CELL_CLASS =
  "sticky right-0 z-10 w-16 min-w-16 max-w-16 bg-background px-2 py-0"

type ColMetaOptions = {
  valueType?: "date" | "datetime"
  valueLabels?: Record<string, string>
  faceted?: boolean
  cellClassName?: string
}

export function colMeta(title: string, opts: ColMetaOptions = {}) {
  const { valueType, valueLabels, faceted = true, cellClassName } = opts
  return {
    ...(faceted ? FACETED_COLUMN_META : {}),
    title,
    ...(valueType ? { valueType } : {}),
    ...(valueLabels ? { valueLabels } : {}),
    ...(cellClassName ? { cellClassName } : {}),
  }
}

export function textColumnMeta(
  title: string,
  /** Relative flex weight; redistributed among visible columns when some are hidden. */
  widthClass = "w-[16%]",
  opts: Omit<ColMetaOptions, "cellClassName"> = {}
) {
  return colMeta(title, {
    ...opts,
    cellClassName: cn("max-w-0", widthClass),
  })
}

export function actionsColumnMeta(extra?: string) {
  return {
    faceted: false as const,
    role: "actions" as const,
    cellClassName: cn("w-16 min-w-16 max-w-16 px-2 py-0", extra),
  }
}

export function isActionsColumn(
  columnId: string,
  meta?: { role?: string }
): boolean {
  return columnId === ACTIONS_COLUMN_ID || meta?.role === "actions"
}
