# cys-agi

Платформа безопасных мульти-агентов для оценки кибербезопасности.

## Два слоя

| Слой | Путь | В git |
|------|------|-------|
| **Продукт** | [`agents/`](agents/) | да |
| **Разработка (Cursor)** | `.agents/skills/` | нет |

## Структура `agents/`

```
agents/
├── manifest.yaml
├── personas/      # redteam, network, soc, compliance, critic, coordinator
├── rules/         # security, scope, output — global constraints
├── plans/         # assessment playbooks
└── skills/        # domain knowledge (CI/CD, beaconing, compliance)
```

## Быстрый старт

```bash
uv sync && docker compose up -d
cp .env.example .env

python main.py info
python main.py assess --input "Authorized scope: ..."
python main.py agent redteam
python main.py adversarial-test
```

## Код

```
cys_core/     llm, registry, runtime, security
graph/        LangGraph pipeline
coordinator/  Deep Agents sessions
docs/         security reference
tests/
```

## Env

| Переменная | Default |
|------------|---------|
| `AGENTS_ROOT` | `agents` |
| `LLM_PROVIDER` | `litellm` |
| `LLM_MODEL` | `anthropic/claude-sonnet-4` |

См. [`.env.example`](.env.example), [AGENTS.md](AGENTS.md), [agents/README.md](agents/README.md).
