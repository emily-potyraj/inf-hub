import json
from unittest.mock import patch
from datetime import datetime, timezone

WORKLOAD_BASE = {
    "model": "LLaMA3-70B", "hardware": "MI300X", "framework": "vLLM",
    "precision": "FP16", "scenario": "agg", "seqlens": "2k/2k",
}


def _setup_log_path(tmp_path, monkeypatch):
    import app.routers.ibdb as ibdb_router
    log_file = tmp_path / "ibdb_sync_log.json"
    monkeypatch.setattr(ibdb_router, "SYNC_LOG_PATH", str(log_file))
    return log_file


def test_sync_sets_ibdb_latest_run_at(auth_client, tmp_path, monkeypatch):
    _setup_log_path(tmp_path, monkeypatch)
    monkeypatch.setenv("IBDB_AUTH_TOKEN", "test-token")

    auth_client.post("/workloads", json=WORKLOAD_BASE)
    run_date = datetime(2025, 3, 14, 9, 32, 0, tzinfo=timezone.utc)

    with patch("app.ibdb_client.check_workload", return_value=run_date):
        r = auth_client.post("/ibdb/sync")

    assert r.status_code == 200
    data = r.json()
    assert data["synced"] == 1
    assert data["with_data"] == 1

    wl = auth_client.get("/workloads").json()[0]
    assert wl["ibdb_latest_run_at"] is not None
    assert "2025-03-14" in wl["ibdb_latest_run_at"]


def test_sync_sets_ibdb_synced_at_even_when_no_data(auth_client, tmp_path, monkeypatch):
    _setup_log_path(tmp_path, monkeypatch)
    monkeypatch.setenv("IBDB_AUTH_TOKEN", "test-token")

    auth_client.post("/workloads", json=WORKLOAD_BASE)

    with patch("app.ibdb_client.check_workload", return_value=None):
        r = auth_client.post("/ibdb/sync")

    assert r.status_code == 200
    wl = auth_client.get("/workloads").json()[0]
    assert wl["ibdb_latest_run_at"] is None
    assert wl["ibdb_synced_at"] is not None


def test_sync_writes_log_file(auth_client, tmp_path, monkeypatch):
    log_file = _setup_log_path(tmp_path, monkeypatch)
    monkeypatch.setenv("IBDB_AUTH_TOKEN", "test-token")

    with patch("app.ibdb_client.check_workload", return_value=None):
        auth_client.post("/ibdb/sync")

    log = json.loads(log_file.read_text())
    assert "timestamp" in log
    assert "synced" in log
    assert "with_data" in log


def test_sync_requires_auth(client):
    r = client.post("/ibdb/sync")
    assert r.status_code == 401


def test_get_status_returns_log(auth_client, tmp_path, monkeypatch):
    log_file = _setup_log_path(tmp_path, monkeypatch)
    log_file.write_text(json.dumps({"timestamp": "2026-04-06T10:00:00Z", "synced": 3, "with_data": 2}))

    r = auth_client.get("/ibdb/status")
    assert r.status_code == 200
    assert r.json()["synced"] == 3


def test_get_status_when_no_log(auth_client, tmp_path, monkeypatch):
    import app.routers.ibdb as ibdb_router
    monkeypatch.setattr(ibdb_router, "SYNC_LOG_PATH", str(tmp_path / "nonexistent.json"))

    r = auth_client.get("/ibdb/status")
    assert r.status_code == 200
    assert r.json()["synced"] == 0
