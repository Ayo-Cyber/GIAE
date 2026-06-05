from __future__ import annotations

import json as _json
import logging
import os
import shutil
import time
import uuid
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from . import auth, database, models
from .worker import process_genome_task

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return _json.dumps(payload)

_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger("giae.api")

# ---------------------------------------------------------------------------
# In-memory rate limiter (per-IP, sliding window)
# ---------------------------------------------------------------------------
_rate_store: dict[str, list[float]] = defaultdict(list)

def _check_rate(key: str, limit: int, window_secs: int) -> None:
    now = time.monotonic()
    hits = _rate_store[key]
    # drop timestamps outside the window
    _rate_store[key] = [t for t in hits if now - t < window_secs]
    if len(_rate_store[key]) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Max {limit} per {window_secs}s.",
            headers={"Retry-After": str(window_secs)},
        )
    _rate_store[key].append(now)

# Absolute base directory — always the repo root regardless of process CWD
_BASE_DIR = Path(__file__).resolve().parents[2]  # src/giae_api → src → repo root
UPLOAD_DIR = _BASE_DIR / "uploads"
REPORTS_DIR = _BASE_DIR / "public_reports"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = ""
    last_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class WaitlistRequest(BaseModel):
    email: EmailStr


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


class APIKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: str
    last_used_at: Optional[str]
    expires_at: Optional[str]
    revoked_at: Optional[str]


# ---------------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------------
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="GIAE API",
    description="Genome Interpretation & Annotation API core",
    version="0.2.0",
)

# CORS: localhost dev + a single placeholder prod domain. Override via env
# ``CORS_ALLOWED_ORIGINS`` as a comma-separated list when deploying.
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://app.giae.io",  # placeholder production domain
]
_env_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
allowed_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Static reports
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    ms = round((time.monotonic() - t0) * 1000)
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": ms,
            "ip": request.client.host if request.client else "unknown",
        },
    )
    return response


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "message": "GIAE API Engine is fully operational."}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.post("/api/v1/auth/signup", status_code=201, response_model=TokenResponse)
def signup(body: RegisterRequest, request: Request, db: Session = Depends(database.get_db)):
    ip = request.client.host if request.client else "unknown"
    _check_rate(f"signup:{ip}", limit=5, window_secs=60)
    email = body.email.lower()
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")
    user = models.User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=auth.hash_password(body.password),
        first_name=body.first_name or None,
        last_name=body.last_name or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token, expires_in = auth.create_access_token(user.id, user.email)
    logger.info("user_signup", extra={"user_id": user.id, "email": email})
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user={
            "id": user.id,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
        },
    )


# Kept as an alias so the existing Next.js signup page (which posts to /register)
# does not break. Prefer /signup in new clients.
@app.post("/api/v1/auth/register", status_code=201, response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(database.get_db)):
    return signup(body, db)


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(database.get_db)):
    ip = request.client.host if request.client else "unknown"
    _check_rate(f"login:{ip}", limit=10, window_secs=60)
    email = body.email.lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not user.is_active or not auth.verify_password(body.password, user.hashed_password):
        logger.warning("login_failed", extra={"email": email, "ip": ip})
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    token, expires_in = auth.create_access_token(user.id, user.email)
    logger.info("login_success", extra={"user_id": user.id, "email": email})
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user={
            "id": user.id,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
        },
    )


