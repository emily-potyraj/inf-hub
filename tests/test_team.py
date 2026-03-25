def test_create_team_function(auth_client):
    r = auth_client.post("/team/functions", json={
        "function": "srt-slurm PR approvals",
        "owner": "weiliang",
        "backup": "alice",
    })
    assert r.status_code == 200
    assert r.json()["function"] == "srt-slurm PR approvals"


def test_list_team_functions(auth_client):
    auth_client.post("/team/functions", json={"function": "AMD monitoring", "owner": "bob"})
    auth_client.post("/team/functions", json={"function": "SA relationship", "owner": "carol"})
    r = auth_client.get("/team/functions")
    assert len(r.json()) == 2


def test_update_team_function(auth_client):
    r = auth_client.post("/team/functions", json={"function": "AMD monitoring", "owner": "bob"})
    fn_id = r.json()["id"]
    r2 = auth_client.patch(f"/team/functions/{fn_id}", json={"owner": "dan"})
    assert r2.json()["owner"] == "dan"


def test_team_functions_require_auth(client):
    r = client.post("/team/functions", json={"function": "AMD monitoring"})
    assert r.status_code == 401
