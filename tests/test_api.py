"""Smoke tests for the GIAE API.

Uses FastAPI's TestClient and an in-memory SQLite database. The Celery
task is monkey-patched so jobs don't actually run — we only verify the
HTTP surface, auth, and DB persistence.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# Set env BEFORE importing the API — engine is created at import time.
_TMPDB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMPDB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDB.name}"
os.environ["JWT_SECRET"] = "test-secret-do-not-use"

from fastapi.testclient import TestClient  # noqa: E402

from giae_api import main as api_main  # noqa: E402
from giae_api import worker as api_worker  # noqa: E402


@pytest.fixture(autouse=True)
def _stub_celery_task(monkeypatch):
    """Replace the Celery task with a no-op so tests don't need Redis."""
    class _FakeTask:
        id = "fake-task-id"

    def _fake_delay(*args, **kwargs):
        return _FakeTask()

    monkeypatch.setattr(api_worker.process_genome_task, "delay", _fake_delay)
    monkeypatch.setattr(api_main, "process_genome_task", api_worker.process_genome_task)


@pytest.fixture
def client():
    return TestClient(api_main.app)


@pytest.fixture
def auth_headers(client):
    """Sign up a fresh user and return Authorization headers."""
    import uuid as _uuid
    email = f"test-{_uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_unauthenticated(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_signup_returns_token_and_user(client):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "alice@example.com", "password": "correct-horse-battery"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "alice@example.com"


def test_signup_duplicate_email_409(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "bob@example.com", "password": "correct-horse-battery"},
    )
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "bob@example.com", "password": "correct-horse-battery"},
    )
    assert r.status_code == 409


def test_login_with_correct_password(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "carol@example.com", "password": "correct-horse-battery"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "correct-horse-battery"},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_password_401(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "dave@example.com", "password": "correct-horse-battery"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "dave@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert "email" in r.json()


# ── API keys ──────────────────────────────────────────────────────────────────

def test_create_and_list_api_key(client, auth_headers):
    r = client.post(
        "/api/v1/keys",
        headers=auth_headers,
        json={"name": "ci-bot"},
    )
    assert r.status_code == 201
    raw_key = r.json()["key"]
    assert raw_key.startswith("gia_")

    # New key shows up in list
    listing = client.get("/api/v1/keys", headers=auth_headers)
    assert listing.status_code == 200
    keys = listing.json()["keys"]
    assert any(k["name"] == "ci-bot" for k in keys)


def test_api_key_authenticates(client, auth_headers):
    r = client.post(
        "/api/v1/keys",
        headers=auth_headers,
        json={"name": "key-auth-test"},
    )
    raw_key = r.json()["key"]

    # Use the key to call /me without a JWT
    r = client.get("/api/v1/auth/me", headers={"X-API-Key": raw_key})
    assert r.status_code == 200


def test_revoke_api_key(client, auth_headers):
    r = client.post(
        "/api/v1/keys",
        headers=auth_headers,
        json={"name": "revoke-test"},
    )
    raw_key = r.json()["key"]
    key_id = r.json()["id"]

    r = client.delete(f"/api/v1/keys/{key_id}", headers=auth_headers)
    assert r.status_code == 204

    # Revoked key no longer authenticates
    r = client.get("/api/v1/auth/me", headers={"X-API-Key": raw_key})
    assert r.status_code == 401


# ── Jobs ──────────────────────────────────────────────────────────────────────

def test_create_job_requires_auth(client):
    r = client.post(
        "/api/v1/jobs",
        files={"file": ("genome.fasta", b">seq\nATCG\n", "text/plain")},
    )
    assert r.status_code == 401


def test_create_job_returns_pending(client, auth_headers):
    r = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        files={"file": ("genome.fasta", b">seq\nATCGATCGATCG\n", "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["job_id"]
    assert body["phage_mode"] is False


def test_create_job_with_phage_mode(client, auth_headers):
    r = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        data={"phage_mode": "true"},
        files={"file": ("genome.fasta", b">seq\nATCG\n", "text/plain")},
    )
    assert r.status_code == 200
    assert r.json()["phage_mode"] is True


def test_list_jobs_returns_users_jobs(client, auth_headers):
    client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        files={"file": ("a.fasta", b">a\nATCG\n", "text/plain")},
    )
    r = client.get("/api/v1/jobs", headers=auth_headers)
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert len(jobs) >= 1


def test_get_job_status_other_user_403(client, auth_headers):
    # User A creates a job
    r = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        files={"file": ("x.fasta", b">x\nATCG\n", "text/plain")},
    )
    job_id = r.json()["job_id"]

    # User B tries to read it
    r2 = client.post(
        "/api/v1/auth/signup",
        json={"email": "user-b@example.com", "password": "correct-horse-battery"},
    )
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    r = client.get(f"/api/v1/jobs/{job_id}", headers=other_headers)
    assert r.status_code == 403


def test_get_unknown_job_404(client, auth_headers):
    r = client.get("/api/v1/jobs/does-not-exist", headers=auth_headers)
    assert r.status_code == 404


# ── Waitlist ──────────────────────────────────────────────────────────────────

def test_waitlist_accepts_email(client):
    r = client.post("/api/v1/waitlist", json={"email": "wait@example.com"})
    assert r.status_code == 201
    assert r.json()["status"] == "ok"


def test_waitlist_dedupes(client):
    client.post("/api/v1/waitlist", json={"email": "twice@example.com"})
    r = client.post("/api/v1/waitlist", json={"email": "twice@example.com"})
    assert r.status_code == 201
    assert r.json()["status"] == "already_registered"


# ── Cleanup ───────────────────────────────────────────────────────────────────

def teardown_module(_module):
    """Drop the temp SQLite file once all tests complete."""
    try:
        Path(_TMPDB.name).unlink()
    except FileNotFoundError:
        pass