@app.get("/api/v1/auth/me")
def me(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "firstName": current_user.first_name,
        "lastName": current_user.last_name,
    }


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------
@app.post("/api/v1/keys", status_code=201)
def create_api_key(
    body: CreateAPIKeyRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    raw, prefix, digest = auth.generate_api_key()
    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    key = models.APIKey(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=digest,
        expires_at=expires_at,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return {
        "id": key.id,
        "name": key.name,
        "key_prefix": key.key_prefix,
        "key": raw,  # shown ONCE — never returned again
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "created_at": key.created_at.isoformat(),
    }


@app.get("/api/v1/keys")
def list_api_keys(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    keys = (
        db.query(models.APIKey)
        .filter(models.APIKey.user_id == current_user.id)
        .order_by(models.APIKey.created_at.desc())
        .all()
    )
    return {
        "keys": [
            APIKeyOut(
                id=k.id,
                name=k.name,
                key_prefix=k.key_prefix,
                created_at=k.created_at.isoformat(),
                last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
                expires_at=k.expires_at.isoformat() if k.expires_at else None,
                revoked_at=k.revoked_at.isoformat() if k.revoked_at else None,
            ).model_dump()
            for k in keys
        ]
    }


@app.delete("/api/v1/keys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    key = db.query(models.APIKey).filter(models.APIKey.id == key_id).first()
    if not key or key.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
@app.post("/api/v1/jobs")
async def create_job(
    file: UploadFile = File(...),
    phage_mode: bool = Form(False),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Submit a genome for interpretation.

    Form fields:
      file        — FASTA or GenBank genome file (required).
      phage_mode  — Set to true to enable phage-aware nested ORF detection.
    """
    job_id = str(uuid.uuid4())

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = str(UPLOAD_DIR / f"{job_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_job = models.Job(
        id=job_id,
        user_id=current_user.id,
        filename=file.filename,
        status=models.JobStatus.PENDING.value,
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    task = process_genome_task.delay(job_id, file_path, file.filename, phage_mode)
    db_job.celery_task_id = task.id
    db.commit()

    return {
        "job_id": job_id,
        "status": "PENDING",
        "filename": file.filename,
        "phage_mode": phage_mode,
    }


@app.get("/api/v1/jobs")
def list_jobs(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    jobs = (
        db.query(models.Job)
        .filter(models.Job.user_id == current_user.id)
        .order_by(models.Job.created_at.desc())
        .all()
    )
    return {
        "jobs": [
            {
                "job_id": j.id,
                "filename": j.filename,
                "status": j.status,
                "report_url": j.report_url,
                "total_genes": j.total_genes,
                "high_confidence_count": j.high_confidence_count,
                "dark_count": j.dark_count,
                "processing_time_seconds": j.processing_time_seconds,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
    }


@app.post("/api/v1/jobs/{job_id}/rerun")
def rerun_job(
    job_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id and job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    file_path = str(UPLOAD_DIR / f"{job_id}_{job.filename}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=409, detail="Original upload file not found")

    # Snapshot current genes before clearing so history diff is available
    if job.genes_json:
        job.previous_genes_json = job.genes_json

    job.status = models.JobStatus.PENDING.value
    job.error_message = None
    job.total_genes = None
    job.interpreted_genes = None
    job.high_confidence_count = None
    job.dark_count = None
    job.processing_time_seconds = None
    job.genes_json = None
    job.report_url = None
    db.commit()

    process_genome_task.delay(job_id, file_path, job.filename)
    return {"job_id": job_id, "status": "PENDING"}


@app.get("/api/v1/jobs/{job_id}")
def get_job_status(
    job_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id and job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    genes = _json.loads(job.genes_json) if job.genes_json else []

    return {
        "job_id": job.id,
        "filename": job.filename,
        "status": job.status,
        "report_url": job.report_url,
        "error_message": job.error_message,
        "total_genes": job.total_genes,
        "interpreted_genes": job.interpreted_genes,
        "high_confidence_count": job.high_confidence_count,
        "dark_count": job.dark_count,
        "processing_time_seconds": job.processing_time_seconds,
        "genes": genes,
    }


@app.get("/api/v1/dark-genes")
def list_dark_genes(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    limit = max(1, min(limit, 500))  # clamp: 1–500
    jobs = (
        db.query(models.Job)
        .filter(
            models.Job.user_id == current_user.id,
            models.Job.status == "COMPLETED",
            models.Job.genes_json.isnot(None),
        )
        .all()
    )

    dark = []
    seen_ids: set[str] = set()
    for job in jobs:
        genes = _json.loads(job.genes_json)
        for g in genes:
            if g.get("is_dark") and g["id"] not in seen_ids:
                seen_ids.add(g["id"])
                dark.append(
                    {
                        "id": g["id"],
                        "name": g.get("name") or g["id"],
                        "locus": g.get("locus") or g["id"],
                        "organism": job.filename,
                        "job_id": job.id,
                    }
                )

    total = len(dark)
    page = dark[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "genes": page}


@app.post("/api/v1/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id and job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if job.status not in (models.JobStatus.PENDING.value, models.JobStatus.RUNNING.value):
        raise HTTPException(status_code=409, detail="Job is not in a cancellable state")

    if job.celery_task_id:
        from .worker import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")

    job.status = models.JobStatus.CANCELLED.value
    job.error_message = "Cancelled by user"
    db.commit()
    return {"job_id": job_id, "status": "CANCELLED"}


@app.get("/api/v1/worker/status")
def worker_status():
    try:
        from .worker import celery_app
        inspector = celery_app.control.inspect(timeout=2.0)
        ping = inspector.ping() or {}
        online = bool(ping)
        if online:
            active = inspector.active() or {}
            reserved = inspector.reserved() or {}
            active_count = sum(len(v) for v in active.values())
            queued_count = sum(len(v) for v in reserved.values())
            worker_names = list(ping.keys())
        else:
            active_count = 0
            queued_count = 0
            worker_names = []
    except Exception:
        online = False
        active_count = 0
        queued_count = 0
        worker_names = []

    return {
        "online": online,
        "workers": worker_names,
        "active_tasks": active_count,
        "queued_tasks": queued_count,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Notifications (derived from recent job state changes)
# ---------------------------------------------------------------------------
@app.get("/api/v1/notifications")
def list_notifications(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    jobs = (
        db.query(models.Job)
        .filter(
            models.Job.user_id == current_user.id,
            models.Job.status.in_(["COMPLETED", "FAILED", "CANCELLED"]),
        )
        .order_by(models.Job.created_at.desc())
        .limit(30)
        .all()
    )

    # Also surface watched loci that got annotated in recent completed jobs
    watched = (
        db.query(models.WatchlistEntry)
        .filter(models.WatchlistEntry.user_id == current_user.id)
        .all()
    )
    watched_loci = {w.locus for w in watched}

    notifications = []
    for j in jobs:
        ntype = "completed" if j.status == "COMPLETED" else "failed" if j.status == "FAILED" else "cancelled"
        notifications.append({
            "id": f"job:{j.id}",
            "type": ntype,
            "job_id": j.id,
            "filename": j.filename,
            "message": (
                f"Annotation complete — {j.total_genes} genes interpreted"
                if j.status == "COMPLETED"
                else f"Job failed: {j.error_message or 'unknown error'}"
                if j.status == "FAILED"
                else "Job was cancelled"
            ),
            "created_at": j.created_at.isoformat() if j.created_at else None,
        })

        # Check if any watched loci appear as non-dark in this job
        if j.status == "COMPLETED" and j.genes_json and watched_loci:
            genes = _json.loads(j.genes_json)
            for g in genes:
                if g.get("locus") in watched_loci and not g.get("is_dark"):
                    notifications.append({
                        "id": f"watch:{j.id}:{g['locus']}",
                        "type": "watch_hit",
                        "job_id": j.id,
                        "filename": j.filename,
                        "message": f"Watched gene {g.get('name', g['locus'])} was annotated: {g.get('function', 'unknown function')}",
                        "created_at": j.created_at.isoformat() if j.created_at else None,
                    })

    return {"notifications": notifications}


# ---------------------------------------------------------------------------
# Annotation history diff
# ---------------------------------------------------------------------------
@app.get("/api/v1/jobs/{job_id}/history")
def get_job_history(
    job_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.previous_genes_json:
        raise HTTPException(status_code=404, detail="No previous run to compare")

    return {
        "previous_genes": _json.loads(job.previous_genes_json),
        "current_genes": _json.loads(job.genes_json) if job.genes_json else [],
    }


# ---------------------------------------------------------------------------
# Gene watchlist
# ---------------------------------------------------------------------------
@app.get("/api/v1/watchlist")
def list_watchlist(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    entries = (
        db.query(models.WatchlistEntry)
        .filter(models.WatchlistEntry.user_id == current_user.id)
        .order_by(models.WatchlistEntry.created_at.desc())
        .all()
    )
    return {
        "entries": [
            {"id": e.id, "locus": e.locus, "gene_name": e.gene_name, "created_at": e.created_at.isoformat()}
            for e in entries
        ]
    }


class WatchlistAddRequest(BaseModel):
    locus: str
    gene_name: str


@app.post("/api/v1/watchlist", status_code=201)
def add_to_watchlist(
    body: WatchlistAddRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    existing = db.query(models.WatchlistEntry).filter(
        models.WatchlistEntry.user_id == current_user.id,
        models.WatchlistEntry.locus == body.locus,
    ).first()
    if existing:
        return {"id": existing.id, "locus": existing.locus, "status": "already_watching"}

    entry = models.WatchlistEntry(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        locus=body.locus,
        gene_name=body.gene_name,
    )
    db.add(entry)
    db.commit()
    return {"id": entry.id, "locus": entry.locus, "status": "watching"}


@app.delete("/api/v1/watchlist/{locus:path}", status_code=204)
def remove_from_watchlist(
    locus: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    entry = db.query(models.WatchlistEntry).filter(
        models.WatchlistEntry.user_id == current_user.id,
        models.WatchlistEntry.locus == locus,
    ).first()
    if entry:
        db.delete(entry)
        db.commit()
    return None


# ---------------------------------------------------------------------------
# Share tokens (public read access to a completed job)
# ---------------------------------------------------------------------------
@app.post("/api/v1/jobs/{job_id}/share", status_code=201)
def create_share_token(
    job_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "COMPLETED":
        raise HTTPException(status_code=409, detail="Only completed jobs can be shared")

    # Reuse existing token if one exists for this job
    existing = db.query(models.ShareToken).filter(models.ShareToken.job_id == job_id).first()
    if existing:
        return {"token": existing.token, "url": f"/report/{existing.token}"}

    token = str(uuid.uuid4()).replace("-", "")
    db.add(models.ShareToken(token=token, job_id=job_id))
    db.commit()
    logger.info("share_created", extra={"job_id": job_id, "user_id": current_user.id})
    return {"token": token, "url": f"/report/{token}"}


@app.get("/api/v1/share/{token}")
def get_shared_job(token: str, db: Session = Depends(database.get_db)):
    share = db.query(models.ShareToken).filter(models.ShareToken.token == token).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    job = db.query(models.Job).filter(models.Job.id == share.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    genes = _json.loads(job.genes_json) if job.genes_json else []
    return {
        "job_id": job.id,
        "filename": job.filename,
        "status": job.status,
        "total_genes": job.total_genes,
        "interpreted_genes": job.interpreted_genes,
        "high_confidence_count": job.high_confidence_count,
        "dark_count": job.dark_count,
        "processing_time_seconds": job.processing_time_seconds,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "report_url": job.report_url,
        "error_message": None,
        "genes": genes,
    }


# ---------------------------------------------------------------------------
# Waitlist (public)
# ---------------------------------------------------------------------------
@app.post("/api/v1/waitlist", status_code=201)
def join_waitlist(body: WaitlistRequest, db: Session = Depends(database.get_db)):
    email = body.email.lower()
    existing = db.query(models.WaitlistEntry).filter(models.WaitlistEntry.email == email).first()
    if existing:
        return {"status": "already_registered"}
    entry = models.WaitlistEntry(id=str(uuid.uuid4()), email=email)
    db.add(entry)
    db.commit()
    return {"status": "ok"}
