from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workload, AuditLog
from app.schemas import WorkloadCreate, WorkloadRow, FieldUpdate
from app.auth import require_auth, get_current_user

router = APIRouter(prefix="/workloads", tags=["workloads"])

EDITABLE_FIELDS = {
    "status", "pic", "priority", "story_label", "accuracy_status",
    "nv_tps", "amd_tps", "dl_perf_published", "infmax_submitted",
    "nvmax_recipe_url", "ibdb_link", "notes",
}

FIELD_TYPES = {
    "status": "select",
    "accuracy_status": "select",
    "pic": "text",
    "priority": "number",
    "story_label": "text",
    "nv_tps": "number",
    "amd_tps": "number",
    "dl_perf_published": "text",
    "infmax_submitted": "text",
    "nvmax_recipe_url": "text",
    "ibdb_link": "text",
    "notes": "text",
}

STATUS_OPTIONS = ["not_started", "config_search", "accuracy_gate", "internal_review", "infmax_submitted", "published"]
ACCURACY_OPTIONS = ["not_run", "pass", "fail", "unknown"]

_templates = Jinja2Templates(directory="app/templates")


def _compute_gap(nv_tps, amd_tps):
    if nv_tps is not None and amd_tps is not None and amd_tps != 0:
        return (nv_tps - amd_tps) / amd_tps
    return None


def _to_row(w: Workload) -> WorkloadRow:
    d = {c.name: getattr(w, c.name) for c in w.__table__.columns}
    d["gap_pct"] = _compute_gap(w.nv_tps, w.amd_tps)
    if w.last_updated:
        d["last_updated"] = w.last_updated.isoformat()
    return WorkloadRow(**d)


@router.get("", response_model=list[WorkloadRow])
def list_workloads(
    hardware: Optional[str] = None,
    framework: Optional[str] = None,
    status: Optional[str] = None,
    story_label: Optional[str] = None,
    priority: Optional[int] = None,
    amd_ahead: Optional[bool] = None,
    unassigned_pic: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Workload)
    if hardware:
        q = q.filter(Workload.hardware == hardware)
    if framework:
        q = q.filter(Workload.framework == framework)
    if status:
        q = q.filter(Workload.status == status)
    if story_label:
        q = q.filter(Workload.story_label == story_label)
    if priority is not None:
        q = q.filter(Workload.priority == priority)
    if unassigned_pic:
        q = q.filter(Workload.pic.is_(None))
    rows = [_to_row(w) for w in q.all()]
    if amd_ahead:
        rows = [r for r in rows if r.gap_pct is not None and r.gap_pct < 0]
    return rows


@router.post("", response_model=None)
def create_workload(
    request: Request,
    payload: WorkloadCreate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    w = Workload(**payload.model_dump())
    db.add(w)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Workload already exists")
    db.refresh(w)
    row = _to_row(w)
    if request.headers.get("HX-Request"):
        from datetime import datetime, timezone, timedelta
        stale_threshold = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        return _templates.TemplateResponse(
            "partials/workload_row.html",
            {"request": request, "w": row, "user": user, "stale_threshold": stale_threshold},
        )
    return row


@router.get("/{workload_id}", response_model=WorkloadRow)
def get_workload(workload_id: int, db: Session = Depends(get_db)):
    w = db.get(Workload, workload_id)
    if not w:
        raise HTTPException(status_code=404, detail="Not found")
    return _to_row(w)


@router.patch("/{workload_id}/{field}")
def update_field(
    request: Request,
    workload_id: int,
    field: str,
    payload: FieldUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    if field not in EDITABLE_FIELDS:
        raise HTTPException(status_code=400, detail=f"Field '{field}' is not editable")
    w = db.get(Workload, workload_id)
    if not w:
        raise HTTPException(status_code=404, detail="Not found")
    old_value = getattr(w, field)
    # Audit log will be added in Task 5 — for now just update
    setattr(w, field, payload.value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(w)
    if request.headers.get("HX-Request"):
        from fastapi.responses import HTMLResponse
        display = str(payload.value) if payload.value is not None else "—"
        return HTMLResponse(
            f'<span class="editable-field" '
            f'hx-get="/workloads/{workload_id}/{field}/edit" '
            f'hx-trigger="click" hx-target="this" hx-swap="outerHTML">'
            f'{display}</span>'
        )
    return _to_row(w)


@router.get("/{workload_id}/{field}/edit")
def edit_field_widget(
    request: Request,
    workload_id: int,
    field: str,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    if field not in EDITABLE_FIELDS:
        raise HTTPException(status_code=400)
    w = db.get(Workload, workload_id)
    if not w:
        raise HTTPException(status_code=404)
    current = getattr(w, field)
    field_type = FIELD_TYPES.get(field, "text")

    if field_type == "select":
        options = STATUS_OPTIONS if field == "status" else ACCURACY_OPTIONS
        opts_html = "".join(
            f'<option value="{o}" {"selected" if o == current else ""}>{o}</option>'
            for o in options
        )
        html = (
            f'<select class="edit-input"'
            f' hx-patch="/workloads/{workload_id}/{field}"'
            f' hx-vals=\'js:{{"value": event.target.value}}\''
            f' hx-trigger="change"'
            f' hx-target="this"'
            f' hx-swap="outerHTML">{opts_html}</select>'
        )
    else:
        html = (
            f'<input class="edit-input" type="{field_type}" value="{current or ""}"'
            f' hx-patch="/workloads/{workload_id}/{field}"'
            f' hx-vals=\'js:{{"value": event.target.value}}\''
            f' hx-trigger="blur, keyup[key==\'Enter\']"'
            f' hx-target="this"'
            f' hx-swap="outerHTML"'
            f' autofocus>'
        )
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


@router.get("/{workload_id}/audit")
def get_audit_trail(workload_id: int, db: Session = Depends(get_db)):
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.workload_id == workload_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    return [
        {
            "field_name": l.field_name,
            "old_value": l.old_value,
            "new_value": l.new_value,
            "user_name": l.user_name,
            "user_email": l.user_email,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        }
        for l in logs
    ]
