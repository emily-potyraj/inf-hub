import pytest


WORKLOAD_BASE = {
    "model": "DSR1", "hardware": "B200", "framework": "vLLM",
    "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
}

STUDY_BASE = {
    "name": "Test Study",
    "models": ["DSR1", "LLM70B"],
    "hardware": ["B200"],
    "frameworks": ["vLLM"],
    "precisions": ["FP8"],
    "scenarios": ["agg"],
    "seqlens": ["1k/1k", "8k/1k"],
}


def test_create_breadth_study_creates_study_and_workloads(auth_client):
    # 2 models x 1 hw x 1 fw x 1 precision x 1 scenario x 2 seqlens = 4 workloads
    r = auth_client.post("/breadth-studies", json=STUDY_BASE)
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 4
    assert data["skipped"] == 0

    # Verify all 4 workloads have work_type='breadth_test' and same study_id
    wl_r = auth_client.get("/workloads")
    assert wl_r.status_code == 200
    workloads = wl_r.json()
    assert len(workloads) == 4
    study_ids = {w["study_id"] for w in workloads}
    assert len(study_ids) == 1  # all same study_id
    assert all(w["work_type"] == "breadth_test" for w in workloads)
    assert all(w["study_id"] is not None for w in workloads)


def test_create_breadth_study_skips_duplicates(auth_client):
    # Pre-create 1 workload that overlaps with study
    auth_client.post("/workloads", json=WORKLOAD_BASE)  # DSR1/B200/vLLM/FP8/agg/1k/1k

    # POST study that includes this workload in its crossproduct
    r = auth_client.post("/breadth-studies", json=STUDY_BASE)
    assert r.status_code == 200
    data = r.json()
    assert data["skipped"] == 1
    assert data["created"] == 3  # 4 total - 1 pre-existing


def test_create_breadth_study_requires_auth(client):
    r = client.post("/breadth-studies", json=STUDY_BASE)
    assert r.status_code == 401


def test_create_breadth_study_validates_empty_dimensions(auth_client):
    payload = {**STUDY_BASE, "models": []}
    r = auth_client.post("/breadth-studies", json=payload)
    assert r.status_code == 422


def test_list_breadth_studies_open(auth_client, client):
    # POST as authenticated user
    r = auth_client.post("/breadth-studies", json=STUDY_BASE)
    assert r.status_code == 200

    # GET as anonymous user
    r2 = client.get("/breadth-studies")
    assert r2.status_code == 200
    data = r2.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Study"
    assert data[0]["workload_count"] == 4


def test_list_breadth_studies_empty(client):
    r = client.get("/breadth-studies")
    assert r.status_code == 200
    assert r.json() == []


def test_create_breadth_study_all_skipped(auth_client):
    # Pre-create all 4 workloads that the study would create
    combos = [
        ("DSR1", "B200", "vLLM", "FP8", "agg", "1k/1k"),
        ("DSR1", "B200", "vLLM", "FP8", "agg", "8k/1k"),
        ("LLM70B", "B200", "vLLM", "FP8", "agg", "1k/1k"),
        ("LLM70B", "B200", "vLLM", "FP8", "agg", "8k/1k"),
    ]
    for model, hardware, framework, precision, scenario, seqlens in combos:
        auth_client.post("/workloads", json={
            "model": model, "hardware": hardware, "framework": framework,
            "precision": precision, "scenario": scenario, "seqlens": seqlens,
        })

    # POST same dims → all skipped
    r = auth_client.post("/breadth-studies", json=STUDY_BASE)
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 0
    assert data["skipped"] == 4
