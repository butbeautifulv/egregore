# syntax=docker/dockerfile:1
# cxado/egregore — API + worker (same image, different command).
FROM python:3.13-slim AS base
WORKDIR /app
RUN pip install --no-cache-dir uv

# Layer 1: lockfile only — deps install cached until pyproject.toml / uv.lock change.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Layer 2: source — only reinstalls the local project wheel, not all PyPI deps.
COPY cys_core ./cys_core
COPY interfaces ./interfaces
COPY bootstrap ./bootstrap
COPY agents ./agents
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1
ENV STAGE=prod
ENV USE_MEMORY_FALLBACK=false

EXPOSE 8080

CMD ["uv", "run", "egregore", "serve", "--host", "0.0.0.0", "--port", "8080"]
