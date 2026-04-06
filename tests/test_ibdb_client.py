import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# Update s_run_date to the actual field name if discovered in Step 1
_DATE_FIELD = "s_run_date"

MOCK_RESPONSE_WITH_DATA = {
    "data": {
        "getData": [
            {
                _DATE_FIELD: "2025-03-14T09:32:00Z",
                "d_tput_output_tps_per_acc": 1200.5,
            }
        ]
    }
}

MOCK_RESPONSE_NO_DATA = {
    "data": {
        "getData": []
    }
}

NAME_MAP = {
    "models": {"LLaMA3-70B": "llama-3-70b"},
    "hardware": {"MI300X": "mi300x"},
    "frameworks": {"vLLM": "vllm"},
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
            model="LLaMA3-70B", hardware="MI300X",
            framework="vLLM", seqlens="2k/2k", token="tok"
        )
    assert result is not None
    assert isinstance(result, datetime)


def test_check_workload_returns_none_when_no_data(tmp_path, monkeypatch):
    import app.ibdb_client as ibdb_mod
    map_file = tmp_path / "ibdb_name_map.json"
    map_file.write_text(json.dumps(NAME_MAP))
    monkeypatch.setattr(ibdb_mod, "NAME_MAP_PATH", str(map_file))

    with patch("httpx.post", side_effect=_mock_post_no_data):
        result = ibdb_mod.check_workload(
            model="LLaMA3-70B", hardware="MI300X",
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
            model="LLaMA3-70B", hardware="MI300X",
            framework="vLLM", seqlens="2k/2k", token="tok"
        )
    assert result is None
