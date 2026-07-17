.PHONY: verify-architecture fga-validate clean

clean:
	rm -rf .pytest_cache .ruff_cache .import_linter_cache .coverage htmlcov
	rm -f .coverage.* 2>/dev/null || true
	find . \
	  -path './.venv' -prune -o \
	  -depth -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . \
	  -path './.venv' -prune -o \
	  -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true

verify-architecture:
	uv run python scripts/verify_import_boundaries.py
	bash scripts/verify_no_langfuse_in_core.sh
	uv run lint-imports
	uv run pytest tests/architecture/ -q

# No domain-gate target here: cys_core/domain physically lives only in
# backend/contracts/src (this package installs it as an editable path
# dependency, and this package has no tests/domain/ of its own). Use
# `make -C ../contracts domain-gate` for the real gate.

fga-validate:
	@if command -v fga >/dev/null 2>&1; then \
		fga model validate --file src/authz/model.fga; \
		fga model test --tests src/authz/model.fga.yaml; \
	else \
		echo "fga CLI not installed; pytest tests/authz/ validates model file contract"; \
		USE_MEMORY_FALLBACK=true STAGE=test uv run pytest tests/authz/ -q; \
	fi
