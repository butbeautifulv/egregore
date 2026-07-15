# syntax=docker/dockerfile:1
# cxado/egregore — API + worker (same image, different command).
# Build from egregore repo root: docker build -f deploy/Dockerfile .
FROM python:3.13-slim AS base
WORKDIR /app/api
COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /usr/local/bin/uv

# Layer 1: lockfile only — deps install cached until pyproject.toml / uv.lock change.
COPY api/pyproject.toml api/uv.lock api/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Layer 2: source — only reinstalls the local project wheel, not all PyPI deps.
COPY api/src ./src
COPY api/agents ./agents
COPY api/migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1
ENV STAGE=prod
ENV USE_MEMORY_FALLBACK=false

RUN groupadd -g 10001 app && useradd -u 10001 -g app -m app && chown -R app:app /app
USER 10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)" || exit 1

CMD ["uv", "run", "egregore", "serve", "--host", "0.0.0.0", "--port", "8080"]
