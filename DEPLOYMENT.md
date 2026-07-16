# GIAE Deployment Plan

How to ship GIAE to production, what the moving parts are, and the gaps to
close first. Written against the current repo (Docker + docker-compose already
present).

> **Read this first — the deployed image is currently weaker than your laptop.**
> The `Dockerfile` installs only `.[api]`. It does **not** install `pyrodigal`
> (gene finding falls back to a naive ORF scanner), the **diamond** binary, or
> the **Swiss-Prot** database. Without those, the container runs the *offline
> motif-only* config: no homology annotation, no calibrated confidence, no
> homology-derived GO/EC. Closing that gap (§2) is the difference between
> deploying "GIAE from the benchmark" and a much weaker tool.

## 1. Architecture

```
                       ┌───────────────┐
   browser  ──HTTPS──► │  Next.js (3000)│  serves UI + /api/v1 proxy
                       │  frontend      │  (attaches JWT, refreshes it)
                       └──────┬─────────┘
                              │ server-side fetch (API_URL)
                       ┌──────▼─────────┐      ┌───────────┐
                       │  FastAPI (8000)│◄────►│ Postgres  │  users, jobs, keys
                       │  api           │      └───────────┘
                       └──────┬─────────┘      ┌───────────┐
                              │ enqueue        │  Redis    │  broker + results
                       ┌──────▼─────────┐◄────►└───────────┘
                       │  Celery worker │  parse → pyrodigal → diamond/Swiss-Prot
                       │  (threads pool)│  → calibration → GO/EC → HTML report
                       └────────────────┘
                              │ reads
                       ┌──────▼─────────┐
                       │ Swiss-Prot DB  │  ~280 MB, mounted volume (see §2)
                       │ ~/.giae/diamond│
                       └────────────────┘
```

Five services, all in `docker-compose.yml`: `postgres`, `redis`, `api`,
`worker`, `frontend`. The worker does the heavy lifting; scale it horizontally.

## 2. Close the annotation gap (do this before first deploy)

The engine's quality depends on three things the image lacks. Add them:

1. **pyrodigal** (gene finding). Change the image build to install the
   annotation extra:
   ```dockerfile
   # in both pip stages, replace ".[api]" with ".[api,annotation]"
   ```
   Without it, `ORFFinder` silently uses the naive six-frame scanner — the
   benchmark's F1 numbers do **not** hold.

2. **diamond** binary. Add to the runtime stage:
   ```dockerfile
   RUN apt-get update && apt-get install -y --no-install-recommends diamond-aligner \
       && rm -rf /var/lib/apt/lists/*
   ```
   (or copy a static diamond build). `GIAE_ENABLE_DIAMOND` already defaults on;
   the plugin no-ops safely if the binary or DB is absent.

3. **Swiss-Prot diamond DB** (~280 MB). Do **not** bake it into the image —
   mount it as a volume so the image stays small and the DB is swappable:
   ```yaml
   # add to api + worker services in docker-compose.yml. The container's HOME
   # is /app, so the engine looks for the DB under /app/.giae/diamond/.
   volumes:
     - giae_db:/app/.giae
   ```
   Build it once into the named volume (one-off job or an init container):
   ```bash
   # inside a container that mounts the volume at /app/.giae:
   giae db download swissprot-diamond           # small (E. coli) — smoke test
   # or full Swiss-Prot (recommended, 575k proteins):
   curl -o sprot.fasta.gz https://ftp.uniprot.org/.../uniprot_sprot.fasta.gz
   gunzip -c sprot.fasta.gz | diamond makedb --db /app/.giae/diamond/swissprot
   ```
   The engine resolves the DB at `/app/.giae/diamond/swissprot.dmnd`. **The
   worker warms its interpreter at startup, so build the DB into the volume
   *before* first boot (or restart the worker after) — otherwise it registers
   diamond as unavailable and silently runs the offline config.**

   **Volume ownership:** the container runs as uid 1000 (`giae`), and the same
   `/app/.giae` volume also holds the engine's SQLite cache (`cache.db`). If you
   populate the volume from a root container, `chown -R 1000:1000` it afterwards
   — otherwise the worker can't write its cache and every job fails with
   "unable to open database file":
   ```bash
   docker run --rm -v <project>_giae_db:/d alpine chown -R 1000:1000 /d
   ```
   The calibration mapping (`data/calibration/calibration_mapping.json`) **is**
   already bundled in the image, so calibrated confidence lights up as soon as
   diamond + DB are present.

**Optional (later):** HMMER/Pfam (`GIAE_ENABLE_HMMER=1` + a Pfam DB) and ESM
(`GIAE_ENABLE_ESM=1`, GPU recommended). Both are fork-safe now (lazy per-worker
init) but validate in staging before enabling in prod.

## 3. Prerequisites & secrets

Create a `.env` next to `docker-compose.yml`:

