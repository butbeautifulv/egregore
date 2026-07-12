# Shadow → enforce rollout (OpenFGA)

## Preconditions

1. `make fga-validate` green locally and in CI.
2. `scripts/migrate_default_workspaces.py` executed for every org.
3. `scripts/seed_datasource_fga.py` executed for datasource tuples.
4. `scripts/sync_idp_membership.py` wired (cron/Helm job) for org membership.

## Staged enablement

| Stage | `AUTHZ_MODE` | Goal |
|-------|--------------|------|
| 1 | `off` | Local dev unchanged |
| 2 | `shadow` | Log denies; no user impact |
| 3 | `shadow` + backfill | Fix tuple gaps from metrics |
| 4 | `enforce` | Block denies in prod |

## Metrics baseline (Grafana)

- `cys_authz_deny_total` rate by `relation`
- `cys_authz_error_total` should stay near zero
- Worker traces include `workspace_id` and `authz_decision`

## Route checklist before enforce

- [ ] Work-order / engagement detail, memory, events
- [ ] Investigations list/detail/jobs
- [ ] Follow-up create (`can_operate`)
- [ ] Workspace admin (invite, grant, revoke, fork)
- [ ] Worker gateway invoke carries `workspace_id`
- [ ] Spawn scope: forked + platform_readonly only
