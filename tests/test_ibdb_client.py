import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


MOCK_RESPONSE_WITH_DATA = {
    "records": [
        {
            "ts_timestamp": "2025-03-14T09:32:00",
            "s_model_name": "deepseek-r1",
            "s_accelerator_name": "MI355X",
            "d_tput_output_tps_per_acc": 1200.5,
        }
    ]
}

MOCK_RESPONSE_NO_DATA = {
    "records": []
}

NAME_MAP = {
    "models": {"DSR1": "deepseek-r1"},
    "hardware": {"MI355X": "MI355X"},
    "frameworks": {"vLLM": "vLLM-Public"},
}


def _mock_post_with_data(url, **kwargs):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = MOCK_RESPONSE_WITH_DATA
    return mock


def _mock_post_no_data(url, **kwargs):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = MOCK_RESPONSE_NO_DATA
    return mock


def test_check_workload_returns_latest_run_at_when_data_exists(tmp_path, monkeypatch):
    import app.ibdb_client as ibdb_mod
    map_file = tmp_path / "ibdb_name_map.json"
    map_file.write_text(json.dumps(NAME_MAP))
    monkeypatch.setattr(ibdb_mod, "NAME_MAP_PATH", str(map_file))

    with patch("httpx.post", side_effect=_mock_post_with_data):
        result = ibdb_mod.check_workload(
            model="DSR1", hardware="MI355X",
            framework="vLLM", seqlens="2k/2k", token="tok"
        )
    assert result is not None
    assert isinstance(result, datetime)
    assert result.year == 2025


def test_check_workload_uses_rest_body_not_graphql(tmp_path, monkeypatch):
    """Verify request uses session_id in body and REST endpoint (not GraphQL)."""
    import app.ibdb_client as ibdb_mod
    map_file = tmp_path / "ibdb_name_map.json"
    map_file.write_text(json.dumps(NAME_MAP))
    monkeypatch.setattr(ibdb_mod, "NAME_MAP_PATH", str(map_file))

    captured = {}

    def capture_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json", {})
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = MOCK_RESPONSE_WITH_DATA
        return mock

    with patch("httpx.post", side_effect=capture_post):
        ibdb_mod.check_workload(
            model="DSR1", hardware="MI355X",
            framework="vLLM", seqlens="2k/2k", token="mytoken"
        )

    assert captured["url"].endswith("/data"), f"Expected /data endpoint, got: {captured['url']}"
    assert captured["json"]["session_id"] == "mytoken"
    assert "query" not in captured["json"], "Should not send GraphQL query"
    assert captured["json"]["filters"]["s_model_name"] == "deepseek-r1"
    assert captured["json"]["filters"]["s_accelerator_name"] == "MI355X"


def test_check_workload_returns_none_when_no_data(tmp_path, monkeypatch):
    import app.ibdb_client as ibdb_mod
    map_file = tmp_path / "ibdb_name_map.json"
    map_file.write_text(json.dumps(NAME_MAP))
    monkeypatch.setattr(ibdb_mod, "NAME_MAP_PATH", str(map_file))

    with patch("httpx.post", side_effect=_mock_post_no_data):
        result = ibdb_mod.check_workload(
            model="DSR1", hardware="MI355X",
            framework="vLLM", seqlens="2k/2k", token="tok"
        )
    assert result is None


def test_check_workload_returns_none_when_unmapped(tmp_path, monkeypatch):
    import app.ibdb_client as ibdb_mod
    map_file = tmp_path / "ibdb_name_map.json"
    map_file.write_text(json.dumps({"models": {}, "hardware": {}, "frameworks": {}}))
    monkeypatch.setattr(ibdb_mod, "NAME_MAP_PATH", str(map_file))

    result = ibdb_mod.check_workload(
        model="UnknownModel", hardware="UnknownHW",
        framework="vLLM", seqlens="2k/2k", token="tok"
    )
    assert result is None


def test_check_workload_returns_none_on_http_error(tmp_path, monkeypatch):
    import app.ibdb_client as ibdb_mod
    map_file = tmp_path / "ibdb_name_map.json"
    map_file.write_text(json.dumps(NAME_MAP))
    monkeypatch.setattr(ibdb_mod, "NAME_MAP_PATH", str(map_file))

    def fail(*a, **kw):
        raise Exception("connection refused")

    with patch("httpx.post", side_effect=fail):
        result = ibdb_mod.check_workload(
            model="DSR1", hardware="MI355X",
            framework="vLLM", seqlens="2k/2k", token="tok"
        )
    assert result is None
