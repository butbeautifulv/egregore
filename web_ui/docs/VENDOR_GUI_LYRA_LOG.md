# Vendor GUI — radix-lyra profile

**Date:** 2026-07-01 (updated)  
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
```

Verify: `npx shadcn@latest preset resolve` → `b3Rq8QejA`.

## Context

| Source | Style | Activation |
|--------|-------|------------|
| `shared/gui` | semantic tokens | default nova; lyra via `data-gui-style` |
| Egregore `vendor/gui` | same code as shared/gui | `data-gui-style="lyra"` on `<html>` |
| FSTEC | radix-nova | no attribute |

Lyra geometry and control typography come from [`shared/gui/gui-style-profiles.css`](../../../../shared/gui/gui-style-profiles.css), vendored to `vendor/gui-style-profiles.css` and imported in `app/globals.css`. **No post-sync regex adaptation.**

## Setup

```tsx
// app/layout.tsx
<html lang="en" data-gui-style="lyra" suppressHydrationWarning>
```

```css
/* app/globals.css */
@import "../vendor/gui-style-profiles.css";
```

## Re-sync policy

After **every** `./scripts/vendor-gui.sh`:

1. `node scripts/rewrite-vendor-imports.mjs` (run automatically by `vendor-gui.sh`)
2. Confirm `vendor/gui-style-profiles.css` was copied from `shared/gui`

Do **not** run `apply-vendor-lyra-adaptation.mjs` for token mapping — it is a deprecated no-op.

## Semantic tokens (shared/gui)

See [`shared/gui/docs/gui-style-profiles.md`](../../../../shared/gui/docs/gui-style-profiles.md).

| Nova | Lyra | Token |
|------|------|-------|
| `rounded-lg` | `rounded-none` | `rounded-gui-control` |
| `rounded-xl` | `rounded-none` | `rounded-gui-surface` |
| `rounded-md` | `rounded-none` | `rounded-gui-muted` |
| `ring-3` | `ring-1` | `ring-gui-focus` |
| `text-sm` controls | `text-xs` | `text-gui-ui` / `text-gui-control` |
| `hover:bg-primary/90` | `hover:bg-primary/80` | `hover:bg-primary/[var(--gui-primary-hover-opacity)]` |

## App layer

Screen components import from `@/vendor/gui/ui/*` (not `@/components/ui/*`). Use `PageHeader` for page titles.

## Visual checklist

- [ ] Home — chat panel: Button, Input, Card same corner style
- [ ] Investigations table — Badge, Table headers
- [ ] Investigation detail — Card, persona stepper badges
- [ ] Sidebar — menu items, brand block, lime primary CTA
- [ ] Dialogs / dropdowns — square Lyra overlays
- [ ] Compare with https://ui.shadcn.com/create?preset=b3Rq8QejA&item=preview
