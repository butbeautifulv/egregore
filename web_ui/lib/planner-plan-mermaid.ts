export type PlannerPlanGraph = {
  personas: string[]
  subGoals?: Record<string, string>
  dependsOn?: Record<string, string[]>
  executionMode?: string | null
  synthesisPersona?: string | null
}

function escapeMermaidLabel(text: string): string {
  return text.replace(/"/g, "'").replace(/[[\]]/g, " ").replace(/[<>]/g, " ")
}

function truncate(text: string, max = 72): string {
  const normalized = text.replace(/\s+/g, " ").trim()
  return normalized.length <= max ? normalized : `${normalized.slice(0, max - 1)}…`
}

function nodeId(persona: string): string {
  return `persona_${persona.replace(/[^a-zA-Z0-9_]/g, "_")}`
}

function nodeLabel(persona: string, subGoal?: string): string {
  const title = escapeMermaidLabel(persona)
  if (!subGoal?.trim()) return title
  return `${title}<br/>${escapeMermaidLabel(truncate(subGoal))}`
}

export function buildPlannerMermaidChart(plan: PlannerPlanGraph): string | null {
  const personas = plan.personas.filter(Boolean)
  if (personas.length === 0) return null

  const subGoals = plan.subGoals ?? {}
  const dependsOn = plan.dependsOn ?? {}
  const synthesis = plan.synthesisPersona?.trim()
  const staged = plan.executionMode === "staged"
  const hasExplicitDeps = Object.values(dependsOn).some((deps) => deps.length > 0)

  const lines: string[] = ["flowchart LR"]
  lines.push(`  start([Work order])`)

  for (const persona of personas) {
    lines.push(`  ${nodeId(persona)}["${nodeLabel(persona, subGoals[persona])}"]`)
  }

  const synthesisInPlan = synthesis ? personas.includes(synthesis) : false
  if (synthesis && !synthesisInPlan) {
    lines.push(
      `  ${nodeId(synthesis)}["${nodeLabel(synthesis, subGoals[synthesis] || "Synthesis")}"]`,
    )
  }

  const edges = new Set<string>()
  const addEdge = (from: string, to: string) => {
    edges.add(`  ${from} --> ${to}`)
  }

  if (hasExplicitDeps) {
    const roots = personas.filter((persona) => !(dependsOn[persona]?.length ?? 0))
    if (roots.length === 0) {
      addEdge("start", nodeId(personas[0]))
    } else {
      for (const root of roots) {
        addEdge("start", nodeId(root))
      }
    }
    for (const persona of personas) {
      for (const dependency of dependsOn[persona] ?? []) {
        if (personas.includes(dependency)) {
          addEdge(nodeId(dependency), nodeId(persona))
        }
      }
    }
  } else if (staged) {
    addEdge("start", nodeId(personas[0]))
    for (let index = 0; index < personas.length - 1; index += 1) {
      addEdge(nodeId(personas[index]), nodeId(personas[index + 1]))
    }
  } else {
    for (const persona of personas) {
      addEdge("start", nodeId(persona))
    }
  }

  if (synthesis && !synthesisInPlan) {
    const synthId = nodeId(synthesis)
    if (staged && !hasExplicitDeps) {
      addEdge(nodeId(personas[personas.length - 1]), synthId)
    } else if (hasExplicitDeps) {
      const terminal = personas.filter(
        (persona) => !personas.some((other) => (dependsOn[other] ?? []).includes(persona)),
      )
      for (const persona of terminal.length > 0 ? terminal : [personas[personas.length - 1]]) {
        addEdge(nodeId(persona), synthId)
      }
    } else {
      for (const persona of personas) {
        addEdge(nodeId(persona), synthId)
      }
    }
  }

  lines.push(...edges)
  return lines.join("\n")
}
