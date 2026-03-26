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
    work_type: Optional[str] = None
    study_id: Optional[str] = None


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
    work_type: Optional[str] = None
    study_id: Optional[str] = None
    last_updated: Optional[str]

    model_config = {"from_attributes": True}


class BreadthStudyCreate(BaseModel):
    name:       str
    models:     list[str]
    hardware:   list[str]
    frameworks: list[str]
    precisions: list[str]
    scenarios:  list[str]
    seqlens:    list[str]


class BreadthStudyRow(BaseModel):
    id:               str
    name:             str
    created_by:       Optional[str]
    created_by_email: Optional[str]
    created_at:       Optional[str]   # ISO string
    workload_count:   int

    model_config = {"from_attributes": True}


class BreadthStudyResponse(BaseModel):
    study_id: str
    created:  int
    skipped:  int


class FieldUpdate(BaseModel):
    value: Optional[str | float | int] = None
