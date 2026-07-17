.PHONY: verify-architecture domain-gate run fga-validate dev-web-ui clean clean-cache

verify-architecture:
	$(MAKE) -C backend/contracts $@
	$(MAKE) -C backend/worker $@
	$(MAKE) -C backend/api $@

# cys_core/domain only physically lives in backend/contracts/src — worker and
# api install it as an editable path dependency, so coverage.py can never
# find data under their own src/ tree to satisfy the --include filter (always
# "No data to report", regardless of actual test coverage). Contracts-only.
domain-gate:
	$(MAKE) -C backend/contracts $@

fga-validate:
	$(MAKE) -C backend/api $@

run:
	cd tui && $(MAKE) run

dev-web-ui:
	cd web_ui && bun run dev

clean:
	./scripts/clean.sh all

clean-cache:
	./scripts/clean.sh cache
