import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import ConfigVersion, Workload
from app.auth import require_auth

router = APIRouter(tags=["configs"])

CONFIG_UPLOAD_DIR = "data/configs"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class ConfigUrlCreate(BaseModel):
    source_type: str = "url"
    url: str
    notes: Optional[str] = None


class ConfigVersionOut(BaseModel):
    id: int
    workload_id: int
    version_num: int
    source_type: str
    file_path: Optional[str]
    original_filename: Optional[str]
    url: Optional[str]
    uploaded_by: str
    uploaded_by_email: str
    notes: Optional[str]

    model_config = {"from_attributes": True}


def _next_version(workload_id: int, db: Session) -> int:
    result = db.query(func.max(ConfigVersion.version_num)).filter(
        ConfigVersion.workload_id == workload_id
    ).scalar()
    return (result or 0) + 1


@router.post("/workloads/{workload_id}/configs", response_model=ConfigVersionOut)
def add_config_url(
    workload_id: int,
    payload: ConfigUrlCreate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    if not db.get(Workload, workload_id):
        raise HTTPException(status_code=404, detail="Workload not found")
    version_num = _next_version(workload_id, db)
    cv = ConfigVersion(
        workload_id=workload_id,
        version_num=version_num,
        source_type="url",
        url=payload.url,
        notes=payload.notes,
        uploaded_by=user["name"],
        uploaded_by_email=user["email"],
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


@router.post("/workloads/{workload_id}/configs/upload", response_model=ConfigVersionOut)
async def upload_config_file(
    workload_id: int,
    file: UploadFile = File(...),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    if not db.get(Workload, workload_id):
        raise HTTPException(status_code=404, detail="Workload not found")
    version_num = _next_version(workload_id, db)
    dest_dir = os.path.join(CONFIG_UPLOAD_DIR, str(workload_id), str(version_num))
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file.filename)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")
    with open(dest_path, "wb") as f:
        f.write(content)

    cv = ConfigVersion(
        workload_id=workload_id,
        version_num=version_num,
        source_type="file",
        file_path=dest_path,
        original_filename=file.filename,
        notes=notes,
        uploaded_by=user["name"],
        uploaded_by_email=user["email"],
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


@router.get("/workloads/{workload_id}/configs", response_model=list[ConfigVersionOut])
def list_configs(workload_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ConfigVersion)
        .filter(ConfigVersion.workload_id == workload_id)
        .order_by(ConfigVersion.version_num.desc())
        .all()
    )


@router.get("/workloads/{workload_id}/configs/current", response_model=ConfigVersionOut)
def get_current_config(workload_id: int, db: Session = Depends(get_db)):
    cv = (
        db.query(ConfigVersion)
        .filter(ConfigVersion.workload_id == workload_id)
        .order_by(ConfigVersion.version_num.desc())
        .first()
    )
    if not cv:
        raise HTTPException(status_code=404, detail="No config versions found")
    return cv


@router.get("/workloads/{workload_id}/config/{version_num}", response_model=ConfigVersionOut)
def get_config_version(workload_id: int, version_num: int, db: Session = Depends(get_db)):
    cv = (
        db.query(ConfigVersion)
        .filter(
            ConfigVersion.workload_id == workload_id,
            ConfigVersion.version_num == version_num,
        )
        .first()
    )
    if not cv:
        raise HTTPException(status_code=404, detail="Config version not found")
    return cv


@router.get("/workloads/{workload_id}/configs/{version_num}/download")
def download_config(workload_id: int, version_num: int, db: Session = Depends(get_db)):
    cv = (
        db.query(ConfigVersion)
        .filter(
            ConfigVersion.workload_id == workload_id,
            ConfigVersion.version_num == version_num,
            ConfigVersion.source_type == "file",
        )
        .first()
    )
    if not cv or not cv.file_path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(cv.file_path, filename=cv.original_filename)
