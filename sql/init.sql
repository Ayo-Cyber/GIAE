-- GIAE schema bootstrap.
-- Idempotent; safe to run on every container start. SQLAlchemy create_all
-- will keep this in sync at the application layer too — this file exists so
-- the DB has a known-good shape even before the API ever boots.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT UNIQUE,                       -- if citext is missing the column will be VARCHAR via the app layer
    email_lower     VARCHAR(320) UNIQUE NOT NULL,        -- guaranteed-lower copy for portable case-insensitive lookup
    hashed_password VARCHAR(255)        NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    is_active       BOOLEAN             NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN             NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users (email_lower);

-- ---------------------------------------------------------------------------
-- API keys
-- Raw key shown to the user once at creation; only a SHA-256 hash is stored.
-- prefix is the first 8 chars (after the `gia_` tag) for UI display.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    key_prefix      VARCHAR(16)  NOT NULL,
    key_hash        VARCHAR(64)  NOT NULL UNIQUE,        -- sha256 hex
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys (user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys (key_hash);

-- ---------------------------------------------------------------------------
-- Jobs (existing)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id                       VARCHAR(64) PRIMARY KEY,
    user_id                  UUID REFERENCES users(id) ON DELETE SET NULL,
    filename                 VARCHAR(512),
    status                   VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    report_url               VARCHAR(1024),
    error_message            TEXT,
    total_genes              INTEGER,
    interpreted_genes        INTEGER,
    high_confidence_count    INTEGER,
    dark_count               INTEGER,
    processing_time_seconds  INTEGER,
    genes_json               TEXT,
    celery_task_id           VARCHAR(128),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs (user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at DESC);

-- ---------------------------------------------------------------------------
-- Waitlist (existing)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS waitlist (
    id          VARCHAR(64) PRIMARY KEY,
    email       VARCHAR(320) UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
