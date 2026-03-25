import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Workload, ConfigVersion, AuditLog, TeamFunction


def test_workload_unique_constraint(db):
    w1 = Workload(
        model="DSR1", hardware="B200", framework="vLLM",
        precision="FP8", scenario="agg", seqlens="1k/1k",
    )
    w2 = Workload(
        model="DSR1", hardware="B200", framework="vLLM",
        precision="FP8", scenario="agg", seqlens="1k/1k",
    )
    db.add(w1)
    db.commit()
    db.add(w2)
    with pytest.raises(IntegrityError):
        db.commit()


def test_workload_different_seqlens_allowed(db):
    w1 = Workload(
        model="DSR1", hardware="B200", framework="vLLM",
        precision="FP8", scenario="agg", seqlens="1k/1k",
    )
    w2 = Workload(
        model="DSR1", hardware="B200", framework="vLLM",
        precision="FP8", scenario="agg", seqlens="8k/1k",
    )
    db.add_all([w1, w2])
    db.commit()
    assert db.query(Workload).count() == 2


def test_config_version_num_per_workload(db):
    w = Workload(
        model="DSR1", hardware="B200", framework="vLLM",
        precision="FP8", scenario="agg", seqlens="1k/1k",
    )
    db.add(w)
    db.commit()
    c1 = ConfigVersion(workload_id=w.id, version_num=1, source_type="url",
                       url="https://example.com/config1", uploaded_by="alice",
                       uploaded_by_email="alice@nvidia.com")
    c2 = ConfigVersion(workload_id=w.id, version_num=2, source_type="url",
                       url="https://example.com/config2", uploaded_by="alice",
                       uploaded_by_email="alice@nvidia.com")
    db.add_all([c1, c2])
    db.commit()
    versions = db.query(ConfigVersion).filter_by(workload_id=w.id).order_by(ConfigVersion.version_num).all()
    assert [v.version_num for v in versions] == [1, 2]


def test_audit_log_fields(db):
    w = Workload(
        model="DSR1", hardware="B200", framework="vLLM",
        precision="FP8", scenario="agg", seqlens="1k/1k",
    )
    db.add(w)
    db.commit()
    log = AuditLog(workload_id=w.id, user_name="alice",
                   user_email="alice@nvidia.com", field_name="status",
                   old_value="not_started", new_value="config_search")
    db.add(log)
    db.commit()
    fetched = db.query(AuditLog).first()
    assert fetched.field_name == "status"
    assert fetched.old_value == "not_started"


def test_team_function_crud(db):
    tf = TeamFunction(function="srt-slurm PR approvals",
                      owner="weiliang", backup="alice")
    db.add(tf)
    db.commit()
    assert db.query(TeamFunction).count() == 1
