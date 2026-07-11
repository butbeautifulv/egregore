"use client"

import { useMemo } from "react"

import { MermaidDiagram } from "@/components/mermaid-diagram"
import { StructuredFieldRow } from "@/components/structured-field-row"
import { formatJsonLabel, isPlainObject } from "@/lib/json-display"
import { buildPlannerMermaidChart } from "@/lib/planner-plan-mermaid"
import { JsonPayloadView } from "@/components/json-payload-view"
import { Badge } from "@/vendor/gui/ui/badge"

function asString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string" && item.length > 0)
}

function asStringMap(value: unknown): Record<string, string> {
  if (!isPlainObject(value)) return {}
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, entry]) => entry !== undefined && entry !== null)
      .map(([key, entry]) => [key, String(entry)]),
  )
}

function asDependsOn(value: unknown): Record<string, string[]> {
  if (!isPlainObject(value)) return {}
  const result: Record<string, string[]> = {}
  for (const [key, entry] of Object.entries(value)) {
    if (Array.isArray(entry)) {
      result[key] = entry.map(String)
    } else if (typeof entry === "string" && entry) {
      result[key] = [entry]
    }
  }
  return result
}

export function PlannerPlanView({ data }: { data: Record<string, unknown> }) {
  const personas = asStringList(data.personas)
  const subGoals = asStringMap(data.sub_goals)
  const dependsOn = asDependsOn(data.depends_on)
  const rationale = asString(data.rationale)
  const executionMode = asString(data.execution_mode)
  const synthesisPersona = asString(data.synthesis_persona)

  const knownKeys = new Set([
    "personas",
    "sub_goals",
    "depends_on",
    "rationale",
    "execution_mode",
    "synthesis_persona",
  ])
  const extra = Object.fromEntries(
    Object.entries(data).filter(([key, value]) => !knownKeys.has(key) && value !== undefined && value !== null),
  )

  const mermaidChart = useMemo(
    () =>
      buildPlannerMermaidChart({
        personas,
        subGoals,
        dependsOn,
        executionMode,
        synthesisPersona,
      }),
    [personas, subGoals, dependsOn, executionMode, synthesisPersona],
  )

  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {executionMode ? <Badge variant="outline">mode: {executionMode}</Badge> : null}
        {synthesisPersona ? <Badge variant="secondary">synthesis: {synthesisPersona}</Badge> : null}
        {personas.length > 0 ? <Badge variant="outline">{personas.length} personas</Badge> : null}
      </div>

      {personas.length > 0 ? (
        <div className="space-y-3">
          <p className="text-xs font-medium">Personas</p>
          <ol className="space-y-3">
            {personas.map((persona, index) => {
              const subGoal = subGoals[persona]
              const dependencies = dependsOn[persona] ?? []
              return (
                <li key={persona} className="border p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{index + 1}. {persona}</Badge>
                    {dependencies.length > 0 ? (
                      <span className="text-muted-foreground text-xs">
                        depends on {dependencies.join(", ")}
                      </span>
                    ) : null}
                  </div>
                  {subGoal ? (
                    <div className="space-y-1">
                      <p className="text-xs font-medium">Sub-goal</p>
                      <p className="text-muted-foreground leading-relaxed">{subGoal}</p>
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-xs italic">No sub-goal recorded.</p>
                  )}
                </li>
              )
            })}
          </ol>
        </div>
      ) : null}

      {Object.keys(subGoals).some((persona) => !personas.includes(persona)) ? (
        <div className="space-y-2">
          <p className="text-xs font-medium">Additional sub-goals</p>
          <div className="space-y-2">
            {Object.entries(subGoals)
              .filter(([persona]) => !personas.includes(persona))
              .map(([persona, subGoal]) => (
                <div key={persona} className="border p-3">
                  <Badge variant="outline" className="mb-2">
                    {persona}
                  </Badge>
                  <p className="text-muted-foreground leading-relaxed">{subGoal}</p>
                </div>
              ))}
          </div>
        </div>
      ) : null}

      {rationale ? (
        <StructuredFieldRow title="Rationale">
          <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">{rationale}</p>
        </StructuredFieldRow>
      ) : null}

      {Object.keys(extra).length > 0 ? (
        <JsonPayloadView data={extra} title="Additional planner fields" />
      ) : null}

      {personas.length === 0 && !rationale && Object.keys(extra).length === 0 ? (
        <JsonPayloadView data={data} />
      ) : null}

      {mermaidChart ? (
        <div className="space-y-2 border-t pt-4">
          <p className="text-xs font-medium">Execution plan</p>
          <MermaidDiagram chart={mermaidChart} />
        </div>
      ) : null}
    </div>
  )
}

export function PlannerPlanSummary({
  plannerPlan,
  plannerSubGoals = {},
  plannerDependsOn = {},
  plannerRationale,
  executionMode,
  synthesisPersona,
}: {
  plannerPlan?: string[] | null
  plannerSubGoals?: Record<string, string>
  plannerDependsOn?: Record<string, string[]>
  plannerRationale?: string
  executionMode?: string | null
  synthesisPersona?: string | null
}) {
  if (!plannerPlan?.length && !plannerRationale) return null

  return (
    <div className="mb-4 space-y-3 border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium">Planner output</p>
        {executionMode ? <Badge variant="outline">{formatJsonLabel(executionMode)}</Badge> : null}
        {synthesisPersona ? <Badge variant="secondary">synthesis: {synthesisPersona}</Badge> : null}
      </div>
      <PlannerPlanView
        data={{
          personas: plannerPlan ?? [],
          sub_goals: plannerSubGoals,
          depends_on: plannerDependsOn,
          rationale: plannerRationale ?? "",
          execution_mode: executionMode ?? null,
          synthesis_persona: synthesisPersona ?? null,
        }}
      />
    </div>
  )
}
