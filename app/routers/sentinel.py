import json
import os
import re
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth import require_auth, get_current_user
from app.database import get_db
from app.models import AuditLog, Workload

router = APIRouter(prefix="/sentinel", tags=["sentinel"])
templates = Jinja2Templates(directory="app/templates")

MAPPINGS_PATH = os.getenv("SENTINEL_MAPPINGS_PATH", "data/sentinel_mappings.json")
SYNC_LOG_PATH = os.getenv("SENTINEL_SYNC_LOG_PATH", "data/sentinel_sync_log.json")


def _load_mappings() -> dict:
    if not os.path.exists(MAPPINGS_PATH):
        return {"models": {}, "hardware": {}}
    with open(MAPPINGS_PATH) as f:
        return json.load(f)


def _normalize_seqlen(s: str) -> str:
    """'8K / 1K' -> '8k/1k'"""
    return s.replace(" ", "").lower()


def _parse_numeric(s) -> Optional[float]:
    """Extract first number: '1840 tok/s' -> 1840.0, 94.3 -> 94.3"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"[\d]+(?:\.\d+)?", str(s))
    return float(m.group()) if m else None


def _write_log(result: dict) -> None:
    log_dir = os.path.dirname(SYNC_LOG_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    with open(SYNC_LOG_PATH, "w") as f:
        json.dump(result, f, indent=2)


def sync_sentinel(db: Session) -> dict:
    """Fetch Sentinel data.json, match to workloads, write sentinel fields.
    Returns the sync result dict (also written to SYNC_LOG_PATH).
    Safe to call even if Sentinel is unreachable — failure is logged, no DB writes occur.
    """
    sentinel_url = os.getenv("SENTINEL_DATA_URL", "").rstrip("/")
    if not sentinel_url:
        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": "SENTINEL_DATA_URL not configured",
            "analyses_total": 0,
            "matched": 0,
            "unmatched_models": [],
            "unmatched_hardware": [],
            "manual_divergences": [],
        }
        _write_log(result)
        return result

    try:
        resp = httpx.get(f"{sentinel_url}/data/data.json", timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": str(exc),
            "analyses_total": 0,
            "matched": 0,
            "unmatched_models": [],
            "unmatched_hardware": [],
            "manual_divergences": [],
        }
        _write_log(result)
        return result

    mappings = _load_mappings()
    model_map: dict = mappings.get("models", {})
    hw_map: dict = mappings.get("hardware", {})

    analyses = data.get("analyses", [])
    matched = 0
    unmatched_models: set = set()
    unmatched_hardware: set = set()
    manual_divergences: list = []
    now = datetime.utcnow()

    for analysis in analyses:
        raw_model = (analysis.get("model_tested") or "").strip()
        inf_model = model_map.get(raw_model)
        if not inf_model:
            if raw_model:
                unmatched_models.add(raw_model)
            continue

        raw_isl = analysis.get("isl", "")
        inf_seqlen = _normalize_seqlen(raw_isl) if raw_isl else None

        for raw_hw in analysis.get("nvidia_gpus", []):
            inf_hw = hw_map.get(raw_hw.strip())
            if not inf_hw:
                unmatched_hardware.add(raw_hw.strip())
                continue

            q = db.query(Workload).filter(
                Workload.model == inf_model,
                Workload.hardware == inf_hw,
            )
            if inf_seqlen:
                workload = q.filter(Workload.seqlens == inf_seqlen).first() or q.first()
            else:
                workload = q.first()

            if not workload:
                continue

            # Find best amd_value: prefer comparison whose amd_gpu maps to a known hw
            best_amd_value: Optional[float] = None
            for comp in analysis.get("comparisons", []):
                val = _parse_numeric(comp.get("amd_value"))
                if val is None:
                    continue
                if best_amd_value is None:
                    best_amd_value = val
                if hw_map.get((comp.get("amd_gpu") or "").strip()):
                    best_amd_value = val
                    break

            image_url = analysis.get("image_url", "")
            if image_url and not image_url.startswith("http"):
                image_url = f"{sentinel_url}/{image_url.lstrip('/')}"

            workload.sentinel_threat_level = analysis.get("overall_threat_level")
            workload.sentinel_summary = (analysis.get("summary") or "")[:500]
            workload.sentinel_image_url = image_url
            workload.sentinel_synced_at = now

            if best_amd_value is not None:
                workload.amd_tps_sentinel_value = best_amd_value
                workload.amd_tps_synced_at = now

                if workload.amd_tps_source in (None, "sentinel"):
                    old_val = workload.amd_tps
                    workload.amd_tps = best_amd_value
                    workload.amd_tps_source = "sentinel"
                    db.add(AuditLog(
                        workload_id=workload.id,
                        user_name="sentinel-sync",
                        user_email="sentinel-sync",
                        field_name="amd_tps",
                        old_value=str(old_val) if old_val is not None else None,
                        new_value=str(best_amd_value),
                    ))
                else:
                    if workload.amd_tps is not None and workload.amd_tps != 0:
                        diff = abs(best_amd_value - workload.amd_tps) / workload.amd_tps
                        if diff > 0.05:
                            manual_divergences.append({
                                "workload_id": workload.id,
                                "sentinel_value": best_amd_value,
                                "manual_value": workload.amd_tps,
                            })

            matched += 1

    db.commit()

    result = {
        "timestamp": now.isoformat() + "Z",
        "analyses_total": len(analyses),
        "matched": matched,
        "unmatched_models": sorted(unmatched_models),
        "unmatched_hardware": sorted(unmatched_hardware),
        "manual_divergences": manual_divergences,
    }
    _write_log(result)
    return result


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db), user=Depends(require_auth)):
    return sync_sentinel(db)


@router.get("/status")
def get_status():
    if os.path.exists(SYNC_LOG_PATH):
        with open(SYNC_LOG_PATH) as f:
            return json.load(f)
    return {
        "timestamp": None,
        "analyses_total": 0,
        "matched": 0,
        "unmatched_models": [],
        "unmatched_hardware": [],
        "manual_divergences": [],
    }


@router.get("/status-fragment", response_class=HTMLResponse)
def status_fragment(request: Request, user=Depends(get_current_user)):
    status = get_status()
    return templates.TemplateResponse(
        "partials/sentinel_status.html",
        {"request": request, "status": status, "user": user},
    )


@router.get("/analyses-fragment", response_class=HTMLResponse)
def analyses_fragment(
    request: Request,
    model: str,
    seqlen: str,
    scene_id: str,
    db: Session = Depends(get_db),
):
    workloads = (
        db.query(Workload)
        .filter(
            Workload.model == model,
            Workload.seqlens == seqlen,
            Workload.sentinel_threat_level.isnot(None),
        )
        .all()
    )
    analyses = [
        {
            "workload_id": w.id,
            "hardware": w.hardware,
            "framework": w.framework,
            "precision": w.precision,
            "sentinel_threat_level": w.sentinel_threat_level,
            "sentinel_summary": w.sentinel_summary,
            "amd_tps_sentinel_value": w.amd_tps_sentinel_value,
            "pic": w.pic,
        }
        for w in workloads
    ]
    return templates.TemplateResponse(
        "partials/sentinel_analyses_list.html",
        {
            "request": request,
            "analyses": analyses,
            "model": model,
            "seqlen": seqlen,
            "scene_id": scene_id,
        },
    )
