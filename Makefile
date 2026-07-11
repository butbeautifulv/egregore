.PHONY: verify-architecture domain-gate run

verify-architecture:
	uv run python scripts/verify_import_boundaries.py
	bash scripts/verify_no_langfuse_in_core.sh
	uv run lint-imports
	uv run pytest tests/architecture/ -q

domain-gate:
	USE_MEMORY_FALLBACK=true STAGE=test ./scripts/pytest_batches.sh tests/domain --cov --domain-gate

run:
	cd tui && $(MAKE) run
