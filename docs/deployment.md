# Deployment

How to run the GIAE REST API in production.

This doc covers the full stack: Postgres, Redis, the FastAPI server,
and the Celery worker. The Docker compose file in the repo is the
canonical reference — this guide explains what it does and how to
adapt it.

---

## Quick stack-up (local / dev)

```bash
git clone https://github.com/Ayo-Cyber/GIAE.git
cd GIAE
cp .env.example .env

# Generate two random secrets and paste into .env
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(64))"
python -c "import secrets; print('NEXTAUTH_SECRET=' + secrets.token_urlsafe(32))"

# Bring up the core services (skip the Next.js frontend)
docker compose up -d postgres redis api worker
```

Verify:

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","message":"GIAE API Engine is fully operational."}

docker compose ps
# postgres   healthy   5432/tcp
# redis      healthy   6379/tcp
# api        healthy   :8000
# worker     started   (Celery threads pool, concurrency 4)
```

The `frontend` service is a Next.js dashboard — optional. Add `frontend`
to the `up` command to bring it up too.

---

## Stack components

| Service | Image | Role |
|---|---|---|
| `postgres` | `postgres:16-alpine` | Job state, users, API keys, waitlist |
| `redis` | `redis:7-alpine` | Celery broker + result backend |
| `api` | `giae-api:latest` (built from `Dockerfile`) | FastAPI HTTP server (uvicorn) |
| `worker` | `giae-api:latest` | Celery worker (threads pool) |
| `frontend` | `giae-frontend:latest` (built from `frontend/Dockerfile`) | Next.js dashboard |

Volumes:

| Volume | Mounted at | Purpose |
|---|---|---|
| `postgres_data` | `/var/lib/postgresql/data` | DB persistence |
| `redis_data` | `/data` | AOF persistence |
| `uploads_data` | `/app/uploads` | Genome uploads (UUID-prefixed) |
| `reports_data` | `/app/public_reports` | Generated HTML reports |

---

## Environment variables

All vars live in `.env` (which is gitignored). The compose file fails
fast if required vars are missing.

### Required

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | JWT signing key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. **Refuses to boot in production without this.** |
| `NEXTAUTH_SECRET` | Frontend session secret (only required if running the `frontend` service) |

### Recommended

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` | `giae` | DB user |
| `POSTGRES_PASSWORD` | `giae` | **Change in production** |
| `POSTGRES_DB` | `giae` | DB name |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | `60` | Token lifetime |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,https://app.giae.io` | Comma-separated origin list |
| `ENV` | `dev` | Set to `prod` or `production` to enforce JWT_SECRET |
| `NEXTAUTH_URL` | `http://localhost:3000` | Frontend base URL |

### Internal (set automatically by compose)

| Variable | Value (in compose) | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://...` | Built from `POSTGRES_*` vars |
| `REDIS_URL` | `redis://redis:6379/0` | Inside the compose network |

---

## Production hardening

### 1. Strong secrets

Generate fresh values for every deployment:

```bash
JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
POSTGRES_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### 2. `ENV=production`

Set this. The auth module refuses to fall back to the dev JWT secret
when `ENV` is `prod` or `production`.

### 3. Restrict CORS

Default is dev-friendly. Lock to your real domains:

```bash
CORS_ALLOWED_ORIGINS=https://app.example.com,https://staging.example.com
```

### 4. Don't expose Postgres or Redis externally

The compose file already keeps them inside the bridge network. The
commented-out `ports: ["5432:5432"]` line should stay commented in
production.

### 5. Reverse proxy for TLS

Put Caddy / Nginx / Cloudflare in front for TLS termination, rate
limiting, and access logs. The API binds plain HTTP on `:8000`.

### 6. Per-job size limits

FastAPI doesn't enforce upload size by default. Add to your reverse
proxy:

```nginx
client_max_body_size 50m;   # adjust to your largest expected genome
```

---

## Scaling

### Horizontal — more workers

The Celery worker is the bottleneck for throughput. Add replicas:

```bash
docker compose up -d --scale worker=4
```

Each worker uses the **threads** pool (default 4 threads), so
`--scale worker=4` gives you 16 concurrent interpretations.

!!! warning "Don't use `--pool prefork`"
    `pyhmmer` and `torch` are C extensions that aren't fork-safe. Stick
    with `threads`.

### Vertical — more threads per worker

Edit the `command` in `docker-compose.yml`:

```yaml
worker:
  command:
    - celery
    - -A
    - giae_api.worker.celery_app
    - worker
    - --pool=threads
    - --concurrency=8        # bump this
