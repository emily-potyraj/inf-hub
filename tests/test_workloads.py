import pytest


WORKLOAD_BASE = {
    "model": "DSR1", "hardware": "B200", "framework": "vLLM",
    "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
}


def test_create_workload(auth_client):
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] is not None
    assert data["status"] == "not_started"
    assert data["gap_pct"] is None  # no TPS yet


def test_create_duplicate_workload_rejected(auth_client):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    assert r.status_code == 409


def test_create_workload_missing_required_field(auth_client):
    bad = {k: v for k, v in WORKLOAD_BASE.items() if k != "seqlens"}
    r = auth_client.post("/workloads", json=bad)
    assert r.status_code == 422


def test_list_workloads(auth_client):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    r = auth_client.get("/workloads")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_filter_by_hardware(auth_client):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    auth_client.post("/workloads", json={**WORKLOAD_BASE, "hardware": "H100", "seqlens": "8k/1k"})
    r = auth_client.get("/workloads?hardware=B200")
    assert len(r.json()) == 1
    assert r.json()[0]["hardware"] == "B200"


def test_filter_amd_ahead(auth_client):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    w2 = {**WORKLOAD_BASE, "seqlens": "8k/1k"}
    auth_client.post("/workloads", json=w2)
    r1 = auth_client.get("/workloads")
    w1_id = r1.json()[0]["id"]
    auth_client.patch(f"/workloads/{w1_id}/nv_tps", json={"value": 100.0})
    auth_client.patch(f"/workloads/{w1_id}/amd_tps", json={"value": 120.0})
    r = auth_client.get("/workloads?amd_ahead=true")
    assert len(r.json()) == 1
    assert r.json()[0]["gap_pct"] < 0


def test_gap_pct_computed(auth_client):
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/nv_tps", json={"value": 1000.0})
    auth_client.patch(f"/workloads/{w_id}/amd_tps", json={"value": 800.0})
    r2 = auth_client.get(f"/workloads/{w_id}")
    assert abs(r2.json()["gap_pct"] - 0.25) < 0.001


def test_patch_field_requires_auth(client):
    r = client.post("/workloads", json=WORKLOAD_BASE)
    assert r.status_code == 401


def test_get_workload_by_id(auth_client):
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    w_id = r.json()["id"]
    r2 = auth_client.get(f"/workloads/{w_id}")
    assert r2.status_code == 200
    assert r2.json()["model"] == "DSR1"


def test_get_workload_not_found(client):
    r = client.get("/workloads/9999")
    assert r.status_code == 404


def test_filter_unassigned_pic(auth_client):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    auth_client.post("/workloads", json={**WORKLOAD_BASE, "seqlens": "8k/1k"})
    w1_id = auth_client.get("/workloads").json()[0]["id"]
    auth_client.patch(f"/workloads/{w1_id}/pic", json={"value": "alice"})
    r = auth_client.get("/workloads?unassigned_pic=true")
    assert len(r.json()) == 1
    assert r.json()[0]["pic"] is None
