# GUI component library (`vendor/gui`)

`vendor/gui` is Egregore's own component library — first-party code that lives and is edited directly in this repo, not a package we depend on or keep in sync with anything external. It originated as a cherry-picked copy of `shared/gui` (the meta-repo's component kit), but that lineage is history at this point: there is no `file:../../shared/gui` dependency, no expectation that `vendor/gui` mirrors upstream, and no requirement to re-sync after changes land in `shared/gui`.

Screen components import from `@/vendor/gui/ui/*` (not `@/components/ui/*`). Use `PageHeader` for page titles.

## Pulling in a change from `shared/gui` (rare, opt-in)

If you deliberately want to pull a specific update from `shared/gui` — e.g. a new primitive that doesn't exist here yet — `scripts/vendor-gui.sh` can still do that one-off import. It is **not** part of the normal workflow and should not be run reflexively.

```bash
# From projects/egregore/web_ui, with a meta-repo checkout available:
./scripts/vendor-gui.sh
```

This runs, in order: rsync from `shared/gui` (with `--delete`) → copy `gui-style-profiles.css` → `rewrite-vendor-imports.mjs` (rewrites `@cxado/gui/` → `@/vendor/gui/`).

**This is destructive to local edits.** Because `vendor/gui` is now hand-edited, `vendor-gui.sh` refuses to run if `vendor/gui` has uncommitted changes — commit or stash them first, then review the diff after running it like any other change, since `rsync --delete` will happily remove local additions that don't exist upstream.

Override the source path when needed:

```bash
GUI_SRC=/path/to/shared/gui/src ./scripts/vendor-gui.sh
```

It rsyncs these paths from `shared/gui/src/`: `shell/`, `theme/`, `motion/`, `hooks/`, `ui/`, `layout/`, `data-table/`, `lib/data-table/`, `lib/datetime/`, `utils.ts`.

## Style profile (Lyra)

The component kit uses semantic style tokens (`rounded-gui-control`, `ring-gui-focus`, …). Egregore activates **radix-lyra** via:

```tsx
<html data-gui-style="lyra">
```

and `@import "../vendor/gui-style-profiles.css"` in `app/globals.css`.

See [VENDOR_GUI_LYRA_LOG.md](VENDOR_GUI_LYRA_LOG.md) for the Lyra profile background. No post-sync `apply-vendor-lyra-adaptation.mjs` token mapping — that script is a deprecated no-op.

## Theme / colors

**Do not** `@import` a `tailwind.preset.css` as the canonical color source — that preset only defines `@theme inline` tokens without full `:root` values.

Canonical theme is preset **`b3Rq8QejA`** (Lyra + neutral baseColor + lime theme). Apply with:

```bash
bunx shadcn@latest apply b3Rq8QejA --yes
```

`app/globals.css` and `components.json` are updated by the CLI.

## Adding components

Add new components directly under `vendor/gui/` like any other first-party module — there's no "cherry-pick from upstream" ceremony required. Use the `shadcn` CLI (see [`.agents/skills/shadcn`](../.agents/skills/shadcn/SKILL.md)) or write them by hand, matching the existing token conventions.

After any change here, run:

```bash
bun run typecheck
bun run lint
bun run build
```
