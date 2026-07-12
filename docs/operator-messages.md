# Operator messages (initial + follow-up)

Unified model for the first work-order message and closed-WO follow-ups.

## Fields

- `intent_mode`: `plan | qa | auto | orchestrate` — operator intent (distinct from `EngagementMode.async`).
- `follow_up_id`:
  - Initial: `wo-{engagement_id}`
  - Follow-up: `fu-{uuid}`

## Mode matrix

| intent | Context | work_kind | Behavior |
|--------|---------|-----------|----------|
| plan | initial | planner | meta_llm → personas → synthesis → closed |
| auto | initial | planner if flag | first-contact default |
| qa | initial | `initial_qa` | consultant advisory, close without pipeline |
| qa | follow-up | `follow_up_qa` | consultant with findings |
| plan | follow-up | `follow_up_plan` | catalog re-plan |
| orchestrate | follow-up | `follow_up_orchestrate` | reinvestigation |
| orchestrate | initial | → plan | v1 coerce |

## Timeline (UI)

1. Initial `wo-*` pair (top)
2. Intake / planner error / agent entries
3. Final report
4. Follow-up `fu-*` pairs (bottom)
5. Composer dock

## SSE

Initial Q&A uses the same events as follow-ups: `follow_up_queued`, `follow_up_complete`, `assistant_*` on `-fu-` jobs.

## Rate limits

`max_follow_ups_per_engagement` counts only operator turns with `fu-*` IDs. Initial `wo-*` is excluded.

## Backward compatibility

`Engagement.goal` remains a denormalized copy. Legacy engagements without conversation memory get a synthetic initial turn from `list_turns`.
