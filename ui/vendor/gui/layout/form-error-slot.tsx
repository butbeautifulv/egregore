export function FormErrorSlot({ error }: { error?: string }) {
  if (!error) return null
  return <div className="text-sm text-destructive">{error}</div>
}

