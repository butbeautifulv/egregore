.PHONY: verify-architecture domain-gate run fga-validate dev-web-ui dev-tool-gateway clean clean-cache

verify-architecture domain-gate:
	$(MAKE) -C backend/worker $@
	$(MAKE) -C backend/api $@
	$(MAKE) -C backend/tool-gateway $@

fga-validate:
	$(MAKE) -C backend/api $@

run:
	cd tui && $(MAKE) run

dev-web-ui:
	cd web_ui && bun run dev

dev-tool-gateway:
	cd backend/tool-gateway && uv run egregore tool-gateway

clean:
	./scripts/clean.sh all

clean-cache:
	./scripts/clean.sh cache
