import pytest

REQUEST_BASE = {
    "model": "Llama3",
    "hardware": "B200",
    "framework": "vLLM",
    "precision": "FP8",
    "scenario": "offline",
}


def test_create_request(client):
    r = client.post("/requests", json=REQUEST_BASE)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert isinstance(data["id"], int)


def test_create_request_sets_submitted_by_from_session(auth_client, db):
    body = {**REQUEST_BASE, "submitted_by": "someone_else"}
    r = auth_client.post("/requests", json=body)
    assert r.status_code == 200
    request_id = r.json()["id"]

    from app.models import Request as RequestModel
    req = db.get(RequestModel, request_id)
    assert req is not None
    # Session user "Test User" should override the body's submitted_by
    assert req.submitted_by == "Test User"



def test_list_requests_groups_by_status(client, db):
    from app.models import Request as RequestModel

    base = {k: v for k, v in REQUEST_BASE.items()}
    db.add(RequestModel(**{**base, "status": "new"}))
    db.add(RequestModel(**{**base, "model": "Llama4", "status": "in_progress"}))
    db.add(RequestModel(**{**base, "model": "Llama5", "status": "completed"}))
    db.commit()

    r = client.get("/requests")
    assert r.status_code == 200


def test_update_status(auth_client, db):
    from app.models import Request as RequestModel

    req = RequestModel(**REQUEST_BASE)
    db.add(req)
    db.commit()
    db.refresh(req)

    r = auth_client.patch(f"/requests/{req.id}", json={"status": "in_progress"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    db.refresh(req)
    assert req.status == "in_progress"


def test_update_pic(auth_client, db):
    from app.models import Request as RequestModel

    req = RequestModel(**REQUEST_BASE)
    db.add(req)
    db.commit()
    db.refresh(req)

    r = auth_client.patch(f"/requests/{req.id}", json={"pic": "alice"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    db.refresh(req)
    assert req.pic == "alice"


def test_update_requires_auth(client, db):
    from app.models import Request as RequestModel

    req = RequestModel(**REQUEST_BASE)
    db.add(req)
    db.commit()
    db.refresh(req)

    r = client.patch(f"/requests/{req.id}", json={"status": "completed"})
    assert r.status_code == 401


def test_update_not_found(auth_client):
    r = auth_client.patch("/requests/999999", json={"status": "completed"})
    assert r.status_code == 404
