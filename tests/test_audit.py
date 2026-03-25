import pytest
from app.models import AuditLog

WORKLOAD = {
    "model": "DSR1", "hardware": "B200", "framework": "vLLM",
    "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
}


def test_patch_writes_audit_log(auth_client, db):
    r = auth_client.post("/workloads", json=WORKLOAD)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/status", json={"value": "config_search"})
    logs = db.query(AuditLog).filter_by(workload_id=w_id).all()
    assert len(logs) == 1
    assert logs[0].field_name == "status"
    assert logs[0].old_value == "not_started"
    assert logs[0].new_value == "config_search"
    assert logs[0].user_email == "testuser@nvidia.com"


def test_multiple_patches_append_logs(auth_client, db):
    r = auth_client.post("/workloads", json=WORKLOAD)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/status", json={"value": "config_search"})
    auth_client.patch(f"/workloads/{w_id}/status", json={"value": "accuracy_gate"})
    logs = db.query(AuditLog).filter_by(workload_id=w_id, field_name="status").all()
    assert len(logs) == 2
    assert logs[0].old_value == "not_started"
    assert logs[1].old_value == "config_search"
    assert logs[1].new_value == "accuracy_gate"


def test_audit_log_atomic_rollback(auth_client, db, monkeypatch):
    """If audit write fails, the field update must also be rolled back."""
    r = auth_client.post("/workloads", json=WORKLOAD)
    w_id = r.json()["id"]

    from app import audit
    def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated audit failure")
    monkeypatch.setattr(audit, "write_audit_log", fail_audit)

    response = auth_client.patch(f"/workloads/{w_id}/status", json={"value": "config_search"})
    assert response.status_code == 500

    from app.models import Workload
    w = db.get(Workload, w_id)
    db.refresh(w)
    assert w.status == "not_started"  # rolled back


def test_get_workload_audit_history(auth_client, db):
    r = auth_client.post("/workloads", json=WORKLOAD)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/pic", json={"value": "weiliang"})
    r2 = auth_client.get(f"/workloads/{w_id}/audit")
    assert r2.status_code == 200
    logs = r2.json()
    assert len(logs) == 1
    assert logs[0]["field_name"] == "pic"
