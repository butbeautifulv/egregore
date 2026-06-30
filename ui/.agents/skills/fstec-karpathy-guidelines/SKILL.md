---
name: fstec-karpathy-guidelines
description: >-
  Karpathy-inspired behavioral guidelines adapted for FSTEC — phased plans,
  branch-per-stream, critic gate, and verifiable DoD. Use when planning,
  implementing, or reviewing any FSTEC change.
license: MIT
---

# FSTEC + Karpathy guidelines

Behavioral guidelines merged with FSTEC project rules ([AGENTS.md](../../../AGENTS.md)).

**Tradeoff:** Caution over speed on non-trivial work.

| Role | Focus |
|------|-------|
| **Orchestrator / critic** | Plan compliance, security, build green |
| **Implementer** | Phase plan scope only; commit on branch |

## 1. Think before coding

Read master plan ([docs/plans/fstec_master.plan.md](../../../docs/plans/fstec_master.plan.md)) and phase plan. State context: `public`, `admin`, `api`, `lib`.

For UI work, read [.agents/skills/shadcn/SKILL.md](../shadcn/SKILL.md) first.

## 2. Simplicity first

Minimum code for the phase goal. No speculative features.

## 3. Surgical changes

Touch only phase plan files. Match existing patterns in `app/` and `lib/`.

## 4. Goal-driven execution

Map deliverables to:

```text
npm run typecheck
npm run lint
npm run build
```

Plus curl smokes or UI checks from phase plan.

## Planning rhythm

Master plan → Phase plan → Branch `fstec/phase-NN-slug` → Implement → PR → Critic → Merge → Update master plan.

## Metacognition

On failure: 5 Whys, reproduce at gemba (`npm run dev`, curl admin + public token APIs, Postgres), minimal fix, Kaizen note.
