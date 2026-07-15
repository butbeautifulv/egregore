<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## React hooks: stable dependencies

Hooks that sync state into context (e.g. `usePlatformBreadcrumbMiddle`) must not take freshly allocated arrays/objects each render. Stabilize with `useMemo` keyed on a serialized snapshot (`JSON.stringify` for small crumb lists) or pass primitive labels via `usePlatformBreadcrumbLabel`.
