.PHONY: verify-architecture domain-gate dev-console run

verify-architecture:
	uv run python scripts/verify_import_boundaries.py
	bash scripts/verify_no_langfuse_in_core.sh
	uv run lint-imports
	uv run pytest tests/architecture/ -q

domain-gate:
	USE_MEMORY_FALLBACK=true STAGE=test ./scripts/pytest_batches.sh tests/domain --cov --domain-gate

dev-console:
	cd ui-minimal && python3 -m http.server 5173

run:
	cd tui && $(MAKE) run
