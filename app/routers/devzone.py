from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DevzoneScene, DevzoneCurve
from app.schemas import DevzoneSceneCreate
from app.auth import require_auth
from app.devzone_parser import parse_ibdb_export, CURVE_COLORS


class _SceneRename(BaseModel):
    name: str

router = APIRouter(prefix="/devzone", tags=["devzone"])


def _now():
    return datetime.now(timezone.utc)


def _scene_row(scene: DevzoneScene, curve_count: int = 0) -> dict:
    return {
        "id": scene.id,
        "name": scene.name,
        "model": scene.model,
        "seqlen": scene.seqlen,
        "created_by": scene.created_by,
        "created_by_email": scene.created_by_email,
        "created_at": scene.created_at.isoformat() if scene.created_at else None,
        "is_published": scene.is_published or 0,
        "published_at": scene.published_at.isoformat() if scene.published_at else None,
        "curve_count": curve_count,
    }


def _curve_row(curve: DevzoneCurve) -> dict:
    return {
        "id": curve.id,
        "scene_id": curve.scene_id,
        "label": curve.label,
        "hardware": curve.hardware,
        "framework": curve.framework,
        "precision": curve.precision,
        "color": curve.color,
        "ibdb_source": curve.ibdb_source,
        "uploaded_by": curve.uploaded_by,
        "uploaded_at": curve.uploaded_at.isoformat() if curve.uploaded_at else None,
    }


# --- Scenes ---

@router.post("/scenes")
def create_scene(
    payload: DevzoneSceneCreate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = DevzoneScene(
        id=str(uuid.uuid4()),
        name=payload.name,
        model=payload.model,
        seqlen=payload.seqlen,
        created_by=user.get("name"),
        created_by_email=user.get("email"),
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return _scene_row(scene)


@router.get("/scenes")
def list_scenes(db: Session = Depends(get_db)):
    scenes = db.query(DevzoneScene).order_by(DevzoneScene.created_at.desc()).all()
    counts = (
        db.query(DevzoneCurve.scene_id, func.count(DevzoneCurve.id).label("cnt"))
        .group_by(DevzoneCurve.scene_id)
        .all()
    )
    count_map = {row.scene_id: row.cnt for row in counts}
    return [_scene_row(s, count_map.get(s.id, 0)) for s in scenes]


@router.patch("/scenes/{scene_id}/name")
def rename_scene(
    scene_id: str,
    payload: _SceneRename,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    scene.name = payload.name
    db.commit()
    db.refresh(scene)
    return _scene_row(scene)


@router.delete("/scenes/{scene_id}")
def delete_scene(
    scene_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    if scene.created_by_email and scene.created_by_email != user.get("email"):
        raise HTTPException(status_code=403, detail="Only the creator can delete this scene")
    db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).delete()
    db.delete(scene)
    db.commit()
    return {"deleted": scene_id}


@router.patch("/scenes/{scene_id}/publish")
def publish_scene(
    scene_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    scene.is_published = 1
    scene.published_at = _now()
    db.commit()
    db.refresh(scene)
    return _scene_row(scene)


@router.get("/scenes/{scene_id}/export")
def export_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    curves = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
    return {
        "scene_name": scene.name,
        "model": scene.model,
        "seqlen": scene.seqlen,
        "exported_at": _now().isoformat(),
        "curves": [
            {
                "label": c.label,
                "hardware": c.hardware,
                "framework": c.framework,
                "precision": c.precision,
                "ibdb_source": c.ibdb_source,
                "points": json.loads(c.points),
            }
            for c in curves
        ],
    }


# --- Curves ---

@router.post("/scenes/{scene_id}/curves/preview")
async def preview_curves(
    scene_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    html_content = (await file.read()).decode("utf-8", errors="replace")
    parsed = parse_ibdb_export(html_content)

    # Build set of existing (hardware, framework, precision) for duplicate detection
    existing = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
    existing_sigs = {
        (c.hardware, c.framework, c.precision) for c in existing
    }

    result = []
    for series in parsed:
        sig = (series["hardware"], series["framework"], series["precision"])
        result.append({
            "label": series["label"],
            "hardware": series["hardware"],
            "framework": series["framework"],
            "precision": series["precision"],
            "point_count": len(series["points"]),
            "duplicate": sig in existing_sigs,
        })
    return result


@router.post("/scenes/{scene_id}/curves")
async def add_curves(
    scene_id: str,
    file: UploadFile = File(...),
    selected_labels: str = Form(...),   # JSON array of label strings
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    try:
        labels_to_add = set(json.loads(selected_labels))
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=422, detail="selected_labels must be a JSON array")

    html_content = (await file.read()).decode("utf-8", errors="replace")
    parsed = parse_ibdb_export(html_content)

    existing_count = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).count()

    existing_labels = {
        c.label for c in db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
    }

    added = []
    for i, series in enumerate(parsed):
        if series["label"] not in labels_to_add:
            continue

        # Check for duplicate label and suffix with date if needed
        label = series["label"]
        if label in existing_labels:
            # Append date from first point's metadata if available
            date = series["points"][0].get("date", "") if series["points"] else ""
            label = f"{label} ({date})" if date else f"{label} (2)"
        existing_labels.add(label)  # keep current for subsequent iterations

        color_idx = (existing_count + len(added)) % len(CURVE_COLORS)
        curve = DevzoneCurve(
            id=str(uuid.uuid4()),
            scene_id=scene_id,
            label=label,
            hardware=series["hardware"],
            framework=series["framework"],
            precision=series["precision"],
            color=CURVE_COLORS[color_idx],
            ibdb_source=file.filename,
            uploaded_by=user.get("name"),
            points=json.dumps(series["points"]),
        )
        db.add(curve)
        added.append(curve)

    db.commit()
    for c in added:
        db.refresh(c)
    # Return all curves for this scene (not just the newly added ones)
    all_curves = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
    return [_curve_row(c) for c in all_curves]


@router.delete("/curves/{curve_id}")
def delete_curve(
    curve_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    curve = db.get(DevzoneCurve, curve_id)
    if not curve:
        raise HTTPException(status_code=404, detail="Curve not found")
    db.delete(curve)
    db.commit()
    return {"deleted": curve_id}
