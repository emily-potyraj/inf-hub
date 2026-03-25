from dotenv import load_dotenv
load_dotenv()

from collections import defaultdict
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workload, ConfigVersion, AuditLog, TeamFunction
from app.auth import get_current_user
from app.routers import workloads as workloads_router, configs, team, auth_router
from app.routers.workloads import _to_row

app = FastAPI(title="inf-hub")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(workloads_router.router)
app.include_router(configs.router)
app.include_router(team.router)
app.include_router(auth_router.router)


@app.get("/")
def index(
    request: Request,
    hardware: str = None,
    framework: str = None,
    status: str = None,
    story_label: str = None,
    amd_ahead: bool = None,
    unassigned_pic: bool = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
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
    if unassigned_pic:
        q = q.filter(Workload.pic.is_(None))

    rows = [_to_row(w) for w in q.all()]
    if amd_ahead:
        rows = [r for r in rows if r.gap_pct is not None and r.gap_pct < 0]

    stale_threshold = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "workloads": rows,
        "user": user,
        "filters": {
            "hardware": hardware, "framework": framework,
            "status": status, "story_label": story_label,
            "amd_ahead": amd_ahead, "unassigned_pic": unassigned_pic,
        },
        "stale_threshold": stale_threshold,
    })


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
