import pytest

WORKLOAD_BASE = {
    "model": "Llama3",
    "hardware": "B200",
    "framework": "vLLM",
    "precision": "FP8",
    "scenario": "offline",
    "seqlens": "1024",
}


def _mk_workload(db):
    from app.models import Workload
    w = Workload(**WORKLOAD_BASE)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def test_create_comment(client, db):
    w = _mk_workload(db)
    r = client.post(f"/workloads/{w.id}/comments", json={
        "field": "nv_tps",
        "body": "Looks suspiciously high",
        "author": "Alice",
    })
    assert r.status_code == 200
    assert "id" in r.json()


def test_list_comments_for_workload(client, db):
    w = _mk_workload(db)
    from app.models import Comment
    db.add(Comment(workload_id=w.id, field="nv_tps", body="Check this", author="Alice"))
    db.add(Comment(workload_id=w.id, field="amd_tps", body="Other field", author="Bob"))
    db.commit()

    r = client.get(f"/workloads/{w.id}/comments")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    fields = {c["field"] for c in data}
    assert fields == {"nv_tps", "amd_tps"}


def test_add_reply(client, db):
    w = _mk_workload(db)
    from app.models import Comment
    c = Comment(workload_id=w.id, field="nv_tps", body="Root comment", author="Alice")
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.post(f"/comments/{c.id}/replies", json={
        "body": "Acknowledged, will rerun",
        "author": "Bob",
    })
    assert r.status_code == 200
    assert "id" in r.json()

    from app.models import Comment as C
    reply = db.get(C, r.json()["id"])
    assert reply.parent_id == c.id
    assert reply.workload_id == w.id
    assert reply.field == "nv_tps"


def test_resolve_comment(auth_client, db):
    w = _mk_workload(db)
    from app.models import Comment
    c = Comment(workload_id=w.id, field="nv_tps", body="Root comment", author="Alice")
    db.add(c)
    db.commit()
    db.refresh(c)

    r = auth_client.patch(f"/comments/{c.id}/resolve", json={"resolved_by": "Carol"})
    assert r.status_code == 200

    db.refresh(c)
    assert c.resolved_at is not None
    assert c.resolved_by == "Carol"


def test_resolve_requires_auth(client, db):
    w = _mk_workload(db)
    from app.models import Comment
    c = Comment(workload_id=w.id, field="nv_tps", body="Root comment", author="Alice")
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.patch(f"/comments/{c.id}/resolve", json={"resolved_by": "Hacker"})
    assert r.status_code == 401


def test_list_all_open_comments(client, db):
    from datetime import datetime, timezone
    w = _mk_workload(db)
    from app.models import Comment
    db.add(Comment(workload_id=w.id, field="nv_tps", body="Open comment", author="Alice"))
    db.add(Comment(
        workload_id=w.id, field="amd_tps", body="Resolved comment", author="Bob",
        resolved_at=datetime.now(timezone.utc), resolved_by="Carol",
    ))
    db.commit()

    r = client.get("/comments?resolved=false")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["field"] == "nv_tps"
    assert data[0]["resolved_at"] is None


def test_open_comments_includes_replies_nested(client, db):
    w = _mk_workload(db)
    from app.models import Comment
    root = Comment(workload_id=w.id, field="nv_tps", body="Root", author="Alice")
    db.add(root)
    db.commit()
    db.refresh(root)

    reply = Comment(
        workload_id=w.id, field="nv_tps", body="Reply", author="Bob", parent_id=root.id
    )
    db.add(reply)
    db.commit()

    r = client.get("/comments?resolved=false")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1               # only root-level
    assert len(data[0]["replies"]) == 1
    assert data[0]["replies"][0]["body"] == "Reply"


def test_404_on_missing_workload(client):
    r = client.post("/workloads/999999/comments", json={
        "field": "nv_tps",
        "body": "Ghost comment",
    })
    assert r.status_code == 404
