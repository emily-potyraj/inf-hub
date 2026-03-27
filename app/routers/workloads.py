from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workload, AuditLog, TeamFunction
from app.schemas import WorkloadCreate, WorkloadRow, FieldUpdate
from app.auth import require_auth, get_current_user
from app import audit as audit_service

router = APIRouter(prefix="/workloads", tags=["workloads"])

EDITABLE_FIELDS = {
    "status", "pic", "priority", "story_label", "accuracy_status",
    "nv_tps", "amd_tps", "dl_perf_published", "infmax_submitted",
    "nvmax_recipe_url", "ibdb_link", "notes", "work_type", "seqlens",
}

FIELD_TYPES = {
    "status": "select",
    "accuracy_status": "select",
    "pic": "select",
    "priority": "select",
    "story_label": "text",
    "nv_tps": "number",
    "amd_tps": "number",
    "dl_perf_published": "text",
    "infmax_submitted": "select",
    "nvmax_recipe_url": "text",
    "ibdb_link": "text",
    "notes": "textarea",
    "work_type": "select",
    "seqlens": "text",
}

STATUS_OPTIONS = ["not_started", "config_search", "accuracy_gate", "internal_review", "infmax_submitted", "published"]
ACCURACY_OPTIONS = ["not_run", "pass", "fail", "unknown"]
WORK_TYPE_OPTIONS = ["tune", "breadth_test"]
PRIORITY_OPTIONS = ["1", "2", "3", "4", "5", ""]
INFMAX_OPTIONS = ["", "yes", "staged"]

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
    d["amd_tps_source"] = w.amd_tps_source
    d["amd_tps_sentinel_value"] = w.amd_tps_sentinel_value
    d["amd_tps_synced_at"] = w.amd_tps_synced_at.isoformat() if w.amd_tps_synced_at else None
    d["sentinel_threat_level"] = w.sentinel_threat_level
    d["sentinel_summary"] = w.sentinel_summary
    d["sentinel_image_url"] = w.sentinel_image_url
    d["sentinel_synced_at"] = w.sentinel_synced_at.isoformat() if w.sentinel_synced_at else None
    return WorkloadRow(**d)


def _field_cell_html(workload_id: int, field: str, value) -> str:
    """Return the styled display span for a field after a PATCH update."""
    base = (
        f'<span class="editable-field" '
        f'hx-get="/workloads/{workload_id}/{field}/edit" '
        f'hx-trigger="click" hx-target="this" hx-swap="outerHTML">'
    )
    end = '</span>'

    if field == "status":
        if value == "published":
            inner = f'<span class="badge badge-green">{value}</span>'
        elif value == "accuracy_gate":
            inner = f'<span class="badge badge-amber">{value}</span>'
        elif value == "not_started" or not value:
            inner = f'<span class="badge badge-muted">{value or "not_started"}</span>'
        else:
            inner = f'<span class="badge badge-blue">{value}</span>'
        return base + inner + end

    if field == "work_type":
        if value == "breadth_test":
            inner = f'<span class="badge badge-blue">{value}</span>'
        elif value:
            inner = f'<span class="badge badge-muted">{value}</span>'
        else:
            inner = '<span style="color:var(--text-label)">—</span>'
        return base + inner + end

    if field == "pic":
        if value:
            inner = f'<span>{value}</span>'
        else:
            inner = '<span style="color:var(--amber);font-size:0.78rem">⚠ unassigned</span>'
        return base + inner + end

    if field == "priority":
        if value:
            p = str(value)
            badge_cls = {
                "1": "badge-p1",
                "2": "badge-p2",
                "3": "badge-p3",
                "4": "badge-p4",
                "5": "badge-p5",
            }.get(p, "badge-muted")
            inner = f'<span class="badge {badge_cls}">P{p}</span>'
        else:
            inner = '<span style="color:var(--text-label)">—</span>'
        return base + inner + end

    if field == "infmax_submitted":
        if value:
            inner = f'<span class="badge badge-green">✓ {value}</span>'
        else:
            inner = '<span style="color:var(--text-label)">—</span>'
        return base + inner + end

    # seqlens and other text fields
    if value is not None and str(value).strip():
        inner = f'<span style="color:var(--text-muted)">{value}</span>'
    else:
        inner = '<span style="color:var(--text-label)">—</span>'
    return base + inner + end


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
        from sqlalchemy import func
        from app.models import ConfigVersion
        stale_threshold = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        config_subq = (
            db.query(ConfigVersion.workload_id, func.max(ConfigVersion.version_num).label("max_v"))
            .group_by(ConfigVersion.workload_id)
            .all()
        )
        latest_configs = {r.workload_id: r.max_v for r in config_subq}
        return _templates.TemplateResponse(
            "partials/workload_row.html",
            {"request": request, "w": row, "user": user, "stale_threshold": stale_threshold,
             "latest_configs": latest_configs},
        )
    return row


