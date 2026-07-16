---
name: research-heuristics
description: OSINT and open-web research anti-failure heuristics
---

# Research heuristics

- Use web_search with specific entities; retry with search_archived_webpage for dead links.
- Prefer read_document on attachments before synthesis.
- Use delegate_research for isolated sub-questions; keep main thread focused.
- For ambiguous facts, run reasoning_check before final answer.
