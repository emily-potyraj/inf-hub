from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import TeamFunction
from app.auth import require_auth

router = APIRouter(prefix="/team", tags=["team"])


class TeamFunctionCreate(BaseModel):
    function: str
    owner: Optional[str] = None
    backup: Optional[str] = None
    notes: Optional[str] = None


class TeamFunctionUpdate(BaseModel):
    owner: Optional[str] = None
    backup: Optional[str] = None
    notes: Optional[str] = None


class TeamFunctionOut(BaseModel):
    id: int
    function: str
    owner: Optional[str]
    backup: Optional[str]
    notes: Optional[str]

    model_config = {"from_attributes": True}


@router.get("/functions", response_model=list[TeamFunctionOut])
def list_functions(db: Session = Depends(get_db)):
    return db.query(TeamFunction).all()


@router.post("/functions", response_model=TeamFunctionOut)
def create_function(
    payload: TeamFunctionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    tf = TeamFunction(**payload.model_dump())
    db.add(tf)
    db.commit()
    db.refresh(tf)
    return tf


@router.patch("/functions/{fn_id}", response_model=TeamFunctionOut)
def update_function(
    fn_id: int,
    payload: TeamFunctionUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    tf = db.get(TeamFunction, fn_id)
    if not tf:
        raise HTTPException(status_code=404, detail="Not found")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(tf, field, val)
    db.commit()
    db.refresh(tf)
    return tf
