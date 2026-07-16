---
name: gaia-bench-heuristics
description: GAIA benchmark anti-failure rules (optional gaia-bench profile)
---

# GAIA heuristics

- Detect answer type before extraction (number, name, list, date).
- Use python_sandbox for spreadsheets; vision_analyze for charts.
- Verify units and formatting in extract_structured_output.
- On 403 or blocked pages switch to search_archived_webpage or alternate engine.
