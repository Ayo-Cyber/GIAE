# Security Policy

GIAE includes a public-facing REST API with authentication, file uploads,
and a job-execution worker. We take security seriously and welcome
responsible disclosure of vulnerabilities.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅ Receiving security fixes |
| 0.1.x   | ❌ End of life — please upgrade |

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Instead, report privately via one of:

- **GitHub Security Advisories** — preferred. Open a private advisory at
  [github.com/Ayo-Cyber/GIAE/security/advisories/new](https://github.com/Ayo-Cyber/GIAE/security/advisories/new).
- **Email** — `security@giae.dev` (or the maintainer email in
  [`pyproject.toml`](pyproject.toml) if that address isn't yet active).

Please include:

- A clear description of the vulnerability
- Steps to reproduce, or a proof-of-concept
- The version of GIAE affected (`giae --version`)
- Your assessment of impact and severity
- Whether you'd like credit in the disclosure

We commit to:

| Step | Target turnaround |
|---|---|
| Acknowledge receipt | 48 hours |
| Initial assessment | 5 business days |
| Fix or mitigation | 30 days for critical, 90 days for low/moderate |
| Public disclosure | Coordinated with the reporter |

## Scope

Vulnerabilities **in scope** for this policy:

- The GIAE Python package (CLI, library, internal modules)
- The REST API (`giae_api/`) and its authentication layer
- The Celery worker job-processing pipeline
- The Docker images shipped from this repository
- The mkdocs documentation site

Issues **out of scope**:

- Vulnerabilities in upstream dependencies (BioPython, FastAPI, Celery,
  etc.) — please report those upstream. We'll absorb their fixes.
- Bugs that don't have a security impact (open a regular issue).
- Self-XSS, social-engineering attacks, physical access, denial of
  service through resource exhaustion on a public-facing instance you
  don't own.

## What we ask of you

Please:

- Give us reasonable time to fix before disclosing publicly.
- Avoid privacy violations, data destruction, or service disruption
  during testing.
- Don't access data that isn't yours.
- Test only against deployments you control or are authorised to test.

## Recognition

We're happy to credit security researchers who responsibly disclose
vulnerabilities. With your permission, we'll list you in the
[CHANGELOG](CHANGELOG.md) entry for the fix and in any associated
GitHub Security Advisory.

## Threat model notes

A few things worth knowing if you're auditing GIAE:

- **JWT secret.** `JWT_SECRET` must be set in production
  (`ENV=production`). The dev fallback (`dev-insecure-secret-do-not-use-in-prod`)
  refuses to boot when `ENV` is `prod`/`production`.
- **API keys.** Stored only as `sha256(raw_key)`; the raw key is
  shown to the user **once** at creation. Compared with `hmac.compare_digest`.
- **Passwords.** Hashed with `bcrypt` (passlib `CryptContext`). Bcrypt's
  72-byte limit is handled by truncating defensively at the boundary.
- **Worker isolation.** Celery workers run uploaded genomes through
  pyrodigal, BioPython, and (optionally) `aragorn` / `barrnap` /
  `diamond`. None of these load uploaded code. We don't `eval` or
  `exec` user content.
- **File handling.** Uploads go to `uploads/` with a UUID prefix. We
  don't trust the filename — it's only echoed back in the report
  title.
- **Database access.** Job rows are scoped per-user in queries; no
  endpoint trusts a `user_id` from the request body.

If you find a way to bypass any of the above, that's exactly the kind
of report we want.
