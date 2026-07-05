# RAGAS / FaithEval runbook (local)

1. Install optional deps when running heavy suites: `uv sync --extra eval`
2. Export RAG triples from `tests/fixtures/rag_eval_tiny.json`
3. Run: `uv run python scripts/evals/egregore_eval.py --suite rag-tiny --dry-run`
4. Adapters: `cys_core/application/eval/adapters.py` (`RagasAdapterSkeleton`)
