from dotenv import load_dotenv
load_dotenv()

import json as _json
import re
import os
from collections import defaultdict, OrderedDict
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.database import get_db
from app.models import Workload, ConfigVersion, AuditLog, TeamFunction, DevzoneScene, DevzoneCurve
from app.auth import get_current_user
from app.routers import workloads as workloads_router, configs, team, auth_router
from app.routers import breadth_studies as breadth_studies_router
from app.routers import devzone as devzone_router
from app.routers import sentinel as sentinel_router
from app.routers import requests as requests_router
from app.routers import ibdb as ibdb_router
from app.routers import comments as comments_router
from app.routers import roadmap as roadmap_router
from app.routers.roadmap import _build_data
from app.routers.workloads import _to_row

app = FastAPI(title="inf-hub")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")
# TODO: set to False once Entra SSO is configured (gated by bool(user) per-request)
templates.env.globals["editable"] = True

@app.get("/roadmap")
def roadmap_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    data = _build_data(db)
    return templates.TemplateResponse("roadmap.html", {"request": request, "user": user, "data": data})


@app.get("/workloads/{workload_id}")
def workload_detail(
    request: Request,
    workload_id: int,
    config: int = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    w = db.get(Workload, workload_id)
    if not w:
        from fastapi.responses import Response
        return Response(status_code=404, content="Not found")
    row = _to_row(w)
    wl_configs = (
        db.query(ConfigVersion)
        .filter(ConfigVersion.workload_id == workload_id)
        .order_by(ConfigVersion.version_num.desc())
        .all()
    )
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.workload_id == workload_id)
        .order_by(AuditLog.timestamp.desc())
        .all()
    )
    return templates.TemplateResponse("workload_detail.html", {
        "request": request, "w": row, "configs": wl_configs,
        "audit": audit, "user": user, "highlight_config": config,
        "workload_id": workload_id,
    })


app.include_router(workloads_router.router)
app.include_router(configs.router)
app.include_router(team.router)
app.include_router(auth_router.router)
app.include_router(breadth_studies_router.router)
app.include_router(devzone_router.router)
app.include_router(sentinel_router.router)
app.include_router(requests_router.router)
app.include_router(ibdb_router.router)
app.include_router(comments_router.router)
app.include_router(roadmap_router.router)

_scheduler = BackgroundScheduler(daemon=True)


def _run_daily_sentinel_sync() -> None:
    """Called by APScheduler in a background thread."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        sentinel_router.sync_sentinel(db)
    except Exception as exc:
        print(f"[sentinel] daily sync error: {exc}")
    finally:
        db.close()


def _run_ibdb_sync() -> None:
    """Called by APScheduler every 5 minutes."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        ibdb_router.sync_ibdb(db)
    except Exception as exc:
        print(f"[ibdb] scheduled sync error: {exc}")
    finally:
        db.close()


@app.on_event("startup")
def start_sentinel_scheduler() -> None:
    if not _scheduler.running:
        hour = int(os.getenv("SENTINEL_SYNC_HOUR", "6"))
        _scheduler.add_job(_run_daily_sentinel_sync, "cron", hour=hour, minute=0)
        _scheduler.add_job(_run_ibdb_sync, "interval", minutes=5)
        _scheduler.start()


@app.on_event("shutdown")
def stop_sentinel_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


_CURVE_COLORS = [
    "#76b900", "#00b4d8", "#fbbf24", "#f87171",
    "#a78bfa", "#34d399", "#fb923c", "#e879f9",
]

def _build_plotly_traces(curves):
    traces = []
    for i, c in enumerate(curves):
        try:
            points = _json.loads(c.points)
        except (ValueError, TypeError):
            points = []
        color = c.color or _CURVE_COLORS[i % len(_CURVE_COLORS)]
        traces.append({
            "name": c.label,
            "x": [p["x"] for p in points],
            "y": [p["y"] for p in points],
            "mode": "markers+lines",
            "line": {"color": color, "width": 3},
            "marker": {"color": color, "size": 8},
            "hovertemplate": "%{text}<extra></extra>",
            "text": [
                f"<b>{c.label}</b><br>Concurrency: {p.get('concurrency', '?')}"
                f"<br>Date: {p.get('date', '?')}"
                for p in points
            ],
        })
    return traces


def _group_id(key: tuple) -> str:
    """Convert a group key tuple to a URL-safe HTML id string."""
    joined = "-".join(str(k) for k in key if k)
    return re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")


