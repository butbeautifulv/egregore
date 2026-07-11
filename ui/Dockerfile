# syntax=docker/dockerfile:1
FROM oven/bun:1-alpine AS deps
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

FROM oven/bun:1-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_LANGFUSE_HOST=https://localhost:3001
ARG NEXT_PUBLIC_EGRESS_SSE=1
ENV NEXT_PUBLIC_LANGFUSE_HOST=${NEXT_PUBLIC_LANGFUSE_HOST}
ENV NEXT_PUBLIC_EGRESS_SSE=${NEXT_PUBLIC_EGRESS_SSE}
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
EXPOSE 3000
CMD ["bun", "server.js"]