```

Or run the worker via the CLI with explicit args:

```bash
giae worker --concurrency 8 --pool threads
```

### API tier — more uvicorn workers

The `api` service runs uvicorn with one worker by default. To match
multi-core machines, edit the Dockerfile `CMD` or override the compose
command:

```yaml
api:
  command: ["uvicorn", "giae_api.main:app", "--host", "0.0.0.0",
            "--port", "8000", "--workers", "4"]
```

Each uvicorn worker is independent — no shared state — so this scales
linearly until DB connections become the bottleneck.

### Database connection pooling

`database.py` configures `pool_size=10, max_overflow=20`. For a
multi-worker deployment, increase these so each uvicorn worker gets a
healthy share. Postgres' `max_connections` (default 100) is the global
ceiling.

---

## Observability

### Healthchecks

Built into the Dockerfile and compose file:

- `api` — `curl /api/v1/health` every 30 s
- `postgres` — `pg_isready` every 10 s
- `redis` — `redis-cli ping` every 10 s

### Logs

```bash
docker compose logs -f api
docker compose logs -f worker
```

Set `--loglevel debug` on the worker for verbose Celery output.

### Worker status from the API

```bash
curl http://localhost:8000/api/v1/worker/status
# {"online": true}
```

Returns `false` when no worker is reachable via Redis.

### Metrics

Not built in — add `prometheus-fastapi-instrumentator` if you want
Prometheus metrics. PRs welcome.

---

## Backup & disaster recovery

### Postgres

```bash
# Backup
docker compose exec postgres pg_dump -U giae giae > backup.sql

# Restore
docker compose exec -T postgres psql -U giae giae < backup.sql
```

### Volumes

The named volumes (`postgres_data`, `uploads_data`, `reports_data`) live
in Docker's data directory. For real durability, use bind mounts to
known paths and back them up with your standard tooling.

### Stateless restart

The API and worker are stateless — they can be killed and recreated
freely. All state lives in Postgres + Redis + the volumes.

---

## Without Docker

You can run GIAE without Docker if you have Python 3.9+, Postgres, and
Redis available:

```bash
pip install "giae[api]"

export DATABASE_URL=postgresql+psycopg2://giae:giae@localhost:5432/giae
export REDIS_URL=redis://localhost:6379/0
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
export ENV=production

# Terminal 1 — API
giae serve --host 0.0.0.0 --port 8000 --workers 4

# Terminal 2 — worker
giae worker --concurrency 8
```

This is also how `systemd` units would launch the services.

### SQLite for tiny deployments

For a single-user, single-machine deployment, SQLite is supported:

```bash
export DATABASE_URL=sqlite:///./giae.db
```

The engine config detects SQLite and adjusts pool settings. You still
need Redis for the worker queue.

---

## Common gotchas

### "AMRFinderPlus not found" during Bakta benchmark

That's specifically the `post_assets/bakta_comparison.py` setup, not
GIAE itself. See the [benchmarks page](benchmarks.md) for the patch.

### "JWT_SECRET must be set in production"

You set `ENV=production` but didn't supply a `JWT_SECRET`. Either
remove `ENV=production` for dev, or generate a secret.

### "process did not complete successfully" during Docker build

Old buildx cache. Run:

```bash
docker buildx prune -af
docker compose build --no-cache api
```

### Worker is up but jobs stay in `PENDING`

Check Redis is reachable from the worker container:

```bash
docker compose exec worker redis-cli -h redis ping
# PONG
```

If the API can reach Redis but the worker can't, check the compose
network.
