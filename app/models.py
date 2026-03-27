from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Text, Float, DateTime, ForeignKey,
    UniqueConstraint,
)
from app.database import Base


def _now():
    return datetime.now(timezone.utc)


class Workload(Base):
    __tablename__ = "workloads"
    __table_args__ = (
        UniqueConstraint(
            "model", "hardware", "framework", "precision", "scenario", "seqlens",
            name="uq_workload_identity",
        ),
    )

    id = Column(Integer, primary_key=True)
    model = Column(Text, nullable=False)
    hardware = Column(Text, nullable=False)
    framework = Column(Text, nullable=False)
    precision = Column(Text, nullable=False)
    scenario = Column(Text, nullable=False)
    seqlens = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="not_started")
    pic = Column(Text)
    priority = Column(Integer)
    story_label = Column(Text)
    accuracy_status = Column(Text, nullable=False, default="not_run")
    nv_tps = Column(Float)
    amd_tps = Column(Float)
    amd_tps_source          = Column(Text)          # 'manual' | 'sentinel'
    amd_tps_sentinel_value  = Column(Float)
    amd_tps_synced_at       = Column(DateTime)
    sentinel_threat_level   = Column(Text)           # 'GREEN' | 'YELLOW' | 'RED'
    sentinel_summary        = Column(Text)
    sentinel_image_url      = Column(Text)
    sentinel_synced_at      = Column(DateTime)
    dl_perf_published = Column(Text)
    infmax_submitted = Column(Text)
    nvmax_recipe_url = Column(Text)
    ibdb_link = Column(Text)
    notes = Column(Text)
    work_type = Column(Text)   # nullable; 'tune' | 'breadth_test'
    study_id  = Column(Text)   # nullable; FK to breadth_studies.id (app-enforced)
    created_at = Column(DateTime, default=_now)
    last_updated = Column(DateTime, default=_now, onupdate=_now)


class ConfigVersion(Base):
    __tablename__ = "config_versions"

    id = Column(Integer, primary_key=True)
    workload_id = Column(Integer, ForeignKey("workloads.id"), nullable=False)
    version_num = Column(Integer, nullable=False)
    source_type = Column(Text, nullable=False)  # "file" or "url"
    file_path = Column(Text)
    original_filename = Column(Text)
    url = Column(Text)
    uploaded_by = Column(Text, nullable=False)
    uploaded_by_email = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=_now)
    notes = Column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    workload_id = Column(Integer, ForeignKey("workloads.id"), nullable=False)
    user_name = Column(Text, nullable=False)
    user_email = Column(Text, nullable=False)
    field_name = Column(Text, nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    timestamp = Column(DateTime, default=_now)


class BreadthStudy(Base):
    __tablename__ = "breadth_studies"
    id               = Column(Text, primary_key=True)   # UUID string
    name             = Column(Text, nullable=False)
    created_by       = Column(Text)
    created_by_email = Column(Text)
    created_at       = Column(DateTime, default=_now)


class TeamFunction(Base):
    __tablename__ = "team_functions"

    id = Column(Integer, primary_key=True)
    function = Column(Text, nullable=False)
    owner = Column(Text)
    backup = Column(Text)
    notes = Column(Text)


class DevzoneScene(Base):
    __tablename__ = "devzone_scenes"

    id               = Column(Text, primary_key=True)
    name             = Column(Text, nullable=False)
    model            = Column(Text, nullable=False)
    seqlen           = Column(Text, nullable=False)
    created_by       = Column(Text)
    created_by_email = Column(Text)
    created_at       = Column(DateTime, default=_now)
    is_published     = Column(Integer, default=0)
    published_at     = Column(DateTime)


class DevzoneCurve(Base):
    __tablename__ = "devzone_curves"

    id          = Column(Text, primary_key=True)
    scene_id    = Column(Text, ForeignKey("devzone_scenes.id", ondelete="CASCADE"), nullable=False)
    label       = Column(Text, nullable=False)
    hardware    = Column(Text, nullable=False)
    framework   = Column(Text)
    precision   = Column(Text)
    color       = Column(Text)
    ibdb_source = Column(Text)
    uploaded_by = Column(Text)
    uploaded_at = Column(DateTime, default=_now)
    inf_hub_workload_id = Column(Text)   # nullable FK to workloads.id, app-enforced
    points      = Column(Text, nullable=False)   # JSON string
