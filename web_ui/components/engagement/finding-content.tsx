import { JsonPayloadView } from "@/components/json-payload-view"
import { StructuredFieldRow } from "@/components/structured-field-row"
import {
  formatFindingField,
  hasFindingValue,
  isDisplayableFindingKey,
  mergeFindingContext,
} from "@/lib/finding-display"
import { formatJsonLabel, isPlainObject, parseJsonMaybe } from "@/lib/json-display"
import { Badge } from "@/vendor/gui/ui/badge"

function asString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string" && item.length > 0)
}

function firstNonemptyStringList(...values: unknown[]): string[] {
  for (const value of values) {
    const list = asStringList(value)
    if (list.length > 0) return list
  }
  return []
}

function telemetryBadge(level: string) {
  if (!level || level === "rich") return null
  const label = level === "sparse" ? "Low telemetry" : "Metadata only"
  return (
    <span className="bg-amber-500/15 text-amber-700 dark:text-amber-300 px-1.5 py-0.5 text-[10px]">
      {label}
    </span>
  )
}

function FieldValue({ value }: { value: unknown }) {
  if (Array.isArray(value) || isPlainObject(value)) {
    return <JsonPayloadView data={value} boxed={false} />
  }
  if (typeof value === "boolean") {
    return <Badge variant="outline">{value ? "true" : "false"}</Badge>
  }
  if (typeof value === "number") {
    return <code className="text-xs">{value}</code>
  }
  return <p className="text-muted-foreground whitespace-pre-wrap text-sm leading-relaxed">{String(value)}</p>
}

function StringListField({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <StructuredFieldRow title={title}>
      <ul className="text-muted-foreground list-disc space-y-1 pl-4 text-sm">
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </StructuredFieldRow>
  )
}

function RemainingFields({
  data,
  rendered,
}: {
  data: Record<string, unknown>
  rendered: Set<string>
}) {
  const entries = Object.entries(data).filter(
    ([key, value]) => isDisplayableFindingKey(key) && !rendered.has(key) && hasFindingValue(value),
  )
  if (entries.length === 0) return null

  return (
    <>
      {entries.map(([key, value]) => (
        <StructuredFieldRow key={key} title={formatFindingField(key)}>
          <FieldValue value={value} />
        </StructuredFieldRow>
      ))}
    </>
  )
}

