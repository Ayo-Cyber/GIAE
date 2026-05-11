# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# GIAE Python image — used by both `api` and `worker` services.
# Multi-stage so runtime images don't carry build toolchains.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pyhmmer + biopython occasionally need build deps; psycopg2 needs libpq.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data

RUN pip install --upgrade pip wheel \
    && pip wheel --wheel-dir /wheels \
        ".[api]" \
        "python-jose[cryptography]>=3.3.0" \
        "passlib[bcrypt]>=1.7.4" \
        "bcrypt<4.0" \
        "psycopg2-binary>=2.9.9" \
        "email-validator>=2.0.0"

# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 giae \
    && useradd  --system --uid 1000 --gid giae --shell /bin/bash --home /app giae

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data

RUN pip install --no-index --find-links /wheels \
        "giae[api]" \
        "python-jose[cryptography]" \
        "passlib[bcrypt]" \
        "bcrypt<4.0" \
        "psycopg2-binary" \
        "email-validator" \
    && rm -rf /wheels

RUN mkdir -p /app/uploads /app/public_reports \
    && chown -R giae:giae /app

USER giae

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# Default command runs the API. The worker service overrides this.
CMD ["uvicorn", "giae_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
