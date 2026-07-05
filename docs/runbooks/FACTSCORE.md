# FActScore runbook

1. Prepare KB JSONL with `doc_id`, `text`
2. Use `FaithEvalLoader` for unanswerable/inconsistent cases
3. Wire cyber KB spec in product pack when available
4. Smoke: `tests/application/test_eval_adapters.py`
