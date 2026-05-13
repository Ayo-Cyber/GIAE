"""Mark stale PENDING/RUNNING jobs as CANCELLED.

Anything older than 10 minutes in PENDING or RUNNING is treated as stuck.
Run this before starting the stack to clear leftover jobs from earlier sessions.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make giae_api importable when run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from giae_api import database, models  # noqa: E402

STALE_AFTER = timedelta(minutes=10)


def main() -> int:
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    session = database.SessionLocal()
    try:
        stuck = (
            session.query(models.Job)
            .filter(models.Job.status.in_(["PENDING", "RUNNING"]))
            .all()
        )
        cancelled = 0
        for job in stuck:
            created = job.created_at
            if created is None:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created < cutoff:
                job.status = "CANCELLED"
                job.error_message = "Auto-cancelled by clean_stale_jobs (stuck > 10 min)"
                cancelled += 1
        session.commit()
        print(f"Cleaned up {cancelled} stale job(s).")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
