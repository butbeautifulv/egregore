# GUI vendor sync

Egregore UI copies a minimal subset of [`shared/gui`](../../../../shared/gui) into `vendor/gui/`. We do **not** use `file:../../shared/gui` as an npm dependency.

## Why vendor-copy

- Avoids import resolution issues in Next.js builds and tests
- Keeps the operator UI self-contained for deployment
- Allows cherry-picking only the components we need

## Sync workflow

From `projects/egregore/ui` (meta-repo checkout required for `shared/gui`):

```bash
./scripts/vendor-gui.sh
```

This runs, in order: rsync from `shared/gui` → `rewrite-vendor-imports.mjs` → `apply-vendor-lyra-adaptation.mjs`.

Manual steps (if not using `vendor-gui.sh`):

```bash
node scripts/rewrite-vendor-imports.mjs
node scripts/apply-vendor-lyra-adaptation.mjs
```

See [VENDOR_GUI_LYRA_LOG.md](VENDOR_GUI_LYRA_LOG.md) for nova→lyra rules and re-sync policy.

Override source path when needed:

```bash
GUI_SRC=/path/to/shared/gui/src ./scripts/vendor-gui.sh
```

`vendor-gui.sh` rsyncs these paths from `shared/gui/src/`:

- `shell/`, `theme/`, `motion/`, `hooks/`, `ui/`, `layout/`
- `utils.ts`

Then `rewrite-vendor-imports.mjs` rewrites `@cxado/gui/` → `@/vendor/gui/`.

`apply-vendor-lyra-adaptation.mjs` copies **radix-lyra** classes from `components/ui/` into `vendor/gui/ui/` (egregore uses `radix-lyra`; shared/gui uses `radix-nova`).

## Theme / colors

**Do not** `@import` `shared/gui/tailwind.preset.css` as the canonical color source. That preset only defines `@theme inline` tokens without full `:root` values.

Canonical theme is preset **`b3Rq8QejA`** (Lyra + neutral baseColor + lime theme). Apply with:

```bash
npx shadcn@latest apply b3Rq8QejA --yes
```

`app/globals.css` and `components.json` are updated by the CLI. After theme changes, re-run `node scripts/apply-vendor-lyra-adaptation.mjs`.

## What to cherry-pick

Copy only modules required by current screens. Prefer adding directories to `vendor-gui.sh` over copying all of `src/`.

After sync, run:

```bash
npm run typecheck
npm run build
```
