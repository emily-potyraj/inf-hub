from pydantic import BaseModel
from typing import Optional


class WorkloadCreate(BaseModel):
    model: str
    hardware: str
    framework: str
    precision: str
    scenario: str
    seqlens: str
    status: str = "not_started"
    pic: Optional[str] = None
    priority: Optional[int] = None
    story_label: Optional[str] = None
    accuracy_status: str = "not_run"
    nv_tps: Optional[float] = None
    amd_tps: Optional[float] = None
    dl_perf_published: Optional[str] = None
    infmax_submitted: Optional[str] = None
    nvmax_recipe_url: Optional[str] = None
    ibdb_link: Optional[str] = None
    notes: Optional[str] = None


class WorkloadRow(BaseModel):
    id: int
    model: str
    hardware: str
    framework: str
    precision: str
    scenario: str
    seqlens: str
    status: str
    pic: Optional[str]
    priority: Optional[int]
    story_label: Optional[str]
    accuracy_status: str
    nv_tps: Optional[float]
    amd_tps: Optional[float]
    gap_pct: Optional[float]
    dl_perf_published: Optional[str]
    infmax_submitted: Optional[str]
    nvmax_recipe_url: Optional[str]
    ibdb_link: Optional[str]
    notes: Optional[str]
    last_updated: Optional[str]

    model_config = {"from_attributes": True}


class FieldUpdate(BaseModel):
    value: Optional[str | float | int] = None
