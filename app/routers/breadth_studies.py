import itertools
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import get_db
from app.models import BreadthStudy, Workload
from app.schemas import BreadthStudyCreate, BreadthStudyRow, BreadthStudyResponse
from app.auth import require_auth

router = APIRouter(prefix="/breadth-studies", tags=["breadth_studies"])


@router.post("", response_model=BreadthStudyResponse)
def create_breadth_study(
    payload: BreadthStudyCreate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    # Validate all dimension lists are non-empty
    dimensions = {
        "models": payload.models,
        "hardware": payload.hardware,
        "frameworks": payload.frameworks,
        "precisions": payload.precisions,
        "scenarios": payload.scenarios,
        "seqlens": payload.seqlens,
    }
    for dim_name, dim_values in dimensions.items():
        if not dim_values:
            raise HTTPException(status_code=422, detail=f"'{dim_name}' must not be empty")

    # Generate study_id and insert BreadthStudy row
    study_id = str(uuid.uuid4())
    study = BreadthStudy(
        id=study_id,
        name=payload.name,
        created_by=user.get("name"),
        created_by_email=user.get("email"),
    )
    db.add(study)
    db.flush()  # persist study before workloads

    # Compute crossproduct
    combos = list(itertools.product(
        payload.models,
        payload.hardware,
        payload.frameworks,
        payload.precisions,
        payload.scenarios,
        payload.seqlens,
    ))
    total = len(combos)

    rows = [
        {
            "model": model,
            "hardware": hardware,
            "framework": framework,
            "precision": precision,
            "scenario": scenario,
            "seqlens": seqlens,
            "status": "not_started",
            "accuracy_status": "not_run",
            "work_type": "breadth_test",
            "study_id": study_id,
        }
        for model, hardware, framework, precision, scenario, seqlens in combos
    ]

    # Bulk insert with INSERT OR IGNORE
    stmt = sqlite_insert(Workload).values(rows).prefix_with("OR IGNORE")
    result = db.execute(stmt)
    created = result.rowcount
    skipped = total - created

    db.commit()

    return BreadthStudyResponse(study_id=study_id, created=created, skipped=skipped)


@router.get("", response_model=List[BreadthStudyRow])
def list_breadth_studies(db: Session = Depends(get_db)):
    studies = (
        db.query(BreadthStudy)
        .order_by(BreadthStudy.created_at.desc())
        .all()
    )

    # Count workloads per study
    counts = (
        db.query(Workload.study_id, func.count(Workload.id).label("cnt"))
        .filter(Workload.study_id.isnot(None))
        .group_by(Workload.study_id)
        .all()
    )
    count_map = {row.study_id: row.cnt for row in counts}

    result = []
    for s in studies:
        result.append(BreadthStudyRow(
            id=s.id,
            name=s.name,
            created_by=s.created_by,
            created_by_email=s.created_by_email,
            created_at=s.created_at.isoformat() if s.created_at else None,
            workload_count=count_map.get(s.id, 0),
        ))
    return result
