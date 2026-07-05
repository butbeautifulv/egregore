"use client"

import { useEffect, useMemo, useState } from "react"

import {
  getProfilePolicy,
  listCatalogEvaluations,
  listCatalogProfiles,
  type CatalogEvaluation,
  type CatalogProfile,
} from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Alert, AlertDescription } from "@/vendor/gui/ui/alert"
import { Field, FieldGroup, FieldLabel } from "@/vendor/gui/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/vendor/gui/ui/select"
import { PageSection } from "@/components/page-section"

function profileLabel(profile: CatalogProfile) {
  return profile.name ? `${profile.name} (${profile.id})` : profile.id
}

function evalMap(rows: CatalogEvaluation[]) {
  return Object.fromEntries(rows.map((r) => [r.persona, r]))
}

export default function ProfileComparePage() {
  const [profiles, setProfiles] = useState<CatalogProfile[]>([])
  const [leftId, setLeftId] = useState("")
  const [rightId, setRightId] = useState("")
  const [leftEvals, setLeftEvals] = useState<CatalogEvaluation[]>([])
  const [rightEvals, setRightEvals] = useState<CatalogEvaluation[]>([])
  const [leftPolicy, setLeftPolicy] = useState<Record<string, unknown>>({})
  const [rightPolicy, setRightPolicy] = useState<Record<string, unknown>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const { profiles: loaded } = await listCatalogProfiles()
        if (cancelled) return
        setProfiles(loaded)
        if (loaded.length >= 2) {
          setLeftId(loaded[0].id)
          setRightId(loaded[1].id)
        } else if (loaded.length === 1) {
          setLeftId(loaded[0].id)
        }
      } catch (exc) {
        if (!cancelled) {
          setError(formatApiError(exc, "Failed to load profiles"))
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!leftId || !rightId) return
    let cancelled = false
    ;(async () => {
      try {
        const [le, re, lp, rp] = await Promise.all([
          listCatalogEvaluations(leftId),
          listCatalogEvaluations(rightId),
          getProfilePolicy(leftId),
          getProfilePolicy(rightId),
        ])
        if (cancelled) return
        setLeftEvals(le.evaluations)
        setRightEvals(re.evaluations)
        setLeftPolicy(lp.policy ?? {})
        setRightPolicy(rp.policy ?? {})
        setError(null)
      } catch (exc) {
        if (!cancelled) {
          setError(formatApiError(exc, "Failed to compare profiles"))
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [leftId, rightId])

  const personas = useMemo(() => {
    const left = evalMap(leftEvals)
    const right = evalMap(rightEvals)
    return Array.from(new Set([...Object.keys(left), ...Object.keys(right)])).sort()
  }, [leftEvals, rightEvals])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Profile compare"
        description="Side-by-side persona trust and policy diff for catalog profiles."
      />

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <FieldGroup className="grid gap-4 md:grid-cols-2">
        <Field>
          <FieldLabel>Profile A</FieldLabel>
          <Select value={leftId} onValueChange={setLeftId}>
            <SelectTrigger>
              <SelectValue placeholder="Select profile" />
            </SelectTrigger>
            <SelectContent>
              {profiles.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {profileLabel(p)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel>Profile B</FieldLabel>
          <Select value={rightId} onValueChange={setRightId}>
            <SelectTrigger>
              <SelectValue placeholder="Select profile" />
            </SelectTrigger>
            <SelectContent>
              {profiles.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {profileLabel(p)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </FieldGroup>

      <div className="grid gap-4 lg:grid-cols-2">
        <PageSection className="p-4">
          <h3 className="mb-3 text-sm font-medium">Persona trust (A vs B)</h3>
          <ul className="space-y-2 text-sm">
            {personas.map((persona) => {
              const a = evalMap(leftEvals)[persona]
              const b = evalMap(rightEvals)[persona]
              const delta =
                a && b ? ((b.empirical_trust - a.empirical_trust) * 100).toFixed(1) : "—"
              return (
                <li key={persona} className="flex justify-between gap-2 border-b pb-2">
                  <span className="font-medium">{persona}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {a ? `${(a.empirical_trust * 100).toFixed(0)}%` : "—"} →{" "}
                    {b ? `${(b.empirical_trust * 100).toFixed(0)}%` : "—"} ({delta}%)
                  </span>
                </li>
              )
            })}
            {personas.length === 0 ? (
              <li className="text-muted-foreground">No overlapping persona eval data.</li>
            ) : null}
          </ul>
        </PageSection>

        <PageSection className="p-4">
          <h3 className="mb-3 text-sm font-medium">Policy JSON (read-only)</h3>
          <div className="grid gap-3 md:grid-cols-2">
            <pre className="bg-muted max-h-64 overflow-auto rounded-md p-2 text-xs">
              {JSON.stringify(leftPolicy, null, 2)}
            </pre>
            <pre className="bg-muted max-h-64 overflow-auto rounded-md p-2 text-xs">
              {JSON.stringify(rightPolicy, null, 2)}
            </pre>
          </div>
        </PageSection>
      </div>
    </div>
  )
}
