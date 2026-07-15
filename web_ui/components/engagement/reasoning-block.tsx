import type { ChatReasoning } from "@/lib/types"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/vendor/gui/ui/collapsible"

export function ReasoningBlock({ reasoning }: { reasoning: ChatReasoning | null }) {
  if (!reasoning) return null
  const steps = reasoning.reasoning_steps ?? []
  if (!reasoning.current_situation && !steps.length && !reasoning.plan_status) {
    return null
  }

  return (
    <Collapsible defaultOpen className="border p-2">
      <CollapsibleTrigger className="text-muted-foreground text-xs font-medium hover:underline">
        Reasoning
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-2 text-xs">
        {reasoning.plan_status ? (
          <p className="text-muted-foreground">{reasoning.plan_status}</p>
        ) : null}
        {reasoning.current_situation ? (
          <p className="leading-relaxed">{reasoning.current_situation}</p>
        ) : null}
        {steps.length > 0 ? (
          <ol className="text-muted-foreground list-decimal space-y-1 pl-4">
            {steps.map((step, index) => (
              <li key={`${step}-${index}`}>{step}</li>
            ))}
          </ol>
        ) : null}
      </CollapsibleContent>
    </Collapsible>
  )
}
