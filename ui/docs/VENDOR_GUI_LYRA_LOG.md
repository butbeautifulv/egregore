# Vendor GUI — radix-lyra adaptation log

**Date:** 2026-06-30 (updated)  
**Project:** egregore Operator UI (`projects/egregore/ui`)

## Preset (source of truth)

| Field | Value |
|-------|-------|
| Code | `b3Rq8QejA` |
| URL | https://ui.shadcn.com/create?preset=b3Rq8QejA |
| Style | lyra (`radix-lyra`) |
| baseColor | neutral |
| theme | lime |
| chartColor | lime |
| font | inter |
| radius | default |

Apply to the project:

```bash
cd projects/egregore/ui
npx shadcn@latest apply b3Rq8QejA --yes
node scripts/apply-vendor-lyra-adaptation.mjs
```

Verify: `npx shadcn@latest preset resolve` → `b3Rq8QejA`.

## Context

| Source | Style | `components.json` |
|--------|-------|-------------------|
| `shared/gui` → `vendor/gui` (via `vendor-gui.sh`) | **radix-nova** | FSTEC: `radix-nova` |
| `components/ui` (shadcn apply) | **radix-lyra** | Egregore: `radix-lyra` |

FSTEC (`projects/tabula/fstec`) and `shared/gui` stay on **nova**. Egregore adapts the vendored copy to **lyra** after each sync so screens do not mix square buttons with rounded cards/inputs.

## Nova → Lyra rules (class tokens)

| Nova (vendor default) | Lyra (canonical) |
|-----------------------|------------------|
| `rounded-lg`, `rounded-md`, `rounded-xl`, `rounded-4xl` | `rounded-none` or `rounded-sm` per shadcn Lyra output |
| `rounded-[min(var(--radius-md),…)]` | `rounded-none` |
| `ring-3`, `ring-[3px]` | `ring-1` |
| `focus-visible:ring-3` | `focus-visible:ring-1` |
| `aria-invalid:ring-3` | `aria-invalid:ring-1` |
| `hover:bg-primary/90` | `hover:bg-primary/80` |
| Base `text-sm` on controls | `text-xs` (see Lyra button/card) |
| `in-data-[slot=button-group]:rounded-lg` | removed / `rounded-none` |

**CSS:** `app/globals.css` is owned by `shadcn apply` (lime theme + neutral baseColor). Do not hand-edit color tokens unless changing the preset.

## Canonical reference

- [`components/ui/button.tsx`](../components/ui/button.tsx) — Lyra primitive from preset apply
- All other Lyra primitives: `components/ui/<name>.tsx` (reinstalled by `shadcn apply`)

## Files adapted

### `vendor/gui/ui/` (from `components/ui/` via script)

alert, alert-dialog, avatar, badge, breadcrumb, button, card, chart, checkbox, command, dialog, dropdown-menu, empty, field, input, input-group, label, popover, scroll-area, select, separator, sheet, sidebar, skeleton, sonner, table, tabs, textarea, tooltip

### `vendor/gui/ui/` (token map only — no shadcn pair)

collapsible, slider, spinner, table-skeleton, typography

### `vendor/gui/layout/`

attachment-gallery, data-table-shell, form-error-slot, page-header

### `vendor/gui/shell/`

shell-brand, shell-sidebar, shell-nav-main, shell-breadcrumb

### Unchanged

`vendor/gui/motion/*`, `vendor/gui/theme/*`, `vendor/gui/hooks/*` — no hardcoded nova radius classes.

## Reproduce

```bash
cd projects/egregore/ui

# 1. Apply preset (theme + components)
npx shadcn@latest apply b3Rq8QejA --yes

# 2. (optional) Re-sync from shared/gui
./scripts/vendor-gui.sh

# 3. Copy Lyra classes to vendor/gui
node scripts/apply-vendor-lyra-adaptation.mjs
```

## Re-sync policy

After **every** `./scripts/vendor-gui.sh`:

1. `node scripts/rewrite-vendor-imports.mjs`
2. `node scripts/apply-vendor-lyra-adaptation.mjs`

Never commit vendor/gui UI primitives with `rounded-lg` or `ring-3` — the adaptation script exits non-zero if guard fails.

## App layer

Screen components import from `@/vendor/gui/ui/*` (not `@/components/ui/*`). Use `PageHeader` for page titles; avoid `text-base` / ad-hoc `text-sm` overrides on Lyra primitives.

## Visual checklist

- [ ] Home — chat panel: Button, Input, Card same corner style
- [ ] Investigations table — Badge, Table headers
- [ ] Investigation detail — Card, persona stepper badges
- [ ] Sidebar — menu items, brand block, lime primary CTA
- [ ] Dialogs / dropdowns — square Lyra overlays
- [ ] Compare with https://ui.shadcn.com/create?preset=b3Rq8QejA&item=preview
