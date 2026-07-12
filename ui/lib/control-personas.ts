/** Mirrors cys_core/domain/agents/control.py CONTROL_PERSONAS. */
export const CONTROL_PERSONAS = new Set(["planner", "critic", "coordinator"])

export function isControlPersona(name: string): boolean {
  return CONTROL_PERSONAS.has(name)
}
