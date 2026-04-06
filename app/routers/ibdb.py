"""IBDB sync router.

POST /ibdb/sync  — trigger immediate sync (auth required)
GET  /ibdb/status — return last sync result from log file
"""
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.models import Workload
from app import ibdb_client

router = APIRouter(prefix="/ibdb", tags=["ibdb"])

SYNC_LOG_PATH = os.getenv("IBDB_SYNC_LOG_PATH", "data/ibdb_sync_log.json")


def _write_log(result: dict) -> None:
    log_dir = os.path.dirname(SYNC_LOG_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    with open(SYNC_LOG_PATH, "w") as f:
        json.dump(result, f, indent=2)


def sync_ibdb(db: Session) -> dict:
    """Check all workloads against IBDB. Safe to call even if IBDB is unreachable."""
    token = os.getenv("IBDB_AUTH_TOKEN", "")
    workloads = db.query(Workload).all()
    now = datetime.now(timezone.utc)
    synced = 0
    with_data = 0

    for w in workloads:
        latest_run_at = ibdb_client.check_workload(
            model=w.model,
            hardware=w.hardware,
            framework=w.framework,
            seqlens=w.seqlens or "",
            token=token,
        )
        w.ibdb_synced_at = now
        if latest_run_at is not None:
            w.ibdb_latest_run_at = latest_run_at
            with_data += 1
        synced += 1

    db.commit()

    result = {
        "timestamp": now.isoformat(),
        "synced": synced,
        "with_data": with_data,
    }
    _write_log(result)
    return result


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db), user=Depends(require_auth)):
    return sync_ibdb(db)


@router.get("/status")
def get_status():
    if os.path.exists(SYNC_LOG_PATH):
        with open(SYNC_LOG_PATH) as f:
            return json.load(f)
    return {"timestamp": None, "synced": 0, "with_data": 0}