@app.get("/")
def index(
    request: Request,
    model: str = None,
    hardware: str = None,
    status: str = None,
    pic: str = None,
    q: str = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    all_workloads = db.query(Workload).all()
    all_rows = [_to_row(w) for w in all_workloads]

    filter_options = {
        "model": sorted(set(r.model for r in all_rows if r.model)),
        "hardware": sorted(set(r.hardware for r in all_rows if r.hardware)),
        "framework": sorted(set(r.framework for r in all_rows if r.framework)),
        "precision": sorted(set(r.precision for r in all_rows if r.precision)),
        "scenario": sorted(set(r.scenario for r in all_rows if r.scenario)),
        "seqlens": sorted(set(r.seqlens for r in all_rows if r.seqlens)),
        "pic": sorted(set(r.pic for r in all_rows if r.pic)),
    }

    # Apply filters
    rows = all_rows
    if model:
        rows = [r for r in rows if r.model == model]
    if hardware:
        rows = [r for r in rows if r.hardware == hardware]
    if status:
        rows = [r for r in rows if r.status == status]
    if pic:
        rows = [r for r in rows if r.pic == pic]
    if q:
        q_lower = q.lower()
        rows = [r for r in rows if any(
            q_lower in str(v or "").lower()
            for v in [r.model, r.hardware, r.framework, r.precision, r.scenario, r.seqlens, r.pic, r.notes]
        )]

    # Sort: priority asc (None last), then model → hardware → seqlens → precision → scenario → framework
    rows_sorted = sorted(rows, key=lambda r: (
        r.priority if r.priority is not None else 9999,
        r.model or "", r.hardware or "", r.seqlens or "", r.precision or "", r.scenario or "", r.framework or ""
    ))

    # Build tree: model → hardware (chip) → seqlens → precision → [rows]
    tree: OrderedDict = OrderedDict()
    for r in rows_sorted:
        m = r.model or "Unknown"
        hw = r.hardware or "?"
        sl = r.seqlens or "—"
        prec = r.precision or "?"
        if m not in tree:
            tree[m] = OrderedDict()
        if hw not in tree[m]:
            tree[m][hw] = OrderedDict()
        if sl not in tree[m][hw]:
            tree[m][hw][sl] = OrderedDict()
        if prec not in tree[m][hw][sl]:
            tree[m][hw][sl][prec] = []
        tree[m][hw][sl][prec].append(r)

    # Serialize all rows as JSON for client-side matrix + export
    rows_json = _json.dumps([{
        "id": r.id, "model": r.model, "hardware": r.hardware,
        "framework": r.framework, "precision": r.precision,
        "scenario": r.scenario, "seqlens": r.seqlens,
        "status": r.status, "pic": r.pic, "priority": r.priority,
        "nv_tps": r.nv_tps, "amd_tps": r.amd_tps, "gap_pct": r.gap_pct,
        "notes": r.notes, "last_run_date": r.last_run_date,
        "ibdb_latest_run_at": r.ibdb_latest_run_at,
        "ibdb_synced_at": r.ibdb_synced_at,
        "s_record_id": r.s_record_id,
        "s_study_id":  r.s_study_id,
    } for r in rows_sorted])

    stats = {
        "total": len(rows),
        "published": sum(1 for r in rows if r.status == "published"),
        "in_flight": sum(1 for r in rows if r.status in ("internal_review", "accuracy_gate", "config_search")),
        "not_started": sum(1 for r in rows if r.status == "not_started"),
        "amd_ahead": sum(1 for r in rows if r.gap_pct is not None and r.gap_pct < 0),
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "tree": tree,
        "filter_options": filter_options,
        "filters": {"model": model, "hardware": hardware, "status": status, "pic": pic, "q": q},
        "stats": stats,
        "rows_json": rows_json,
        "user": user,
        "editable": True,
    })


@app.get("/add")
def add_page(
    request: Request,
    user=Depends(get_current_user),
):
    return templates.TemplateResponse("add.html", {"request": request, "user": user, "editable": True})


@app.get("/overview")
def overview_page(
    request: Request,
    user=Depends(get_current_user),
):
    return templates.TemplateResponse("overview.html", {"request": request, "user": user})


@app.get("/devzone/compare")
def devzone_compare_page(
    request: Request,
    a: str = None,
    b: str = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    scene_a = db.get(DevzoneScene, a) if a else None
    scene_b = db.get(DevzoneScene, b) if b else None

    def _traces(scene_id):
        if not scene_id:
            return "[]"
        cs = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
        return _json.dumps(_build_plotly_traces(cs))

    all_scenes = db.query(DevzoneScene).order_by(DevzoneScene.created_at.desc()).all()

    return templates.TemplateResponse("devzone_compare.html", {
        "request": request,
        "user": user,
        "editable": True,
        "scene_a": scene_a,
        "scene_b": scene_b,
        "traces_a": _traces(a),
        "traces_b": _traces(b),
        "all_scenes": all_scenes,
    })


@app.get("/devzone")
def devzone_page(
    request: Request,
    user=Depends(get_current_user),
):
    return templates.TemplateResponse("devzone.html", {
        "request": request,
        "user": user,
    })


@app.get("/team")
def team_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    functions = db.query(TeamFunction).all()
    workloads = db.query(Workload).order_by(Workload.pic).all()
    by_pic = defaultdict(list)
    unassigned = []
    for w in workloads:
        row = _to_row(w)
        if w.pic:
            by_pic[w.pic].append(row)
        else:
            unassigned.append(row)
    return templates.TemplateResponse("team.html", {
        "request": request, "functions": functions,
        "by_pic": dict(by_pic), "unassigned": unassigned, "user": user,
    })
