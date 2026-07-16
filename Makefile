.PHONY: verify-architecture domain-gate run fga-validate dev-web-ui clean clean-cache

verify-architecture domain-gate:
	$(MAKE) -C backend/contracts $@
	$(MAKE) -C backend/worker $@
	$(MAKE) -C backend/api $@

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
