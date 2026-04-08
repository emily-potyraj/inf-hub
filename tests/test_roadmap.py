import pytest

from app.models import BenchmarkVersion, BenchmarkSubmission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_version(db, bv="inferenceX-v3", group="inferenceX", display="InferenceX", is_active=1):
    v = BenchmarkVersion(
        benchmark_version=bv,
        benchmark_group=group,
        display_name=display,
        is_active=is_active,
        sort_order=10,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _seed_submission(db, bv="inferenceX-v3", chip="H100", model="DeepSeekV4", seqlen="1k/1k", status="undecided"):
    s = BenchmarkSubmission(
        benchmark_version=bv,
        chip=chip,
        model=model,
        seqlen=seqlen,
        status=status,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ---------------------------------------------------------------------------
# GET /roadmap/data
# ---------------------------------------------------------------------------

def test_get_roadmap_data_empty(client):
    r = client.get("/roadmap/data")
    assert r.status_code == 200
    data = r.json()
    assert "groups" in data
    assert data["groups"] == []


def test_get_roadmap_data_structure(client, db):
    _seed_version(db)
    _seed_submission(db, seqlen="1k/1k", status="tuning_wip")
    _seed_submission(db, seqlen="8k/1k", status="undecided")

    r = client.get("/roadmap/data")
    assert r.status_code == 200
    data = r.json()

    assert len(data["groups"]) == 1
    group = data["groups"][0]
    assert group["benchmark_group"] == "inferenceX"
    assert len(group["versions"]) == 1

    v = group["versions"][0]
    assert v["benchmark_version"] == "inferenceX-v3"
    assert v["display_name"] == "InferenceX"
    assert v["is_active"] is True
    assert v["chips"] == ["H100"]
    assert v["models"] == ["DeepSeekV4"]
    assert v["targeting_count"] == 1
    assert v["total_count"] == 2

    cells = v["cells"]
    assert "DeepSeekV4" in cells
    assert "H100" in cells["DeepSeekV4"]
    subs = cells["DeepSeekV4"]["H100"]
    assert len(subs) == 2
    # Sorted by seqlen
    assert subs[0]["seqlen"] == "1k/1k"
    assert subs[0]["status"] == "tuning_wip"
    assert subs[1]["seqlen"] == "8k/1k"
    assert subs[1]["status"] == "undecided"


def test_get_roadmap_data_multiple_groups(client, db):
    _seed_version(db, bv="inferenceX-v3", group="inferenceX")
    _seed_version(db, bv="mlperf-v6.1", group="mlperf", display="MLPerf Inference")
    _seed_submission(db, bv="inferenceX-v3")
    _seed_submission(db, bv="mlperf-v6.1", chip="B200", model="Llama3", seqlen="Offline")

    r = client.get("/roadmap/data")
    assert r.status_code == 200
    groups = r.json()["groups"]
    group_names = [g["benchmark_group"] for g in groups]
    assert "inferenceX" in group_names
    assert "mlperf" in group_names


# ---------------------------------------------------------------------------
# PATCH /roadmap/submissions/{id}/status
# ---------------------------------------------------------------------------

def test_patch_status_updates_db(client, db):
    _seed_version(db)
    s = _seed_submission(db)

    r = client.patch(f"/roadmap/submissions/{s.id}/status", json={"status": "targeting"})
    assert r.status_code == 200

    db.refresh(s)
    assert s.status == "targeting"


def test_patch_status_returns_html(client, db):
    _seed_version(db)
    s = _seed_submission(db)

    r = client.patch(f"/roadmap/submissions/{s.id}/status", json={"status": "skip"})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "skip" in r.text


def test_patch_status_not_found(client):
    r = client.patch("/roadmap/submissions/999999/status", json={"status": "targeting"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /roadmap/submissions/{id}/notes
# ---------------------------------------------------------------------------

def test_patch_notes_updates_db(client, db):
    _seed_version(db)
    s = _seed_submission(db)

    r = client.patch(f"/roadmap/submissions/{s.id}/notes", json={"notes": "Need to verify config"})
    assert r.status_code == 200

    db.refresh(s)
    assert s.notes == "Need to verify config"


def test_patch_notes_returns_html(client, db):
    _seed_version(db)
    s = _seed_submission(db)

    r = client.patch(f"/roadmap/submissions/{s.id}/notes", json={"notes": "Test note"})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_patch_notes_clears_notes(client, db):
    _seed_version(db)
    s = _seed_submission(db)
    s.notes = "existing note"
    db.commit()

    r = client.patch(f"/roadmap/submissions/{s.id}/notes", json={"notes": None})
    assert r.status_code == 200

    db.refresh(s)
    assert s.notes is None


def test_patch_notes_not_found(client):
    r = client.patch("/roadmap/submissions/999999/notes", json={"notes": "hi"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /roadmap/versions/{benchmark_version}/dates
# ---------------------------------------------------------------------------

def test_patch_dates_updates_submission_date(client, db):
    _seed_version(db)

    r = client.patch("/roadmap/versions/inferenceX-v3/dates", json={"submission_date": "2026-05-01"})
    assert r.status_code == 200

    db.expire_all()
    v = db.get(BenchmarkVersion, "inferenceX-v3")
    assert v.submission_date == "2026-05-01"


def test_patch_dates_updates_publication_date(client, db):
    _seed_version(db)

    r = client.patch("/roadmap/versions/inferenceX-v3/dates", json={"publication_date": "2026-06-15"})
    assert r.status_code == 200

    db.expire_all()
    v = db.get(BenchmarkVersion, "inferenceX-v3")
    assert v.publication_date == "2026-06-15"


def test_patch_dates_returns_html(client, db):
    _seed_version(db)

    r = client.patch("/roadmap/versions/inferenceX-v3/dates", json={"submission_date": "2026-05-01"})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "2026-05-01" in r.text


def test_patch_dates_not_found(client):
    r = client.patch("/roadmap/versions/nonexistent/dates", json={"submission_date": "2026-01-01"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Unique constraint
# ---------------------------------------------------------------------------

def test_unique_constraint_enforced(db):
    _seed_version(db)
    _seed_submission(db)  # First insert OK

    import sqlalchemy.exc
    with pytest.raises((sqlalchemy.exc.IntegrityError, Exception)):
        s2 = BenchmarkSubmission(
            benchmark_version="inferenceX-v3",
            chip="H100",
            model="DeepSeekV4",
            seqlen="1k/1k",
            status="undecided",
        )
        db.add(s2)
        db.commit()