@router.get("/{workload_id}/expand")
async def expand_workload(
    request: Request,
    workload_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    w = db.get(Workload, workload_id)
    if not w:
        raise HTTPException(status_code=404, detail="Not found")
    row = _to_row(w)
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.workload_id == workload_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(5)
        .all()
    )
    return _templates.TemplateResponse(
        "partials/workload_row_expand.html",
        {"request": request, "w": row, "audit": audit, "user": user},
    )


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
    audit_service.write_audit_log(
        db, workload_id, user["name"], user["email"], field, old_value, payload.value
    )
    setattr(w, field, payload.value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(w)
    if request.headers.get("HX-Request"):
        return HTMLResponse(_field_cell_html(workload_id, field, payload.value))
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
        if field == "status":
            options = STATUS_OPTIONS
        elif field == "work_type":
            options = WORK_TYPE_OPTIONS
        elif field == "accuracy_status":
            options = ACCURACY_OPTIONS
        elif field == "priority":
            options = PRIORITY_OPTIONS
            current_str = str(current) if current is not None else ""
            opts_html = "".join(
                f'<option value="{o}" {"selected" if o == current_str else ""}>{o if o else "—"}</option>'
                for o in options
            )
            html = (
                f'<select class="edit-input"'
                f' hx-patch="/workloads/{workload_id}/{field}"'
                f' hx-vals=\'js:{{"value": event.target.value || null}}\''
                f' hx-trigger="change"'
                f' hx-target="this"'
                f' hx-swap="outerHTML">{opts_html}</select>'
            )
            return HTMLResponse(html)
        elif field == "infmax_submitted":
            options = INFMAX_OPTIONS
            opts_html = "".join(
                f'<option value="{o}" {"selected" if o == (current or "") else ""}>{o if o else "—"}</option>'
                for o in options
            )
            html = (
                f'<select class="edit-input"'
                f' hx-patch="/workloads/{workload_id}/{field}"'
                f' hx-vals=\'js:{{"value": event.target.value || null}}\''
                f' hx-trigger="change"'
                f' hx-target="this"'
                f' hx-swap="outerHTML">{opts_html}</select>'
            )
            return HTMLResponse(html)
        elif field == "pic":
            # Query team members for pic options
            team_members = db.query(TeamFunction).all()
            pic_set = set()
            for tf in team_members:
                if tf.owner:
                    pic_set.add(tf.owner)
                if tf.backup:
                    pic_set.add(tf.backup)
            pic_list = sorted(pic_set)
            opts_html = f'<option value="" {"selected" if not current else ""}>— unassigned</option>'
            opts_html += "".join(
                f'<option value="{p}" {"selected" if p == current else ""}>{p}</option>'
                for p in pic_list
            )
            html = (
                f'<select class="edit-input"'
                f' hx-patch="/workloads/{workload_id}/{field}"'
                f' hx-vals=\'js:{{"value": event.target.value || null}}\''
                f' hx-trigger="change"'
                f' hx-target="this"'
                f' hx-swap="outerHTML">{opts_html}</select>'
            )
            return HTMLResponse(html)
        else:
            options = ACCURACY_OPTIONS

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
    elif field_type == "textarea":
        escaped = (current or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = (
            f'<textarea class="edit-input" rows="3"'
            f' hx-patch="/workloads/{workload_id}/{field}"'
            f' hx-vals=\'js:{{"value": event.target.value}}\''
            f' hx-trigger="blur"'
            f' hx-target="this"'
            f' hx-swap="outerHTML"'
            f' autofocus>{escaped}</textarea>'
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