export function FindingContent({
  data,
  evidenceManifest,
  profileId: _profileId,
}: {
  data: Record<string, unknown>
  evidenceManifest?: Record<string, unknown>
  profileId?: string
}) {
  const raw = asString(data.raw_response)
  if (raw) {
    const parsed = parseJsonMaybe(raw)
    if (parsed && isPlainObject(parsed)) {
      return <FindingContent data={parsed} evidenceManifest={evidenceManifest} profileId={_profileId} />
    }
    if (!data.summary && !data.finding) {
      return (
        <pre className="bg-muted max-h-96 overflow-auto whitespace-pre-wrap border p-3 text-xs">{raw}</pre>
      )
    }
  }

  const merged = mergeFindingContext(data, evidenceManifest)
  const rendered = new Set<string>()

  const topic = asString(merged.topic)
  const summary =
    asString(merged.summary) ||
    asString(merged.finding) ||
    asString(merged.message) ||
    asString(merged.analysis)
  const risk =
    asString(merged.risk_level) ||
    asString(merged.severity) ||
    asString(merged.priority) ||
    asString(merged.compliance_status) ||
    asString(merged.hunt_status) ||
    asString(merged.containment_status)
  const findingType = asString(merged.finding_type)
  const attackPhase = asString(merged.attack_phase)
  const confidence =
    typeof merged.confidence === "number"
      ? merged.confidence
      : typeof merged.forensic_confidence === "number"
        ? merged.forensic_confidence
        : null
  const recommendations = firstNonemptyStringList(
    merged.recommendations,
    merged.recommended_actions,
    merged.recommended_remediation,
    merged.remediation,
    merged.eradication_steps,
  )
  const timeline = asStringList(merged.timeline)
  const mitreTactics = asStringList(merged.mitre_tactics)
  const mitreTechniques = asStringList(merged.mitre_techniques)
  const references = asStringList(merged.references)
  const evidence = Array.isArray(merged.evidence) ? merged.evidence : []
  const dataGaps = Array.isArray(merged.data_gaps) ? merged.data_gaps : []
  const telemetryLevel = asString(merged.telemetry_level)
  const affectedAssets = Array.isArray(merged.affected_assets)
    ? merged.affected_assets
    : firstNonemptyStringList(merged.affected_assets, merged.affected_systems)

  const mark = (...keys: string[]) => {
    for (const key of keys) rendered.add(key)
  }

  const hasStructuredContent = Object.entries(merged).some(
    ([key, value]) => isDisplayableFindingKey(key) && hasFindingValue(value),
  )

  if (!hasStructuredContent) {
    return <JsonPayloadView data={merged} />
  }

  mark(
    "topic",
    "summary",
    "finding",
    "message",
    "analysis",
    "risk_level",
    "severity",
    "priority",
    "compliance_status",
    "hunt_status",
    "containment_status",
    "confidence",
    "forensic_confidence",
    "finding_type",
    "attack_phase",
    "telemetry_level",
    "recommendations",
    "recommended_actions",
    "recommended_remediation",
    "remediation",
    "eradication_steps",
    "timeline",
    "mitre_tactics",
    "mitre_techniques",
    "references",
    "evidence",
    "data_gaps",
    "affected_assets",
    "affected_systems",
  )

  return (
    <div className="space-y-3 text-sm">
      {risk || confidence !== null || telemetryLevel || findingType || attackPhase ? (
        <div className="flex flex-wrap items-center gap-2">
          {telemetryBadge(telemetryLevel)}
          {findingType ? <Badge variant="outline">type: {findingType}</Badge> : null}
          {attackPhase ? <Badge variant="outline">phase: {attackPhase}</Badge> : null}
          {risk ? <Badge variant="outline">risk: {risk}</Badge> : null}
          {confidence !== null ? (
            <Badge variant="outline">confidence: {(confidence * 100).toFixed(0)}%</Badge>
          ) : null}
          {telemetryLevel ? <Badge variant="outline">telemetry: {telemetryLevel}</Badge> : null}
        </div>
      ) : null}

      {topic ? (
        <StructuredFieldRow title="Topic">
          <p className="leading-relaxed">{topic}</p>
        </StructuredFieldRow>
      ) : null}

      {summary ? (
        <StructuredFieldRow title="Summary">
          <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">{summary}</p>
        </StructuredFieldRow>
      ) : null}

      {mitreTactics.length > 0 || mitreTechniques.length > 0 ? (
        <StructuredFieldRow title="MITRE">
          <div className="text-muted-foreground space-y-1 text-sm">
            {mitreTactics.length > 0 ? <p>Tactics: {mitreTactics.join(", ")}</p> : null}
            {mitreTechniques.length > 0 ? <p>Techniques: {mitreTechniques.join(", ")}</p> : null}
          </div>
        </StructuredFieldRow>
      ) : null}

      <StringListField title="Timeline" items={timeline} />
      <StringListField title="Recommendations" items={recommendations} />
      <StringListField title="References" items={references} />

      {evidence.length > 0 ? (
        <div className="space-y-3">
          <p className="text-xs font-medium">Evidence</p>
          {evidence.map((item, index) => (
            <StructuredFieldRow key={`evidence-${index}`} title={`Evidence ${index + 1}`}>
              {isPlainObject(item) ? (
                <JsonPayloadView data={item} boxed={false} />
              ) : (
                <p className="text-muted-foreground whitespace-pre-wrap text-sm">{String(item)}</p>
              )}
            </StructuredFieldRow>
          ))}
        </div>
      ) : null}

      {dataGaps.length > 0 ? (
        <div className="space-y-3">
          <p className="text-xs font-medium">Data gaps</p>
          {dataGaps.map((gap, index) => {
            if (typeof gap === "string") {
              return (
                <StructuredFieldRow key={`gap-${index}`} title={`Gap ${index + 1}`}>
                  <p className="text-muted-foreground text-sm">{gap}</p>
                </StructuredFieldRow>
              )
            }
            if (isPlainObject(gap)) {
              const field = asString(gap.field) || "unknown"
              const remediation = asString(gap.remediation)
              return (
                <StructuredFieldRow
                  key={`${field}-${index}`}
                  title={formatJsonLabel(field)}
                  action={<Badge variant="outline">gap</Badge>}
                >
                  {remediation ? (
                    <p className="text-muted-foreground text-sm">{remediation}</p>
                  ) : (
                    <JsonPayloadView data={gap} boxed={false} />
                  )}
                </StructuredFieldRow>
              )
            }
            return (
              <StructuredFieldRow key={`gap-${index}`} title={`Gap ${index + 1}`}>
                <p className="text-muted-foreground text-sm">{String(gap)}</p>
              </StructuredFieldRow>
            )
          })}
        </div>
      ) : null}

      {affectedAssets.length > 0 ? (
        <StructuredFieldRow title="Affected assets">
          <ul className="text-muted-foreground list-disc space-y-1 pl-4 text-sm">
            {affectedAssets.map((asset, index) => (
              <li key={index}>{typeof asset === "string" ? asset : JSON.stringify(asset)}</li>
            ))}
          </ul>
        </StructuredFieldRow>
      ) : null}

      <RemainingFields data={merged} rendered={rendered} />
    </div>
  )
}
