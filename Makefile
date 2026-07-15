.PHONY: verify-architecture domain-gate run fga-validate dev-web-ui

verify-architecture domain-gate fga-validate:
	$(MAKE) -C api $@

run:
	cd tui && $(MAKE) run

dev-web-ui:
	cd web_ui && bun run dev
