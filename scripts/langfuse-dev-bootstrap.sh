#!/usr/bin/env bash
# Bootstrap self-hosted Langfuse for local egregore dev (headless initialization).
# See: https://langfuse.com/self-hosting/administration/headless-initialization
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LF_DIR="$ROOT/deploy/langfuse"
EGREGORE_ENV="$ROOT/.env"

# Fixed dev-only credentials — never use in production.
DEV_ORG_ID="egregore"
DEV_PROJECT_ID="egregore-dev"
DEV_PUBLIC_KEY="pk-lf-egregore-dev-local"
DEV_SECRET_KEY="sk-lf-egregore-dev-local"
DEV_USER_EMAIL="dev@egregore.local"
DEV_USER_PASSWORD="egregore-dev"

cd "$LF_DIR"

if [[ ! -f .env ]]; then
  cp env.example .env
  echo "Created deploy/langfuse/.env from env.example"
fi

# Generate stack secrets if still placeholders
if grep -q 'CHANGEME-nextauth-secret' .env 2>/dev/null; then
  sed -i "s|CHANGEME-nextauth-secret|$(openssl rand -base64 32)|" .env
fi
if grep -q 'CHANGEME-salt' .env 2>/dev/null; then
  sed -i "s|CHANGEME-salt|$(openssl rand -base64 32)|" .env
fi
if grep -q 'CHANGEME-64-hex-chars-from-openssl-rand-hex-32' .env 2>/dev/null; then
  sed -i "s|CHANGEME-64-hex-chars-from-openssl-rand-hex-32|$(openssl rand -hex 32)|" .env
fi
for placeholder in CHANGEME-postgres CHANGEME-clickhouse CHANGEME-redis CHANGEME-minio; do
  if grep -q "$placeholder" .env 2>/dev/null; then
    sed -i "s/$placeholder/dev-local-secret/g" .env
  fi
done

# Headless init — no quotes (Langfuse/docker-compose requirement)
set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${val}|" .env
  elif grep -q "^# ${key}=" .env; then
    sed -i "s|^# ${key}=.*|${key}=${val}|" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

set_kv LANGFUSE_INIT_ORG_ID "$DEV_ORG_ID"
set_kv LANGFUSE_INIT_ORG_NAME "Egregore"
set_kv LANGFUSE_INIT_PROJECT_ID "$DEV_PROJECT_ID"
set_kv LANGFUSE_INIT_PROJECT_NAME "egregore-dev"
set_kv LANGFUSE_INIT_PROJECT_PUBLIC_KEY "$DEV_PUBLIC_KEY"
set_kv LANGFUSE_INIT_PROJECT_SECRET_KEY "$DEV_SECRET_KEY"
set_kv LANGFUSE_INIT_USER_EMAIL "$DEV_USER_EMAIL"
set_kv LANGFUSE_INIT_USER_NAME "Dev Admin"
set_kv LANGFUSE_INIT_USER_PASSWORD "$DEV_USER_PASSWORD"
set_kv NEXTAUTH_URL "http://localhost:3001"

# DATABASE_URL must match POSTGRES_PASSWORD
PG_PASS="$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
set_kv DATABASE_URL "postgresql://postgres:${PG_PASS}@postgres:5432/postgres"

# Sync egregore app .env
touch "$EGREGORE_ENV"
set_eg_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$EGREGORE_ENV"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$EGREGORE_ENV"
  elif grep -q "^# ${key}=" "$EGREGORE_ENV"; then
    sed -i "s|^# ${key}=.*|${key}=${val}|" "$EGREGORE_ENV"
  else
    echo "${key}=${val}" >> "$EGREGORE_ENV"
  fi
}

set_eg_kv LANGFUSE_PUBLIC_KEY "$DEV_PUBLIC_KEY"
set_eg_kv LANGFUSE_SECRET_KEY "$DEV_SECRET_KEY"
set_eg_kv LANGFUSE_HOST "http://localhost:3001"

echo "Ensuring Langfuse MinIO bucket exists..."
LF_NETWORK="$(docker compose ps -q minio 2>/dev/null | xargs -r docker inspect --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -1)"
MINIO_PASS="$(grep '^MINIO_ROOT_PASSWORD=' .env | cut -d= -f2-)"
if [[ -n "$LF_NETWORK" && -n "$MINIO_PASS" ]]; then
  docker run --rm --network "$LF_NETWORK" --entrypoint /bin/sh minio/mc \
    -c "mc alias set local http://minio:9000 minio '${MINIO_PASS}' && mc mb local/langfuse --ignore-existing" \
    && echo "  MinIO bucket: langfuse"
else
  echo "  WARN: skip MinIO bucket bootstrap (stack not running?)"
fi

echo ""
echo "Langfuse dev bootstrap complete."
echo "  UI:      http://localhost:3001"
echo "  Login:   ${DEV_USER_EMAIL} / ${DEV_USER_PASSWORD}"
echo "  API keys written to projects/egregore/.env"
echo ""
echo "If org/project already exist without keys, run:"
echo "  make dev-langfuse-fresh   # destructive: resets Langfuse volumes"
echo "Then restart API/worker so they pick up LANGFUSE_* env."
