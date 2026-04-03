from datetime import datetime, timezone, date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Request as RequestModel
from app.schemas import RequestCreate, RequestUpdate
from app.auth import require_auth, get_current_user

router = APIRouter(prefix="/requests", tags=["requests"])
_templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def list_requests(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    all_requests = (
        db.query(RequestModel)
        .order_by(RequestModel.created_at.desc())
        .all()
    )

    new = [r for r in all_requests if r.status == "new"]
    in_progress = [r for r in all_requests if r.status == "in_progress"]
    completed = [r for r in all_requests if r.status == "completed"]

    filter_options = {
        "model": sorted(set(r.model for r in all_requests if r.model)),
        "hardware": sorted(set(r.hardware for r in all_requests if r.hardware)),
        "framework": sorted(set(r.framework for r in all_requests if r.framework)),
        "precision": sorted(set(r.precision for r in all_requests if r.precision)),
        "scenario": sorted(set(r.scenario for r in all_requests if r.scenario)),
        "seqlens": sorted(set(r.seqlens for r in all_requests if r.seqlens)),
    }

    return _templates.TemplateResponse("requests.html", {
        "request": request,
        "new": new,
        "in_progress": in_progress,
        "completed": completed,
        "filter_options": filter_options,
        "user": user,
    })


@router.post("")
def create_request(
    body: RequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    submitted_by = body.submitted_by
    if user is not None:
        submitted_by = user["name"]

    new_request = RequestModel(
        model=body.model,
        hardware=body.hardware,
        framework=body.framework,
        precision=body.precision,
        scenario=body.scenario,
        seqlens=body.seqlens,
        notes=body.notes,
        submitted_by=submitted_by,
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return {"id": new_request.id}


@router.patch("/{request_id}")
def update_request(
    request_id: int,
    body: RequestUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    req = db.get(RequestModel, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")

    if body.status is not None:
        req.status = body.status
    if body.pic is not None:
        req.pic = body.pic
    if body.eta is not None:
        req.eta = datetime.fromisoformat(body.eta) if body.eta else None

    req.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}
