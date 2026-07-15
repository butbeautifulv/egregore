# shadcn/create reference — preset `b3Rq8QejA`

Visual + layout reference for Egregore Operator UI. **Not** the theme preset itself (already applied via `npx shadcn apply b3Rq8QejA`).

## Live URLs

| URL | What you see |
|-----|----------------|
| [create?preset=b3Rq8QejA](https://ui.shadcn.com/create?preset=b3Rq8QejA) | Theme editor + default preview |
| [create?preset=b3Rq8QejA&item=preview](https://ui.shadcn.com/create?preset=b3Rq8QejA&item=preview) | Card grid (**tab 02**) — close the onboarding popup once |

Preset decode (`meta/preset-decode.txt`): **Lyra** style, **neutral** base, **lime** theme, Inter, Lucide.

## What is in this folder

| Path | Contents |
|------|----------|
| `blocks/preview/` | Card grid from `item=preview` (tab **02**): `style-overview`, `typography-specimen`, `ui-elements`, `observability-card`, … |
| `blocks/preview-02/` | Dashboard / sidebar layout (tab **01** on create site) |
| `blocks/preview-03/` | Chat-style cards (tool/reasoning/sources) |
| `registry-json/` | Official `base-lyra` registry payloads (`preview*.json`) — same preset, paths rewritten to `@/registry/base-lyra/...` |
| `create-ui/` | shadcn/create shell (`preview-switcher.tsx`, layout helpers) |
| `meta/` | Preset decode + source URLs |

Source: [shadcn-ui/ui](https://github.com/shadcn-ui/ui) `apps/v4/registry/bases/radix/blocks/preview*`. Lyra preset serves them as `base-lyra` in the registry; component markup is identical.

## Usage in Egregore UI

1. Open a card under `blocks/preview/cards/` — copy layout, spacing, button placement.
2. Reimplement with existing `@/vendor/gui` + shadcn components already in the app (do not import `@/registry/...` paths verbatim).
3. Keep `data-gui-style="lyra"` and preset `b3Rq8QejA` tokens from `app/globals.css`.

## Refresh

```bash
./scripts/sync-shadcn-create-ref.sh
```
