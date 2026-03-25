import pytest
from itsdangerous import URLSafeTimedSerializer


def test_unauthenticated_read_succeeds(client, auth_client):
    auth_client.post("/workloads", json={
        "model": "DSR1", "hardware": "B200", "framework": "vLLM",
        "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
    })
    r = client.get("/workloads")
    assert r.status_code == 200


def test_unauthenticated_write_returns_401(client):
    r = client.post("/workloads", json={
        "model": "DSR1", "hardware": "B200", "framework": "vLLM",
        "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
    })
    assert r.status_code == 401


def test_expired_session_returns_401(client):
    from app.auth import SESSION_COOKIE_NAME
    bad_s = URLSafeTimedSerializer("wrong-secret")
    payload = {"name": "Old User", "email": "old@nvidia.com"}
    token = bad_s.dumps(payload)
    client.cookies.set(SESSION_COOKIE_NAME, token)
    r = client.post("/workloads", json={
        "model": "DSR1", "hardware": "B200", "framework": "vLLM",
        "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
    })
    assert r.status_code == 401


def test_valid_session_allows_write(auth_client):
    r = auth_client.post("/workloads", json={
        "model": "DSR1", "hardware": "B200", "framework": "vLLM",
        "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
    })
    assert r.status_code == 200


def test_logout_clears_cookie(auth_client):
    r = auth_client.get("/auth/logout")
    assert r.status_code == 200
    assert auth_client.cookies.get("infhub_session") is None or \
           auth_client.cookies.get("infhub_session") == ""
