# Документация egregore

## Core docs

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура, data flow, компоненты |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Langfuse, Prometheus, OTEL/Tempo, Loki, Grafana |
| [PLATFORM_TRUTH_MAP.md](PLATFORM_TRUTH_MAP.md) | Baseline inventory (middleware, tools, policy) |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Разработка, отладка, тестирование |
| [operator-console-contract.md](operator-console-contract.md) | **Общий контракт web UI + TUI** (API, SSE, chat state) |
| [SECURE_DEPLOYMENT.md](SECURE_DEPLOYMENT.md) | Secure deployment, MILS, A2A/mTLS, hardening |

## Architecture site (visual)

Interactive diagrams for architects: [docs/architecture-site/](../../../docs/architecture-site/) in meta-repo.

k3s offline: `https://<host>:30080` via TLS gateway — see [k3s-offline-baseline.md](../../../docs/deploy/k3s-offline-baseline.md).

## Reference

Справочники и cheat sheets: [reference/README.md](reference/README.md)

## Связанные файлы в корне

- [README.md](../README.md) — обзор проекта и quick start
- [LICENSE](../LICENSE) — MIT license
- [AGENTS.md](../AGENTS.md) — правила для AI-ассистентов
- [agents/README.md](../agents/README.md) — продуктовый слой
