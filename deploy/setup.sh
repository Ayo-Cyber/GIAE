#!/usr/bin/env bash
# GIAE one-shot deploy on a fresh Ubuntu VM (e.g. Oracle Always Free ARM).
# Idempotent: safe to re-run. Encodes the exact sequence validated locally,
# including the two gotchas — DB mount path (/app/.giae) and volume ownership.
#
#   sudo bash deploy/setup.sh              # full: docker + stack + Swiss-Prot DB
#   sudo bash deploy/setup.sh --no-db      # skip the 90 MB Swiss-Prot download
#
# Run from the repo root. Reads/creates .env next to docker-compose.yml.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
BUILD_DB=1
[ "${1:-}" = "--no-db" ] && BUILD_DB=0

echo "== 1/5  Docker =="
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi
docker compose version >/dev/null 2>&1 || { echo "docker compose plugin missing"; exit 1; }

echo "== 2/5  .env (secrets) =="
if [ ! -f .env ]; then
  DOMAIN="${GIAE_DOMAIN:-http://localhost:3000}"
  cat > .env <<EOF
POSTGRES_USER=giae
POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
POSTGRES_DB=giae
JWT_SECRET=$(openssl rand -base64 32)
NEXTAUTH_SECRET=$(openssl rand -base64 32)
NEXTAUTH_URL=${DOMAIN}
CORS_ALLOWED_ORIGINS=${DOMAIN}
ENV=prod
JWT_ACCESS_TOKEN_TTL_MINUTES=60
EOF
  echo "  wrote .env (NEXTAUTH_URL=${DOMAIN} — edit to your https domain, then restart frontend)"
else
  echo "  .env exists — leaving as-is"
fi

echo "== 3/5  build + start stack =="
docker compose up -d --build

echo "== 4/5  Swiss-Prot Diamond DB into the giae_db volume =="
VOL="$(docker volume ls --format '{{.Name}}' | grep giae_db | head -1)"
if [ "$BUILD_DB" = "1" ] && [ -n "$VOL" ]; then
  if docker run --rm -v "$VOL":/d alpine test -f /d/diamond/swissprot.dmnd 2>/dev/null; then
    echo "  DB already present in volume — skipping download"
  else
    echo "  downloading Swiss-Prot + building Diamond DB (a few minutes)…"
    # Build inside the api image (has curl + diamond) — the api service already
    # mounts the giae_db volume at /app/.giae, so no extra -v is needed.
    # diamond makedb reads gzip-compressed FASTA directly (no gunzip dependency).
    docker compose run --rm --no-deps api sh -c '
      set -e
      mkdir -p /app/.giae/diamond
      curl -fsSL -o /tmp/sprot.fasta.gz \
        https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz
      diamond makedb --in /tmp/sprot.fasta.gz --db /app/.giae/diamond/swissprot --quiet
      rm -f /tmp/sprot.fasta.gz'
  fi
  # gotcha #2: volume populated as root -> chown to the app uid so the worker
  # can write its SQLite cache (else every job fails "unable to open database file")
  docker run --rm -v "$VOL":/d alpine chown -R 1000:1000 /d
  docker compose restart worker api
else
  echo "  skipped DB build (--no-db or no volume). Homology/calibration stay off until built."
fi

echo "== 5/5  verify =="
sleep 4
curl -fsS http://localhost:8000/api/v1/health && echo " <- API ok" || echo "API not ready yet"
docker compose ps --format '{{.Service}}: {{.Status}}'
echo
echo "Done. Next:"
echo "  • point a domain at this VM and set NEXTAUTH_URL=https://your.domain in .env,"
echo "    then: docker compose up -d frontend  (and run Caddy — see deploy/Caddyfile)"
echo "  • create the first account at the frontend /signup"
