# cxado/egregore — API + worker (same image, different command).
FROM python:3.14-slim AS base
WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY cys_core ./cys_core
COPY interfaces ./interfaces
COPY bootstrap ./bootstrap
COPY agents ./agents

RUN uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1
ENV STAGE=prod
ENV USE_MEMORY_FALLBACK=false

EXPOSE 8080

CMD ["uv", "run", "egregore", "serve", "--host", "0.0.0.0", "--port", "8080"]
