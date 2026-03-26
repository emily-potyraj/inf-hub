from dotenv import load_dotenv
load_dotenv()

import re
from collections import defaultdict, OrderedDict
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.database import get_db
from app.models import Workload, ConfigVersion, AuditLog, TeamFunction
from app.auth import get_current_user
from app.routers import workloads as workloads_router, configs, team, auth_router
from app.routers import breadth_studies as breadth_studies_router
from app.routers import devzone as devzone_router
from app.routers.workloads import _to_row

app = FastAPI(title="inf-hub")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(workloads_router.router)
app.include_router(configs.router)
app.include_router(team.router)
app.include_router(auth_router.router)
app.include_router(breadth_studies_router.router)
app.include_router(devzone_router.router)


def _group_id(key: tuple) -> str:
    """Convert a group key tuple to a URL-safe HTML id string."""
    joined = "-".join(str(k) for k in key if k)
    return re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")


@app.get("/")
def index(
    request: Request,
    hardware: str = None,
    framework: str = None,
    status: str = None,
    story_label: str = None,
    amd_ahead: bool = None,
    unassigned_pic: bool = None,
    model: str = None,
    precision: str = None,
    scenario: str = None,
    work_type: str = None,
    pic: str = None,
    q: str = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Fetch all workloads (unfiltered for filter_options)
    all_workloads = db.query(Workload).all()
    all_rows = [_to_row(w) for w in all_workloads]

    # Build filter options from full unfiltered dataset
    filter_options = {
        "model": sorted(set(r.model for r in all_rows if r.model)),
        "hardware": sorted(set(r.hardware for r in all_rows if r.hardware)),
        "framework": sorted(set(r.framework for r in all_rows if r.framework)),
        "precision": sorted(set(r.precision for r in all_rows if r.precision)),
        "scenario": sorted(set(r.scenario for r in all_rows if r.scenario)),
    }

    # Get pic options from TeamFunction
    team_members = db.query(TeamFunction).all()
    pic_set = set()
    for tf in team_members:
        if tf.owner:
            pic_set.add(tf.owner)
        if tf.backup:
            pic_set.add(tf.backup)
    pic_options = sorted(pic_set)

    # Apply filters
    rows = all_rows
    if hardware:
        rows = [r for r in rows if r.hardware == hardware]
    if framework:
        rows = [r for r in rows if r.framework == framework]
    if status:
        rows = [r for r in rows if r.status == status]
    if story_label:
        rows = [r for r in rows if r.story_label == story_label]
    if model:
        rows = [r for r in rows if r.model == model]
    if precision:
        rows = [r for r in rows if r.precision == precision]
    if scenario:
        rows = [r for r in rows if r.scenario == scenario]
    if work_type:
        rows = [r for r in rows if r.work_type == work_type]
    if pic:
        rows = [r for r in rows if r.pic == pic]
    if unassigned_pic:
        rows = [r for r in rows if r.pic is None]
    if amd_ahead:
        rows = [r for r in rows if r.gap_pct is not None and r.gap_pct < 0]
    if q:
        q_lower = q.lower()
        rows = [
            r for r in rows
            if any(
                q_lower in str(v or "").lower()
                for v in [r.model, r.hardware, r.framework, r.precision,
                          r.scenario, r.seqlens, r.pic, r.notes]
            )
        ]

    # Build groups: OrderedDict keyed by (model, hardware, framework, precision, scenario)
    # Sort rows first: by priority asc (None last), then identity fields alphabetically
    def sort_key(r):
        pri = r.priority if r.priority is not None else 9999
        return (pri, r.model or "", r.hardware or "", r.framework or "",
                r.precision or "", r.scenario or "")

    rows_sorted = sorted(rows, key=sort_key)

    groups: OrderedDict = OrderedDict()
    for r in rows_sorted:
        key = (r.model, r.hardware, r.framework, r.precision, r.scenario)
        if key not in groups:
            groups[key] = []
        groups[key].append(r)

    # Generate group_ids
    group_ids = {key: _group_id(key) for key in groups}

    # Compute stats from filtered rows
    stats = {
        "total": len(rows),
        "submitted": sum(1 for r in rows if r.infmax_submitted == "yes"),
        "in_review": sum(1 for r in rows if r.status == "internal_review"),
        "config_search": sum(1 for r in rows if r.status == "config_search"),
        "not_started": sum(1 for r in rows if r.status == "not_started"),
    }

    stale_threshold = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    config_subq = (
        db.query(ConfigVersion.workload_id, func.max(ConfigVersion.version_num).label("max_v"))
        .group_by(ConfigVersion.workload_id)
        .all()
    )
    latest_configs = {row.workload_id: row.max_v for row in config_subq}

    return templates.TemplateResponse("index.html", {
        "request": request,
        "workloads": rows,
        "groups": groups,
        "group_ids": group_ids,
        "filter_options": filter_options,
        "pic_options": pic_options,
        "user": user,
        "filters": {
            "hardware": hardware,
            "framework": framework,
            "status": status,
            "story_label": story_label,
            "amd_ahead": amd_ahead,
            "unassigned_pic": unassigned_pic,
            "model": model,
            "precision": precision,
            "scenario": scenario,
            "work_type": work_type,
            "pic": pic,
            "q": q,
        },
        "stale_threshold": stale_threshold,
        "latest_configs": latest_configs,
        "stats": stats,
    })


@app.get("/add")
def add_page(
    request: Request,
    user=Depends(get_current_user),
):
    return templates.TemplateResponse("add.html", {"request": request, "user": user})


@app.get("/overview")
def overview_page(
    request: Request,
    user=Depends(get_current_user),
):
    return templates.TemplateResponse("overview.html", {"request": request, "user": user})


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
