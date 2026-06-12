# Refactor Coverage Map

Regenerate: `./scripts/coverage_report.sh`

## Gated (CI fail-under)

| Package | Target | Gate |
|---------|--------|------|
| `cys_core/domain` | 100% | arch-gate.yml + adversarial-gate.yml |

## Report-only (target gates)

| Package | Target | Status |
|---------|--------|--------|
| `cys_core/application` | ≥90% | CI report |
| `cys_core/infrastructure` | ≥95% | CI report |
| `interfaces/` | report | via `coverage_report.sh` |

## Delivery layout (R5.10 DONE)

All delivery code under `interfaces/` — root shims removed.

## Test suites by layer

| Suite | Path | Marker |
|-------|------|--------|
| Domain unit | `tests/domain/` | unit |
| Port contracts | `tests/contracts/` | unit |
| Integration golden paths | `tests/integration/` | integration |
| Adversarial | `tests/adversarial/` | adversarial |
