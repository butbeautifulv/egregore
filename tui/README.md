# Egregore Operator TUI

Terminal operator console for Egregore — Go + [Bubble Tea](https://github.com/charmbracelet/bubbletea).

Master-detail **Operator Console** layout (lazydocker-style): left panel sections, right detail tabs, persistent keybar footer.

Mirrors the web UI operator flows per [../docs/operator-console-contract.md](../docs/operator-console-contract.md).

## Prerequisites

- Go 1.22+
- Egregore API running (default `http://127.0.0.1:8080`)

```bash
cd projects/egregore
docker compose up -d
./scripts/dev.sh
```

## Quick start

```bash
cd tui && make run
# or from projects/egregore:
make run
```

## Layout

```
┌─────────────────┬──────────────────────────────────┐
│ Status          │ Chat · Jobs · Findings · …       │
│ Work orders     │        [detail viewport]         │
│ Approvals       │                                  │
│ Queues          │                                  │
│ Catalog         │                                  │
├─────────────────┴──────────────────────────────────┤
│ ↑↓ select · Tab focus · ←→ tabs · q quit           │
└────────────────────────────────────────────────────┘
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `EGREGORE_API_URL` | `http://127.0.0.1:8080` | API base URL |
| `EGREGORE_API_TOKEN` | `egregore-demo-token` | Bearer token |
| `EGREGORE_TENANT_ID` | `default` | Tenant |
| `EGREGORE_SSE` | `1` | Engagement + status SSE |
| `EGREGORE_API_TIMEOUT_MS` | `20000` | REST timeout |
| `EGREGORE_TUI_CONSOLE` | `1` | Operator console layout (default on) |
| `EGREGORE_TUI_LEGACY` | `0` | Set `1` for old full-screen `1`–`4` navigation |

## Navigation (console)

| Key | Action |
|-----|--------|
| `Tab` | Left panel ↔ right detail |
| `1`–`5` | Jump to section (Status / Work orders / Approvals / Queues / Catalog) |
| `↑↓` / `j`/`k` | Select item in active section |
| `g` / `G` | Jump top / bottom of list |
| `Enter` | Open work order or catalog detail |
| `n` | New work order (overlay) |
| `←→` / `[`/`]` | Detail tabs or catalog sub-tabs |
| `a`/`x` | HITL approve/reject |
| `m` | Follow-up composer (Chat tab, closed WO) |
| `r` | Refresh section / toggle reasoning |
| `/` | Filter catalog memory |
| `?` / `F1` | Help |
| `q` | Quit |

## Feature parity

| Feature | Web UI | TUI |
|---------|--------|-----|
| Work orders list + start | yes | yes |
| Live chat (SSE) | yes | yes (Chat tab) |
| Jobs / findings / intake | yes | yes (detail tabs) |
| Follow-ups | yes | yes (Chat tab timeline + composer) |
| Follow-up plan mode | yes | yes (`follow_up_plan_started` disables composer until `follow_up_plan_complete`) |
| HITL inline + queue | yes | yes |
| Catalog browse + detail | yes | yes |
| Status charts / mermaid | yes | no (JSON text) |

REST paths prefer `/v1/work-orders`; on `404` fall back to `/v1/engagements` (same IDs).

## Tests

```bash
make test
```

## Stack

- [Bubble Tea](https://github.com/charmbracelet/bubbletea) — TUI framework
- [lipgloss](https://github.com/charmbracelet/lipgloss) — styling
- [bubbles](https://github.com/charmbracelet/bubbles) — textarea, viewport
