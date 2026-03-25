import io
import pytest


WORKLOAD = {
    "model": "DSR1", "hardware": "B200", "framework": "vLLM",
    "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
}


@pytest.fixture
def workload_id(auth_client):
    r = auth_client.post("/workloads", json=WORKLOAD)
    return r.json()["id"]


def test_add_config_url(auth_client, workload_id):
    r = auth_client.post(f"/workloads/{workload_id}/configs", json={
        "source_type": "url",
        "url": "https://github.com/NVIDIA/srt-slurm/blob/main/configs/dsr1.yaml",
        "notes": "Initial config",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["version_num"] == 1
    assert data["source_type"] == "url"


def test_add_config_increments_version(auth_client, workload_id):
    auth_client.post(f"/workloads/{workload_id}/configs", json={
        "source_type": "url", "url": "https://example.com/v1",
    })
    r = auth_client.post(f"/workloads/{workload_id}/configs", json={
        "source_type": "url", "url": "https://example.com/v2",
    })
    assert r.json()["version_num"] == 2


def test_current_config_is_latest(auth_client, workload_id):
    auth_client.post(f"/workloads/{workload_id}/configs", json={
        "source_type": "url", "url": "https://example.com/v1",
    })
    auth_client.post(f"/workloads/{workload_id}/configs", json={
        "source_type": "url", "url": "https://example.com/v2",
    })
    r = auth_client.get(f"/workloads/{workload_id}/configs/current")
    assert r.json()["version_num"] == 2
    assert r.json()["url"] == "https://example.com/v2"


def test_list_configs_ordered_newest_first(auth_client, workload_id):
    for i in range(3):
        auth_client.post(f"/workloads/{workload_id}/configs", json={
            "source_type": "url", "url": f"https://example.com/v{i+1}",
        })
    r = auth_client.get(f"/workloads/{workload_id}/configs")
    versions = [c["version_num"] for c in r.json()]
    assert versions == [3, 2, 1]


def test_add_config_file_upload(auth_client, workload_id, tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("tp: 8\nep: 4\n")
    with open(config_file, "rb") as f:
        r = auth_client.post(
            f"/workloads/{workload_id}/configs/upload",
            files={"file": ("config.yaml", f, "application/octet-stream")},
            data={"notes": "First file upload"},
        )
    assert r.status_code == 200
    assert r.json()["source_type"] == "file"
    assert r.json()["original_filename"] == "config.yaml"


def test_config_requires_auth(client, auth_client):
    r = auth_client.post("/workloads", json=WORKLOAD)
    w_id = r.json()["id"]
    r2 = client.post(f"/workloads/{w_id}/configs", json={
        "source_type": "url", "url": "https://example.com",
    })
    assert r2.status_code == 401


def test_get_specific_config_version(auth_client, workload_id):
    auth_client.post(f"/workloads/{workload_id}/configs", json={
        "source_type": "url", "url": "https://example.com/v1",
    })
    auth_client.post(f"/workloads/{workload_id}/configs", json={
        "source_type": "url", "url": "https://example.com/v2",
    })
    r = auth_client.get(f"/workloads/{workload_id}/config/1")
    assert r.status_code == 200
    assert r.json()["version_num"] == 1
    assert r.json()["url"] == "https://example.com/v1"
