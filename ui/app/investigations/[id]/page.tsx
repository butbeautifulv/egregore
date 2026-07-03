"use client"

import { useParams } from "next/navigation"

import { InvestigationDetailView } from "@/components/investigation-detail-view"

export default function InvestigationDetailPage() {
  const params = useParams()
  const id = typeof params.id === "string" ? params.id : ""

  return <InvestigationDetailView investigationId={id} />
}
