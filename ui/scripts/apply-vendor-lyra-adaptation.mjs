#!/usr/bin/env node
/**
 * Copy radix-lyra class strings from components/ui → vendor/gui/ui,
 * rewrite imports for vendor paths, token-map layout/shell, guard nova leftovers.
 */
import { readdir, readFile, writeFile, stat } from "node:fs/promises"
import { basename, dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const canonicalUi = join(root, "components/ui")
const vendorUi = join(root, "vendor/gui/ui")
const vendorRoot = join(root, "vendor/gui")

const LYRA_TOKEN_REPLACEMENTS = [
  [/rounded-4xl/g, "rounded-none"],
  [/rounded-\[min\(var\(--radius-md\),10px\)\]/g, "rounded-none"],
  [/rounded-\[min\(var\(--radius-md\),12px\)\]/g, "rounded-none"],
  [/in-data-\[slot=button-group\]:rounded-lg/g, ""],
  [/rounded-xl/g, "rounded-none"],
  [/rounded-lg/g, "rounded-none"],
  [/rounded-md/g, "rounded-none"],
  [/hover:bg-primary\/90/g, "hover:bg-primary/80"],
  [/focus-visible:ring-\[3px\]/g, "focus-visible:ring-1"],
  [/focus-visible:ring-3/g, "focus-visible:ring-1"],
  [/aria-invalid:ring-3/g, "aria-invalid:ring-1"],
  [/ring-\[3px\]/g, "ring-1"],
  [/ring-3/g, "ring-1"],
]

const FORBIDDEN_UI_PATTERNS = [
  /\brounded-lg\b/,
  /\brounded-md\b/,
  /\brounded-xl\b/,
  /\brounded-4xl\b/,
  /\bring-3\b/,
]

function rewriteVendorImports(source) {
  return source
    .replaceAll("@/lib/utils", "@/vendor/gui/utils")
    .replaceAll("@/components/ui/", "@/vendor/gui/ui/")
    .replaceAll("@/hooks/use-mobile", "@/vendor/gui/hooks/use-mobile")
}

function applyTokenMap(source) {
  let out = source
  for (const [pattern, replacement] of LYRA_TOKEN_REPLACEMENTS) {
    out = out.replace(pattern, replacement)
  }
  return out
}

async function listTsx(dir) {
  const entries = await readdir(dir, { withFileTypes: true })
  return entries.filter((e) => e.isFile() && e.name.endsWith(".tsx")).map((e) => e.name)
}

async function adaptUiPrimitive(name) {
  const canonicalPath = join(canonicalUi, name)
  const vendorPath = join(vendorUi, name)

  try {
    await stat(canonicalPath)
  } catch {
    const existing = await readFile(vendorPath, "utf8")
    const updated = applyTokenMap(existing)
    if (updated !== existing) {
      await writeFile(vendorPath, updated)
      console.log(`  token-map ${name}`)
    } else {
      console.warn(`  skip (no canonical): ${name}`)
    }
    return
  }

  const canonical = await readFile(canonicalPath, "utf8")
  const adapted = rewriteVendorImports(canonical)
  await writeFile(vendorPath, adapted)
  console.log(`  lyra-copy ${name}`)
}

async function adaptExtraFiles(relPaths) {
  for (const rel of relPaths) {
    const path = join(vendorRoot, rel)
    try {
      const original = await readFile(path, "utf8")
      const updated = applyTokenMap(original)
      if (updated !== original) {
        await writeFile(path, updated)
        console.log(`  token-map ${rel}`)
      }
    } catch {
      console.warn(`  missing: ${rel}`)
    }
  }
}

async function guardVendorUi() {
  const files = await listTsx(vendorUi)
  const violations = []
  for (const file of files) {
    const content = await readFile(join(vendorUi, file), "utf8")
    for (const pattern of FORBIDDEN_UI_PATTERNS) {
      if (pattern.test(content)) {
        violations.push(`${file}: ${pattern}`)
      }
    }
  }
  if (violations.length > 0) {
    console.error("Lyra guard failed — nova tokens remain in vendor/gui/ui:")
    for (const v of violations) {
      console.error(`  ${v}`)
    }
    process.exit(1)
  }
}

console.log("Applying radix-lyra adaptation to vendor/gui/ui…")
const vendorFiles = await listTsx(vendorUi)
for (const file of vendorFiles.sort()) {
  await adaptUiPrimitive(file)
}

console.log("Applying token map to layout/shell…")
await adaptExtraFiles([
  "layout/attachment-gallery.tsx",
  "layout/data-table-shell.tsx",
  "layout/form-error-slot.tsx",
  "layout/page-header.tsx",
  "shell/shell-brand.tsx",
  "shell/shell-sidebar.tsx",
  "shell/shell-nav-main.tsx",
  "shell/shell-breadcrumb.tsx",
  "ui/typography.tsx",
])

await guardVendorUi()
console.log("Lyra adaptation complete.")
