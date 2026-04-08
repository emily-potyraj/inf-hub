from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BenchmarkVersion, BenchmarkSubmission
from app.auth import get_current_user

router = APIRouter(prefix="/roadmap", tags=["roadmap"])
_templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Pydantic request bodies
# ---------------------------------------------------------------------------

class StatusUpdate(BaseModel):
    status: str


class NotesUpdate(BaseModel):
    notes: Optional[str] = None


class DatesUpdate(BaseModel):
    submission_date: Optional[str] = None
    publication_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Data builder (shared by GET /roadmap/data and GET /roadmap page route)
# ---------------------------------------------------------------------------

_TAB_LABEL_MAP = {
    "slt": "SLT",
    "agentperf": "AgentPerf",
}

def _tab_label(benchmark_version: str) -> str:
    """Derive a short tab label from the benchmark_version slug."""
    suffix = benchmark_version.rsplit("-", 1)[-1]
    return _TAB_LABEL_MAP.get(suffix, suffix)


def _build_data(db: Session) -> dict:
    versions = (
        db.query(BenchmarkVersion)
        .order_by(BenchmarkVersion.sort_order, BenchmarkVersion.benchmark_version)
        .all()
    )
    submissions = db.query(BenchmarkSubmission).all()

    # Index submissions by version
    by_version: dict[str, list] = {}
    for s in submissions:
        by_version.setdefault(s.benchmark_version, []).append(s)

    # Group versions by benchmark_group preserving order
    group_order: list[str] = []
    groups_map: dict[str, list] = {}
    for v in versions:
        g = v.benchmark_group
        if g not in groups_map:
            group_order.append(g)
            groups_map[g] = []
        groups_map[g].append(v)

    groups_out = []
    for g in group_order:
        versions_out = []
        for v in groups_map[g]:
            vsubs = by_version.get(v.benchmark_version, [])

            # Collect ordered unique chips and models
            chips_seen: list[str] = []
            models_seen: list[str] = []
            for s in vsubs:
                if s.chip not in chips_seen:
                    chips_seen.append(s.chip)
                if s.model not in models_seen:
                    models_seen.append(s.model)

            # Build cells: model → chip → [submissions]
            cells: dict[str, dict[str, list]] = {}
            for s in vsubs:
                cells.setdefault(s.model, {}).setdefault(s.chip, [])
                cells[s.model][s.chip].append({
                    "id": s.id,
                    "seqlen": s.seqlen,
                    "status": s.status,
                    "notes": s.notes,
                })

            # Sort seqlens within each cell consistently
            for model_cells in cells.values():
                for chip_list in model_cells.values():
                    chip_list.sort(key=lambda x: x["seqlen"])

            targeting_count = sum(1 for s in vsubs if s.status in ("tuning_wip", "submitted", "published"))
            total_count = len(vsubs)

            versions_out.append({
                "benchmark_version": v.benchmark_version,
                "display_name": _tab_label(v.benchmark_version),
                "is_active": bool(v.is_active),
                "submission_date": v.submission_date,
                "publication_date": v.publication_date,
                "chips": chips_seen,
                "models": models_seen,
                "cells": cells,
                "targeting_count": targeting_count,
                "total_count": total_count,
            })

        groups_out.append({
            "benchmark_group": g,
            "versions": versions_out,
        })

    return {"groups": groups_out}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/data")
def get_roadmap_data(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return _build_data(db)


@router.patch("/submissions/{submission_id}/status", response_class=HTMLResponse)
def patch_submission_status(
    submission_id: int,
    body: StatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    sub = db.get(BenchmarkSubmission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    sub.status = body.status
    sub.updated_at = datetime.now(timezone.utc)
    if user:
        sub.updated_by = user.get("name") or user.get("email")
    db.commit()
    db.refresh(sub)

    submission = {
        "id": sub.id,
        "seqlen": sub.seqlen,
        "status": sub.status,
        "notes": sub.notes,
    }
    return _templates.TemplateResponse(
        "partials/roadmap_status_row.html",
        {"request": request, "submission": submission},
    )


@router.patch("/submissions/{submission_id}/notes", response_class=HTMLResponse)
def patch_submission_notes(
    submission_id: int,
    body: NotesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    sub = db.get(BenchmarkSubmission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    sub.notes = body.notes
    sub.updated_at = datetime.now(timezone.utc)
    if user:
        sub.updated_by = user.get("name") or user.get("email")
    db.commit()
    db.refresh(sub)

    submission = {
        "id": sub.id,
        "notes": sub.notes,
    }
    return _templates.TemplateResponse(
        "partials/roadmap_notes_cell.html",
        {"request": request, "submission": submission},
    )


@router.patch("/versions/{benchmark_version}/dates", response_class=HTMLResponse)
def patch_version_dates(
    benchmark_version: str,
    body: DatesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    v = db.get(BenchmarkVersion, benchmark_version)
    if v is None:
        raise HTTPException(status_code=404, detail="Benchmark version not found")

    if body.submission_date is not None:
        v.submission_date = body.submission_date or None
    if body.publication_date is not None:
        v.publication_date = body.publication_date or None
    db.commit()
    db.refresh(v)

    version = {
        "benchmark_version": v.benchmark_version,
        "submission_date": v.submission_date,
        "publication_date": v.publication_date,
    }
    return _templates.TemplateResponse(
        "partials/roadmap_date_chips.html",
        {"request": request, "version": version},
    )
