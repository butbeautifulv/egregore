import type { PlaybookHit, PlaybookSearchResult } from "@/lib/types"

const DISPLAY_SKILL_LIMIT = 12

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined
}

function parseSkills(raw: unknown): PlaybookHit[] {
  if (!Array.isArray(raw)) return []
  const skills: PlaybookHit[] = []
  for (const item of raw) {
    if (!item || typeof item !== "object") continue
    const record = item as Record<string, unknown>
    const id = asString(record.id)
    const name = asString(record.name)
    if (!id && !name) continue
    const hit: PlaybookHit = {
      id: id ?? name ?? "skill",
      name: name ?? id ?? "skill",
    }
    const description = asString(record.description)
    if (description) hit.description = description
    if (Array.isArray(record.attack_ids)) {
      hit.attack_ids = record.attack_ids.map(String).filter(Boolean)
    }
    skills.push(hit)
  }
  return skills.slice(0, DISPLAY_SKILL_LIMIT)
}

export function parsePlaybookSearchPreview(outputPreview: string): PlaybookSearchResult | null {
  const trimmed = outputPreview.trim()
  if (!trimmed.startsWith("{")) return null
  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>
    const skills = parseSkills(parsed.skills)
    const query = asString(parsed.query) ?? ""
    const count =
      typeof parsed.count === "number"
        ? parsed.count
        : skills.length
    const subdomain = asString(parsed.subdomain)
    return {
      query,
      count,
      skills,
      ...(subdomain ? { subdomain } : {}),
    }
  } catch {
    return null
  }
}

export function isPlaybookSearchTool(name: string): boolean {
  return name === "playbook_search" || name.startsWith("playbook_search ")
}

export function playbookSearchQuery(tool: {
  tool_args?: { query?: string }
  playbook_result?: PlaybookSearchResult
}): string {
  return tool.playbook_result?.query ?? tool.tool_args?.query ?? ""
}
