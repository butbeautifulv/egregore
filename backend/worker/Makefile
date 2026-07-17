.PHONY: verify-architecture clean

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
# dependency), so `coverage --include=src/cys_core/domain/*` can never find
# data under this package's own src/ tree. Use `make -C ../contracts
# domain-gate` for the real gate.
