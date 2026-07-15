# syntax=docker/dockerfile:1
FROM oven/bun:1-alpine AS deps
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

FROM oven/bun:1-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_LANGFUSE_HOST=https://localhost:3001
ARG NEXT_PUBLIC_EGRESS_SSE=1
ARG NEXT_PUBLIC_STREAM_API_BASE=""
ENV NEXT_PUBLIC_LANGFUSE_HOST=${NEXT_PUBLIC_LANGFUSE_HOST}
ENV NEXT_PUBLIC_EGRESS_SSE=${NEXT_PUBLIC_EGRESS_SSE}
ENV NEXT_PUBLIC_STREAM_API_BASE=${NEXT_PUBLIC_STREAM_API_BASE}
COPY package.json bun.lock ./
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN bun run build

FROM oven/bun:1-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
RUN addgroup -g 10001 app && adduser -u 10001 -G app -D app && chown -R app:app /app
USER 10001
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/ >/dev/null 2>&1 || exit 1
CMD ["bun", "server.js"]