```dotenv
POSTGRES_USER=giae
POSTGRES_PASSWORD=<strong-random>
POSTGRES_DB=giae
JWT_SECRET=<openssl rand -base64 32>          # API refuses to boot in prod without this
NEXTAUTH_SECRET=<openssl rand -base64 32>
NEXTAUTH_URL=https://app.yourdomain.com
CORS_ALLOWED_ORIGINS=https://app.yourdomain.com
ENV=prod
JWT_ACCESS_TOKEN_TTL_MINUTES=60               # refresh tokens (30d) keep sessions alive
```

- `JWT_SECRET` and `NEXTAUTH_SECRET` must be strong and **stable** (rotating
  them invalidates all sessions/API tokens). Store in your platform's secret
  manager, not git.
- The browser never sees the API directly — it calls the Next proxy, which
  attaches the token server-side — so there is no `NEXT_PUBLIC_API_URL` to leak.

## 4. Deploy options

### Option A — single VM + docker compose  (recommended for the pilot)
Cheapest and closest to the repo. One 4-core / 8 GB VM handles a pilot.

1. Provision a VM (Ubuntu 22.04), install Docker + compose plugin.
2. Clone the repo, add `.env` (§3), apply the §2 image changes.
3. Put a TLS reverse proxy in front (Caddy is one line per host, auto-HTTPS):
   ```
   app.yourdomain.com { reverse_proxy localhost:3000 }
   ```
   Keep `api` and `postgres`/`redis` unpublished (compose network only); only
   the frontend (3000) is proxied publicly. The API is reached via the Next
   proxy over the internal network.
4. `docker compose up -d --build`
5. Build the Swiss-Prot DB into the `giae_db` volume (§2).

### Option B — managed platform
Frontend on Vercel (native Next.js) or a container host; API + worker as
containers on Fly.io / Render / Railway; **managed Postgres** and **managed
Redis** (don't self-host stateful services if you can avoid it). The worker
needs the Swiss-Prot DB on a persistent volume — Fly volumes or a startup
download-and-build. Set the same env as §3.

## 5. First-deploy runbook

```bash
# 1. schema — sql/init.sql runs automatically on first Postgres boot
# 2. bring up the stack
docker compose up -d --build
# 3. wait for health
curl -fsS https://app.yourdomain.com/api/v1/health   # {"status":"ok"}
# 4. build the Swiss-Prot DB into the mounted volume (§2), then restart worker
docker compose restart worker
# 5. create the first account via the UI (/signup) or API
```

## 6. Post-deploy verification (proves the good config is live)

1. Upload a small genome (e.g. `case_studies/lambda_phage.gb`) via the UI.
2. Open the job; confirm on a homology-backed gene you see:
   - a **Strongest hit** of `diamond …` (not just motif/PROSITE),
   - a **Calibrated reliability** panel (proves diamond + calibration are live),
   - GO/EC chips where applicable.
   If those are missing, the §2 gap isn't closed — the container is running the
   offline config.
3. Confirm a session survives past `JWT_ACCESS_TOKEN_TTL_MINUTES` without a
   re-login (refresh tokens working).

## 7. Operations

- **Scaling**: the worker is the bottleneck. `docker compose up -d --scale
  worker=N`, or run workers on separate machines pointed at the same Redis.
  The API is stateless — scale behind the proxy.
- **Backups**: snapshot the `postgres_data` volume on a schedule; `reports_data`
  and `uploads_data` are regenerable but cheap to back up.
- **Logs**: API emits structured JSON request logs; ship stdout to your log
  stack. Watch worker logs for `Batch pre-scan: diamond over N genes` — its
  absence means diamond isn't active.
- **DB TTL / refresh**: access tokens are 60 min, refresh tokens 30 days; the
  proxy refreshes transparently. No action needed.
- **Resource sizing**: diamond loads the 280 MB DB per genome scan; give the
  worker ≥ 2 GB RAM. Bacterial genomes (~4k genes) take ~15–35 s each.

## 8. Security checklist

- [ ] `JWT_SECRET` + `NEXTAUTH_SECRET` strong, stable, in a secret manager
- [ ] Postgres/Redis not published to the public internet (compose network only)
- [ ] TLS terminated at the proxy; `NEXTAUTH_URL` is `https://`
- [ ] `CORS_ALLOWED_ORIGINS` limited to your real origin(s)
- [ ] File-upload limits enforced (proxy caps at 50 MB, `.gb/.gbk/.fasta/.fa/.fna`)
- [ ] Rate limiting on auth endpoints is on (signup 5/min, login 10/min per IP)
- [ ] Run containers as the non-root `giae` user (already set in the Dockerfile)

## 9. Known follow-ups

- Bake pyrodigal + diamond into the image (§2) — **required for parity with the benchmark**.
- HMMER/ESM staging validation before enabling in prod.
- A migration tool (Alembic) if the schema evolves beyond `sql/init.sql`.
- UniProt idmapping enrichment for fuller prediction-side GO/EC coverage.
