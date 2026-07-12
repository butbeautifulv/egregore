export function truncateNavLabel(text: string, maxLen = 40): string {
  const trimmed = text.trim()
  if (!trimmed) return ""
  if (trimmed.length <= maxLen) return trimmed
  return `${trimmed.slice(0, maxLen - 1)}…`
}
