.PHONY: verify-architecture domain-gate run fga-validate

verify-architecture:
	uv run python scripts/verify_import_boundaries.py
	bash scripts/verify_no_langfuse_in_core.sh
	uv run lint-imports
	uv run pytest tests/architecture/ -q

domain-gate:
	USE_MEMORY_FALLBACK=true STAGE=test ./scripts/pytest_batches.sh tests/domain --cov --domain-gate

fga-validate:
	@if command -v fga >/dev/null 2>&1; then \
		fga model validate --file authz/model.fga; \
		fga model test --tests authz/model.fga.yaml; \
	else \
		echo "fga CLI not installed; pytest tests/authz/ validates model file contract"; \
		USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/authz/ -q; \
	fi

run:
	cd tui && $(MAKE) run
