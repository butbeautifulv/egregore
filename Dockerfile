# syntax=docker/dockerfile:1.7

FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY . .
RUN python -m compileall -q bootstrap cys_core interfaces connectors

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    STAGE=prod \
    USE_MEMORY_FALLBACK=false \
    PERSISTENCE_CONNECTOR=postgres \
    JOB_STORE_CONNECTOR=postgres

WORKDIR /app

RUN groupadd --system --gid 10001 cysagi \
    && useradd --system --uid 10001 --gid cysagi --home-dir /nonexistent --shell /usr/sbin/nologin cysagi \
    && mkdir -p /app /tmp/cys-agi \
    && chown -R cysagi:cysagi /app /tmp/cys-agi

COPY --from=builder --chown=cysagi:cysagi /build/.venv /app/.venv
COPY --from=builder --chown=cysagi:cysagi /build/agents /app/agents
COPY --from=builder --chown=cysagi:cysagi /build/bootstrap /app/bootstrap
COPY --from=builder --chown=cysagi:cysagi /build/cys_core /app/cys_core
COPY --from=builder --chown=cysagi:cysagi /build/interfaces /app/interfaces
COPY --from=builder --chown=cysagi:cysagi /build/connectors /app/connectors
COPY --from=builder --chown=cysagi:cysagi /build/migrations /app/migrations
COPY --from=builder --chown=cysagi:cysagi /build/pyproject.toml /build/README.md /build/LICENSE /app/

USER 10001:10001

ENTRYPOINT ["cys-agi"]
CMD ["worker", "--help"]
