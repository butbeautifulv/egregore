# syntax=docker/dockerfile:1
# cxado/egregore — API + worker (same image, different command).
# Build from egregore repo root: docker build -f deploy/Dockerfile .
#
# Builder: deps + uv sync. Runtime: fresh slim, OS upgraded, perl-base removed (SCA surface).

FROM python:3.13-slim@sha256:bffeb7bd6a85767587059c6ba23e1e9122078e3aa3fa836099171b9bb5a9bb00 AS builder
ENV DEBIAN_FRONTEND=noninteractive
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
WORKDIR /app/api
COPY --from=ghcr.io/astral-sh/uv:0.11.12@sha256:027318b213a7804ecd085ea7efdcdc4d44fa202c6e676c86ce86c0206d38f65c /uv /usr/local/bin/uv

COPY api/pyproject.toml api/uv.lock api/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY api/src ./src
COPY api/agents ./agents
COPY api/migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.13-slim@sha256:bffeb7bd6a85767587059c6ba23e1e9122078e3aa3fa836099171b9bb5a9bb00 AS runtime
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV STAGE=prod
ENV USE_MEMORY_FALLBACK=false
ENV UV_CACHE_DIR=/tmp/uv-cache
WORKDIR /app/api

RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get purge -y --allow-remove-essential \
      perl-base gzip login util-linux mount \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 10001 app \
 && useradd --uid 10001 --gid app --home-dir /app --no-create-home app

COPY --from=builder --chown=app:app /app/api /app/api

USER 10001
ENV PATH="/app/api/.venv/bin:$PATH"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)" || exit 1

ENTRYPOINT ["egregore"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]
