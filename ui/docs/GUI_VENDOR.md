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
node scripts/rewrite-vendor-imports.mjs
```

Override source path when needed:

```bash
GUI_SRC=/path/to/shared/gui/src ./scripts/vendor-gui.sh
```

`vendor-gui.sh` rsyncs these paths from `shared/gui/src/`:

- `shell/`, `theme/`, `motion/`, `hooks/`, `ui/`, `layout/`
- `utils.ts`

Then `rewrite-vendor-imports.mjs` rewrites `@cxado/gui/` → `@/vendor/gui/`.

## Theme / colors

**Do not** `@import` `shared/gui/tailwind.preset.css` as the canonical color source. That preset only defines `@theme inline` tokens without full `:root` values.

Canonical theme lives in `app/globals.css` (oklch green primary). When syncing structural CSS from shared/gui, preserve egregore-ui color tokens.

## What to cherry-pick

Copy only modules required by current screens. Prefer adding directories to `vendor-gui.sh` over copying all of `src/`.

After sync, run:

```bash
npm run typecheck
npm run build
```
