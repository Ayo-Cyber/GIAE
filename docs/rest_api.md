# REST API reference

GIAE ships a full REST API (`giae_api`) for running interpretation as a
service: async job queue, multi-user, two auth schemes. Everything in
this doc is what runs when you `docker compose up` or `giae serve`.

**Base URL:** `http://your-host:8000`
**API prefix:** `/api/v1`
**Interactive docs:** `http://your-host:8000/docs` (Swagger) or
`/redoc` (ReDoc)

---

## Authentication

Two equally valid credentials, in priority order:

1. **JWT bearer** — short-lived (default 60 min), issued by `/auth/login`.
2. **API key** — long-lived, issued by `/keys`. Send as `X-API-Key: gia_...`.

```bash
# Bearer
curl -H "Authorization: Bearer eyJhbGc..." ...

# API key
curl -H "X-API-Key: gia_xxxxxxxxxxxxxxxxxxxx" ...
```

Either resolves to a `User`. `/auth/me`, all `/keys/*`, and all
`/jobs/*` routes require auth. `/health`, `/auth/signup`,
`/auth/login`, `/waitlist`, and `/reports/{id}.html` (static) are
public.

API keys are stored only as `sha256(raw_key)` — the raw value is shown
**once** at creation. Compared with `hmac.compare_digest`.

---

## Health & status

### `GET /api/v1/health`

```bash
curl http://localhost:8000/api/v1/health
```

```json
{ "status": "ok", "message": "GIAE API Engine is fully operational." }
```

Public. No auth required.

### `GET /api/v1/worker/status`

Pings the Celery worker pool via Redis.

```json
{ "online": true }
```

Public.

---

## Auth

### `POST /api/v1/auth/signup` &nbsp;`201`

Create a new account and receive a token.

```json
// request
{
  "email": "you@lab.org",
  "password": "correct-horse-battery",
  "first_name": "Ada",
  "last_name": "Lovelace"
}
```

```json
// 201 Created
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "id": "uuid", "email": "you@lab.org", "firstName": "Ada", "lastName": "Lovelace" }
}
```

| Status | Meaning |
|---|---|
| `201` | Created |
| `409` | Email already registered |
| `422` | Validation error (invalid email, password too short) |

Password requirements: 8 ≤ length ≤ 128.

`/api/v1/auth/register` is an alias for backwards compatibility with
older frontend clients.

### `POST /api/v1/auth/login` &nbsp;`200`

Same response shape as signup.

```json
// request
{ "email": "you@lab.org", "password": "correct-horse-battery" }
```

| Status | Meaning |
|---|---|
| `200` | OK |
| `401` | Invalid credentials |

### `GET /api/v1/auth/me` &nbsp;`200`

Current user (auth required).

```json
{ "id": "uuid", "email": "you@lab.org", "firstName": "Ada", "lastName": "Lovelace" }
```

---

## API keys

For programmatic clients that don't want to refresh JWTs every hour.

### `POST /api/v1/keys` &nbsp;`201`

Create a new key. The raw value is shown **once** in this response —
store it immediately.

```json
// request
{ "name": "ci-bot", "expires_in_days": 365 }
```

```json
// 201 Created
{
  "id": "uuid",
  "name": "ci-bot",
  "key_prefix": "gia_abcd1234",
  "key": "gia_abcd1234ef56...",         // ⚠️ shown once
  "expires_at": "2027-05-09T...",
  "created_at": "2026-05-09T..."
}
```

| Field | Constraints |
|---|---|
| `name` | 1–100 chars |
| `expires_in_days` | optional, 1–3650 |

### `GET /api/v1/keys` &nbsp;`200`

List your keys (no raw values — only prefixes).

```json
{
  "keys": [
    {
      "id": "uuid",
      "name": "ci-bot",
      "key_prefix": "gia_abcd1234",
      "created_at": "2026-05-09T...",
      "last_used_at": "2026-05-09T...",
      "expires_at": "2027-05-09T...",
      "revoked_at": null
    }
  ]
}
```

### `DELETE /api/v1/keys/{key_id}` &nbsp;`204`

Revoke a key. Idempotent.

| Status | Meaning |
|---|---|
| `204` | Revoked |
| `404` | Key not found or doesn't belong to you |

---

## Jobs

The core surface — submit a genome, poll status, fetch the report.

### `POST /api/v1/jobs` &nbsp;`200`

Submit a genome for interpretation. Multipart form upload.

| Form field | Type | Required | Description |
|---|---|---|---|
| `file` | file | yes | `.gb`, `.gbk`, `.fa`, or `.fasta` |
| `phage_mode` | bool | no | Default `false`. `true` enables phage-aware nested-ORF detection |

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@lambda_phage.gb" \
  -F "phage_mode=true"
