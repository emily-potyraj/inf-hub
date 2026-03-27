import json
import os
import pytest
from unittest.mock import patch, MagicMock

WORKLOAD_BASE = {
    "model": "DSR1", "hardware": "B200", "framework": "TRT-LLM",
    "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
}

MOCK_SENTINEL_DATA = {
    "analyses": [
        {
            "model_tested": "DeepSeek-R1",
            "nvidia_gpus": ["B200"],
            "amd_gpus": ["MI300X"],
            "isl": "1K / 1K",
            "overall_threat_level": "RED",
            "summary": "AMD ahead on throughput by ~14%",
            "image_url": "images/chart_dsr1_b200.jpg",
            "tab": "Inference Performance",
            "comparisons": [
                {
                    "nvidia_gpu": "B200",
                    "amd_gpu": "MI300X",
                    "metric": "throughput",
                    "nvidia_value": "1840",
                    "amd_value": "2100",
                    "winner": "AMD_WINNING",
                    "delta_description": "AMD ahead by ~14%",
                }
            ],
        }
    ]
}

MOCK_MAPPINGS = {
    "models": {"DeepSeek-R1": "DSR1"},
    "hardware": {"B200": "B200"},
}


@pytest.fixture(autouse=True)
def mock_mappings_and_log(tmp_path, monkeypatch):
    mappings_file = tmp_path / "sentinel_mappings.json"
    mappings_file.write_text(json.dumps(MOCK_MAPPINGS))
    log_file = tmp_path / "sentinel_sync_log.json"
    monkeypatch.setenv("SENTINEL_DATA_URL", "https://sentinel.example.com")
    import app.routers.sentinel as sentinel_mod
    monkeypatch.setattr(sentinel_mod, "MAPPINGS_PATH", str(mappings_file))
    monkeypatch.setattr(sentinel_mod, "SYNC_LOG_PATH", str(log_file))
    yield log_file


def _mock_httpx_get(url, timeout=30):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = MOCK_SENTINEL_DATA
    return mock


def test_sync_populates_sentinel_fields(auth_client, monkeypatch):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    with patch("httpx.get", side_effect=_mock_httpx_get):
        r = auth_client.post("/sentinel/sync")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] == 1
    wl = auth_client.get("/workloads/1").json()
    assert wl["sentinel_threat_level"] == "RED"
    assert wl["sentinel_summary"] == "AMD ahead on throughput by ~14%"
    assert "images/chart_dsr1_b200.jpg" in wl["sentinel_image_url"]
    assert wl["sentinel_synced_at"] is not None


def test_sync_sets_amd_tps_when_null(auth_client, monkeypatch):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    wl = auth_client.get("/workloads/1").json()
    assert wl["amd_tps"] == 2100.0
    assert wl["amd_tps_source"] == "sentinel"
    assert wl["amd_tps_sentinel_value"] == 2100.0


def test_sync_does_not_overwrite_manual_amd_tps(auth_client, monkeypatch):
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/amd_tps", json={"value": 9999.0})
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    wl = auth_client.get(f"/workloads/{w_id}").json()
    assert wl["amd_tps"] == 9999.0
    assert wl["amd_tps_source"] == "manual"
    assert wl["amd_tps_sentinel_value"] == 2100.0


def test_sync_records_divergence_in_log(auth_client, monkeypatch, mock_mappings_and_log):
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/amd_tps", json={"value": 9999.0})
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    log = json.loads(mock_mappings_and_log.read_text())
    assert len(log["manual_divergences"]) == 1
    assert log["manual_divergences"][0]["manual_value"] == 9999.0
    assert log["manual_divergences"][0]["sentinel_value"] == 2100.0


def test_sync_writes_audit_log_entry(auth_client, monkeypatch):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    audit = auth_client.get("/workloads/1/audit").json()
    amd_entries = [e for e in audit if e["field_name"] == "amd_tps"]
    assert any(e["user_name"] == "sentinel-sync" for e in amd_entries)


def test_sync_records_unmatched_model(auth_client, monkeypatch, mock_mappings_and_log, tmp_path):
    import app.routers.sentinel as sentinel_mod
    bad_mappings = tmp_path / "bad_mappings.json"
    bad_mappings.write_text(json.dumps({"models": {}, "hardware": {}}))
    monkeypatch.setattr(sentinel_mod, "MAPPINGS_PATH", str(bad_mappings))
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    log = json.loads(mock_mappings_and_log.read_text())
    assert "DeepSeek-R1" in log["unmatched_models"]


def test_sync_fetch_failure_writes_error_log(auth_client, monkeypatch, mock_mappings_and_log):
    def fail(*a, **kw):
        raise Exception("connection refused")
    with patch("httpx.get", side_effect=fail):
        r = auth_client.post("/sentinel/sync")
    assert r.status_code == 200
    log = json.loads(mock_mappings_and_log.read_text())
    assert "error" in log


def test_sync_requires_auth(client):
    r = client.post("/sentinel/sync")
    assert r.status_code == 401


def test_get_status_returns_log(auth_client, monkeypatch, mock_mappings_and_log):
    mock_mappings_and_log.write_text(json.dumps({"timestamp": "2026-03-26T06:00:00Z", "matched": 5}))
    r = auth_client.get("/sentinel/status")
    assert r.status_code == 200
    assert r.json()["matched"] == 5


def test_get_status_when_no_log(auth_client, monkeypatch, tmp_path):
    import app.routers.sentinel as sentinel_mod
    monkeypatch.setattr(sentinel_mod, "SYNC_LOG_PATH", str(tmp_path / "nonexistent.json"))
    r = auth_client.get("/sentinel/status")
    assert r.status_code == 200
    assert r.json()["matched"] == 0
