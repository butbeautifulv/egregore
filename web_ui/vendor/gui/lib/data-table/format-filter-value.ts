import { getFilterTimeZone } from "@/vendor/gui/lib/datetime/filter-timezone"
import {
  formatDisplayDate,
  formatDisplayDateTime,
  isIsoDateString,
  toFilterDateKey,
} from "@/vendor/gui/lib/datetime/format"

type FilterColumnMeta = {
  valueType?: "date" | "datetime"
  valueLabels?: Record<string, string>
}

/** Canonical string for faceted filter match (must match row cell values). */
export function normalizeFilterValue(
  value: unknown,
  meta?: FilterColumnMeta,
  timeZone = getFilterTimeZone()
): string {
  if (value == null || value === "") return "—"
  if (value instanceof Date) {
    const iso = value.toISOString()
    if (meta?.valueType === "date") return toFilterDateKey(iso, timeZone)
    return iso
  }

  const str = String(value)
  if (str === "—") return str

  if (meta?.valueLabels?.[str]) return str

  if (isIsoDateString(str)) {
    const date = new Date(str)
    if (!Number.isNaN(date.getTime())) {
      if (meta?.valueType === "date") return toFilterDateKey(str, timeZone)
      return date.toISOString()
    }
  }

  return str
}

export function formatFilterDisplayValue(
  value: unknown,
  meta: FilterColumnMeta | undefined,
  timeZone: string
): string {
  if (value == null || value === "") return "—"

  const str = normalizeFilterValue(value, meta, timeZone)
  if (str === "—") return str

  if (meta?.valueLabels?.[str]) return meta.valueLabels[str]

  const raw = value instanceof Date ? value.toISOString() : String(value)
  const asDate =
    meta?.valueType === "date" ||
    meta?.valueType === "datetime" ||
    isIsoDateString(raw)

  if (asDate) {
    return meta?.valueType === "datetime"
      ? formatDisplayDateTime(raw, timeZone)
      : formatDisplayDate(raw, timeZone)
  }

  return str
}
