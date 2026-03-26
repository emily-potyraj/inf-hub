import io
import json
import pytest

# Minimal IBDB HTML with 2 hardware series.
IBDB_HTML = '''<div><div id="c" class="plotly-graph-div"></div>
<script>Plotly.newPlot("c",[
  {"legendgroup":"H200","name":"Accelerator: H200","x":[50.0,100.0],"y":[30.0,20.0],
   "text":["H200<br> Precision: FP8<br> Concurrency: 4","H200<br> Precision: FP8<br> Concurrency: 8"]},
  {"legendgroup":"B200","name":"Accelerator: B200","x":[80.0,160.0],"y":[50.0,35.0],
   "text":["B200<br> Precision: FP8<br> Concurrency: 4","B200<br> Precision: FP8<br> Concurrency: 8"]}
],{},{})</script></div>'''

SCENE_BASE = {"name": "Test Scene", "model": "deepseek-r1", "seqlen": "128K/8K"}


def _upload_file(client, scene_id, selected_labels=None, html=IBDB_HTML):
    if selected_labels is None:
        selected_labels = ["H200", "B200"]
    return client.post(
        f"/devzone/scenes/{scene_id}/curves",
        files={"file": ("export.html", io.BytesIO(html.encode()), "text/html")},
        data={"selected_labels": json.dumps(selected_labels)},
    )


# --- Scene CRUD ---

def test_create_scene_requires_auth(client):
    r = client.post("/devzone/scenes", json=SCENE_BASE)
    assert r.status_code == 401


def test_create_scene_success(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Test Scene"
    assert data["model"] == "deepseek-r1"
    assert data["seqlen"] == "128K/8K"
    assert "id" in data


def test_list_scenes_open(auth_client, client):
    auth_client.post("/devzone/scenes", json=SCENE_BASE)
    r = client.get("/devzone/scenes")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Scene"


def test_list_scenes_empty(client):
    r = client.get("/devzone/scenes")
    assert r.status_code == 200
    assert r.json() == []


def test_patch_scene_name_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = client.patch(f"/devzone/scenes/{scene_id}/name", json={"name": "New Name"})
    assert r2.status_code == 401


def test_patch_scene_name_any_authenticated_user(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = auth_client.patch(f"/devzone/scenes/{scene_id}/name", json={"name": "Renamed"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "Renamed"


def test_patch_scene_name_404(auth_client):
    r = auth_client.patch("/devzone/scenes/nonexistent/name", json={"name": "x"})
    assert r.status_code == 404


def test_delete_scene_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = client.delete(f"/devzone/scenes/{scene_id}")
    assert r2.status_code == 401


def test_delete_scene_creator_can_delete(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = auth_client.delete(f"/devzone/scenes/{scene_id}")
    assert r2.status_code == 200
    # Verify gone
    r3 = auth_client.get("/devzone/scenes")
    assert r3.json() == []


def test_delete_scene_non_creator_forbidden(auth_client, db):
    # Create scene attributed to a different user
    from app.models import DevzoneScene
    import uuid
    scene = DevzoneScene(
        id=str(uuid.uuid4()),
        name="Other's scene",
        model="deepseek-r1",
        seqlen="1K/1K",
        created_by="Other User",
        created_by_email="other@nvidia.com",
    )
    db.add(scene)
    db.commit()

    r = auth_client.delete(f"/devzone/scenes/{scene.id}")
    assert r.status_code == 403


def test_publish_scene(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = auth_client.patch(f"/devzone/scenes/{scene_id}/publish")
    assert r2.status_code == 200
    assert r2.json()["is_published"] == 1
    assert r2.json()["published_at"] is not None


def test_publish_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = client.patch(f"/devzone/scenes/{scene_id}/publish")
    assert r2.status_code == 401


# --- Curves ---

def test_preview_curves_returns_series(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = auth_client.post(
        f"/devzone/scenes/{scene_id}/curves/preview",
        files={"file": ("export.html", io.BytesIO(IBDB_HTML.encode()), "text/html")},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert len(data) == 2
    labels = {s["label"] for s in data}
    assert labels == {"H200", "B200"}
    assert all(s["point_count"] == 2 for s in data)
    assert all(s["duplicate"] is False for s in data)


def test_preview_curves_flags_duplicate(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    # Add H200 curve first
    _upload_file(auth_client, scene_id, selected_labels=["H200"])
    # Preview again — H200 should now be flagged as duplicate
    r2 = auth_client.post(
        f"/devzone/scenes/{scene_id}/curves/preview",
        files={"file": ("export.html", io.BytesIO(IBDB_HTML.encode()), "text/html")},
    )
    data = r2.json()
    h200 = next(s for s in data if s["label"] == "H200")
    b200 = next(s for s in data if s["label"] == "B200")
    assert h200["duplicate"] is True
    assert b200["duplicate"] is False


def test_add_curves_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = client.post(
        f"/devzone/scenes/{scene_id}/curves",
        files={"file": ("export.html", io.BytesIO(IBDB_HTML.encode()), "text/html")},
        data={"selected_labels": json.dumps(["H200"])},
    )
    assert r2.status_code == 401


def test_add_curves_success(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = _upload_file(auth_client, scene_id)
    assert r2.status_code == 200
    data = r2.json()
    assert len(data) == 2
    labels = {c["label"] for c in data}
    assert labels == {"H200", "B200"}


def test_add_curves_respects_selected_labels(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = _upload_file(auth_client, scene_id, selected_labels=["H200"])
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["label"] == "H200"


def test_add_curves_duplicate_adds_second(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    _upload_file(auth_client, scene_id, selected_labels=["H200"])
    # Add H200 again — should succeed, yielding 2 H200 curves
    r2 = _upload_file(auth_client, scene_id, selected_labels=["H200"])
    assert r2.status_code == 200
    assert len(r2.json()) == 2
    assert all(c["label"].startswith("H200") for c in r2.json())


def test_add_curves_scene_not_found(auth_client):
    r = _upload_file(auth_client, "nonexistent-id")
    assert r.status_code == 404


def test_delete_curve_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    curves = _upload_file(auth_client, scene_id, selected_labels=["H200"]).json()
    curve_id = curves[0]["id"]
    r2 = client.delete(f"/devzone/curves/{curve_id}")
    assert r2.status_code == 401


def test_delete_curve_success(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    curves = _upload_file(auth_client, scene_id, selected_labels=["H200"]).json()
    curve_id = curves[0]["id"]
    r2 = auth_client.delete(f"/devzone/curves/{curve_id}")
    assert r2.status_code == 200


def test_export_scene_json(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    _upload_file(auth_client, scene_id)
    r2 = auth_client.get(f"/devzone/scenes/{scene_id}/export")
    assert r2.status_code == 200
    data = r2.json()
    assert data["scene_name"] == "Test Scene"
    assert data["model"] == "deepseek-r1"
    assert len(data["curves"]) == 2
    assert "points" in data["curves"][0]
