.PHONY: verify-architecture domain-gate run fga-validate dev-web-ui clean clean-cache

verify-architecture domain-gate fga-validate:
	$(MAKE) -C backend $@

run:
	cd tui && $(MAKE) run

dev-web-ui:
	cd web_ui && bun run dev

clean:
	./scripts/clean.sh all

clean-cache:
	./scripts/clean.sh cache