```

```json
// 200 OK
{
  "job_id": "abc-1234-...",
  "status": "PENDING",
  "filename": "lambda_phage.gb",
  "phage_mode": true
}
```

The job is enqueued to Celery. Poll `/jobs/{id}` until `status` is
`COMPLETED` or `FAILED`.

### `GET /api/v1/jobs` &nbsp;`200`

List your jobs (most recent first).

```json
{
  "jobs": [
    {
      "job_id": "...",
      "filename": "lambda_phage.gb",
      "status": "COMPLETED",
      "report_url": "/reports/....html",
      "total_genes": 92,
      "high_confidence_count": 45,
      "dark_count": 44,
      "processing_time_seconds": 4,
      "created_at": "2026-05-09T..."
    }
  ]
}
```

### `GET /api/v1/jobs/{job_id}` &nbsp;`200`

Full job detail, including the per-gene results when complete.

```json
{
  "job_id": "...",
  "filename": "lambda_phage.gb",
  "status": "COMPLETED",
  "report_url": "/reports/....html",
  "error_message": null,
  "total_genes": 92,
  "interpreted_genes": 92,
  "high_confidence_count": 45,
  "dark_count": 44,
  "processing_time_seconds": 4,
  "genes": [
    {
      "id": "gene_...",
      "name": "cI",
      "locus": "lambda_cI",
      "is_dark": false,
      "confidence": "HIGH",
      "score": 0.873,
      "function": "Repressor protein CI",
      "normalized_product": "Repressor protein CI",
      "cog_category": "K",
      "cog_name": "Transcription",
      "cog_source": "pfam",
      "go_terms": ["GO:0003677", "GO:0006355"],
      "pfam_id": "PF01381",
      "category": "transcription",
      "reasoning": "Pfam HTH_3 hit (1.2e-9) ...",
      "evidence": [
        { "label": "PF01381 (HTH_3)", "source": "pyhmmer", "conf": 0.94 },
        { "label": "P03034 — Repressor CI, λ phage", "source": "uniprot", "conf": 0.96 }
      ]
    }
  ]
}
```

| Status | Meaning |
|---|---|
| `200` | OK |
| `403` | Job belongs to another user |
| `404` | Job not found |

`status` values: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.

### `POST /api/v1/jobs/{job_id}/cancel` &nbsp;`200`

Cancel a `PENDING` or `RUNNING` job.

| Status | Meaning |
|---|---|
| `200` | Cancelled |
| `403` | Not your job |
| `404` | Job not found |
| `409` | Job is already in a terminal state |

### `POST /api/v1/jobs/{job_id}/rerun` &nbsp;`200`

Re-queue a previously completed (or failed) job using the original
upload. Useful for re-running with newer GIAE behaviour.

| Status | Meaning |
|---|---|
| `200` | Re-queued |
| `403` | Not your job |
| `404` | Job not found |
| `409` | Original upload file no longer exists |

---

## Dark-genes index

### `GET /api/v1/dark-genes` &nbsp;`200`

Aggregate dark-matter genes across **all your completed jobs**.
Useful for building a research backlog.

```json
{
  "total": 87,
  "genes": [
    {
      "id": "gene_...",
      "name": "ea22",
      "locus": "lambda_ea22",
      "organism": "lambda_phage.gb",
      "job_id": "..."
    }
  ]
}
```

---

## Reports

### `GET /reports/{job_id}.html`

Static HTML report (generated by the worker on completion). Mounted
under `/reports` from the `public_reports/` volume. **Public** — no
auth required, on the assumption that the job_id is unguessable
(UUID4).

```bash
open http://localhost:8000/reports/abc-1234-....html
```

If you want this private, put the API behind a reverse proxy that
checks `Authorization` before forwarding `/reports/*` paths.

---

## Waitlist (public)

### `POST /api/v1/waitlist` &nbsp;`201`

Capture an email for the upcoming hosted SaaS launch. Used by the
landing page; can be ignored if you're self-hosting.

```json
// request
{ "email": "interested@lab.org" }
```

```json
// 201 Created
{ "status": "ok" }            // first time
{ "status": "already_registered" }  // duplicate
```

---

## OpenAPI schema

The full OpenAPI 3 schema is available at runtime:

```bash
curl http://localhost:8000/openapi.json
```

Use this to generate clients for your favourite language.

---

## Errors

Standard FastAPI / Pydantic error envelope:

```json
{
  "detail": "Invalid credentials."
}
```

For validation errors (`422`):

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate limiting

Not enforced by GIAE itself — put a reverse proxy (Nginx, Caddy, Cloudflare) in front for production rate limiting. The Celery worker pool acts as a natural throttle for compute (default `--concurrency 4`).

---

## CORS

`CORS_ALLOWED_ORIGINS` env var, comma-separated. Default:
`http://localhost:3000,https://app.giae.io`. See
[deployment.md](deployment.md#environment-variables).
