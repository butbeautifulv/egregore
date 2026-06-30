#!/usr/bin/env node
import { readdir, readFile, writeFile } from "node:fs/promises"
import { join } from "node:path"

const vendorRoot = new URL("../vendor/gui", import.meta.url).pathname

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...(await walk(path)))
    } else if (/\.(ts|tsx|mts)$/.test(entry.name)) {
      files.push(path)
    }
  }
  return files
}

const files = await walk(vendorRoot)
let changed = 0
for (const file of files) {
  const original = await readFile(file, "utf8")
  const updated = original.replaceAll("@cxado/gui/", "@/vendor/gui/")
  if (updated !== original) {
    await writeFile(file, updated)
    changed += 1
  }
}
console.log(`Rewrote imports in ${changed} files`)
