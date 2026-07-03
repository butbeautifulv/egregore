"use client"

import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import {
  getProfilePolicy,
  listCatalogEvaluations,
  listCatalogProfiles,
  putProfilePolicy,
  type CatalogEvaluation,
  type CatalogProfile,
} from "@/lib/api-client"
import { formatApiError } from "@/lib/format-api-error"
import { DataTableShell } from "@/vendor/gui/layout/data-table-shell"
import { EmptyTableState } from "@/vendor/gui/layout/empty-table-state"
import { PageHeader } from "@/vendor/gui/layout/page-header"
import { Alert, AlertDescription } from "@/vendor/gui/ui/alert"
import { Badge } from "@/vendor/gui/ui/badge"
import { Button } from "@/vendor/gui/ui/button"
import { Field, FieldGroup, FieldLabel } from "@/vendor/gui/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/vendor/gui/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/vendor/gui/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/vendor/gui/ui/tabs"
import { Textarea } from "@/vendor/gui/ui/textarea"

function TrustBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div className="flex min-w-32 items-center gap-2">
      <div className="bg-muted h-1.5 flex-1 overflow-hidden rounded-full">
        <div className="bg-primary h-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-muted-foreground w-10 text-right text-xs tabular-nums">{pct}%</span>
    </div>
  )
}

export default function CatalogPage() {
  const [rows, setRows] = useState<CatalogEvaluation[]>([])
  const [profiles, setProfiles] = useState<CatalogProfile[]>([])
  const [profileId, setProfileId] = useState("")
  const [policyJson, setPolicyJson] = useState("")
  const [policyDraft, setPolicyDraft] = useState("")
  const [evalError, setEvalError] = useState<string | null>(null)
  const [policyError, setPolicyError] = useState<string | null>(null)
  const [loadingEvals, setLoadingEvals] = useState(true)
  const [loadingPolicy, setLoadingPolicy] = useState(false)
  const [savingPolicy, setSavingPolicy] = useState(false)

  const loadPolicy = useCallback(async (id: string) => {
    if (!id) return
    setLoadingPolicy(true)
    setPolicyError(null)
    try {
      const data = await getProfilePolicy(id)
      const formatted = JSON.stringify(data.policy ?? {}, null, 2)
      setPolicyJson(formatted)
      setPolicyDraft(formatted)
    } catch (exc) {
      setPolicyError(formatApiError(exc, "Failed to load policy"))
    } finally {
      setLoadingPolicy(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [evalResponse, profileResponse] = await Promise.all([
          listCatalogEvaluations(),
          listCatalogProfiles(),
        ])
        if (cancelled) return
        setRows(evalResponse.evaluations)
        setProfiles(profileResponse.profiles)
        setEvalError(null)
        const firstId = profileResponse.profiles[0]?.id
        if (firstId) {
          setProfileId(firstId)
          const data = await getProfilePolicy(firstId)
          if (cancelled) return
          const formatted = JSON.stringify(data.policy ?? {}, null, 2)
          setPolicyJson(formatted)
          setPolicyDraft(formatted)
        }
      } catch (exc) {
        if (cancelled) return
        setEvalError(formatApiError(exc, "Failed to load evaluations"))
      } finally {
        if (!cancelled) {
          setLoadingEvals(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  function onProfileChange(id: string) {
    setProfileId(id)
    void loadPolicy(id)
  }

  async function savePolicy() {
    if (!profileId) return
    setPolicyError(null)
    let policy: Record<string, unknown>
    try {
      policy = JSON.parse(policyJson) as Record<string, unknown>
    } catch {
      toast.error("Invalid JSON — fix syntax before saving")
      return
    }
    setSavingPolicy(true)
    try {
      await putProfilePolicy(profileId, policy)
      setPolicyDraft(policyJson)
      toast.success("Policy saved")
    } catch (exc) {
      const message = formatApiError(exc, "Save failed")
      setPolicyError(message)
      toast.error(message)
    } finally {
      setSavingPolicy(false)
    }
  }

  function resetPolicy() {
    setPolicyJson(policyDraft)
    toast.message("Changes discarded")
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Catalog quality"
        description="Persona trust scores and profile policy."
      />

      <Tabs defaultValue="evaluations">
        <TabsList variant="line">
          <TabsTrigger value="evaluations">Evaluations</TabsTrigger>
          <TabsTrigger value="policy">Profile policy</TabsTrigger>
        </TabsList>

        <TabsContent value="evaluations" className="mt-4">
          {evalError ? (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{evalError}</AlertDescription>
            </Alert>
          ) : null}
          {loadingEvals ? (
            <p className="text-muted-foreground text-sm">Loading evaluations…</p>
          ) : rows.length === 0 && !evalError ? (
            <EmptyTableState
              title="No evaluations"
              description="No persona quality data in the catalog yet."
            />
          ) : (
            <DataTableShell>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Persona</TableHead>
                    <TableHead>Trust</TableHead>
                    <TableHead>Samples</TableHead>
                    <TableHead>Declared</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.persona}>
                      <TableCell className="font-medium">{row.persona}</TableCell>
                      <TableCell>
                        <TrustBar value={row.empirical_trust} />
                      </TableCell>
                      <TableCell className="tabular-nums">{row.sample_size}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{row.declared_trust_level}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </DataTableShell>
          )}
        </TabsContent>

        <TabsContent value="policy" className="mt-4">
          {policyError ? (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{policyError}</AlertDescription>
            </Alert>
          ) : null}
          <FieldGroup className="flex flex-col gap-3">
            <Field>
              <FieldLabel>Profile</FieldLabel>
              <div className="flex flex-wrap items-center gap-2">
                <Select value={profileId} onValueChange={onProfileChange} disabled={profiles.length === 0}>
                  <SelectTrigger className="w-full max-w-xs">
                    <SelectValue placeholder="Select profile" />
                  </SelectTrigger>
                  <SelectContent>
                    {profiles.map((profile) => (
                      <SelectItem key={profile.id} value={profile.id}>
                        {profile.name ?? profile.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void loadPolicy(profileId)}
                  disabled={!profileId || loadingPolicy}
                >
                  Reload
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={resetPolicy}
                  disabled={!profileId || policyJson === policyDraft}
                >
                  Reset
                </Button>
                <Button type="button" onClick={() => void savePolicy()} disabled={!profileId || savingPolicy}>
                  Save
                </Button>
              </div>
            </Field>
            <Textarea
              className="min-h-72 font-mono text-xs"
              value={policyJson}
              onChange={(e) => setPolicyJson(e.target.value)}
              placeholder={loadingPolicy ? "Loading policy…" : "Profile policy JSON"}
              disabled={!profileId || loadingPolicy}
            />
          </FieldGroup>
        </TabsContent>
      </Tabs>
    </div>
  )
}
