"""IBDB REST client.

Checks whether performance data exists for a workload and returns the
latest run datetime. Returns None if the workload is unmapped, IBDB is
unreachable, or no data exists.
"""
import json
import os
from datetime import datetime
from typing import Optional

import httpx

NAME_MAP_PATH = os.getenv("IBDB_NAME_MAP_PATH", "data/ibdb_name_map.json")
IBDB_URL = os.getenv("IBDB_URL", "https://ibpl-service.nvidia.com/data")

_DATE_FIELD = "ts_timestamp"


def _load_name_map() -> dict:
    if not os.path.exists(NAME_MAP_PATH):
        return {"models": {}, "hardware": {}, "frameworks": {}}
    with open(NAME_MAP_PATH) as f:
        return json.load(f)


def _parse_run_date(record: dict) -> Optional[datetime]:
    raw = record.get(_DATE_FIELD)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def check_workload(
    model: str,
    hardware: str,
    framework: str,
    seqlens: str,
    token: str,
) -> Optional[datetime]:
    """Return the latest run datetime from IBDB, or None if no data / unmapped / error."""
    name_map = _load_name_map()
    ibdb_model = name_map.get("models", {}).get(model)
    ibdb_hw    = name_map.get("hardware", {}).get(hardware)
    ibdb_fw    = name_map.get("frameworks", {}).get(framework)

    if not ibdb_model or not ibdb_hw:
        return None  # unmapped — skip quietly

    filters: dict = {
        "s_model_name": ibdb_model,
        "s_accelerator_name": ibdb_hw,
    }
    if ibdb_fw:
        filters["s_framework_name"] = ibdb_fw

    try:
        resp = httpx.post(
            IBDB_URL,
            json={
                "session_id": token,
                "filters": filters,
                "page_size": 100,
            },
            timeout=15,
        )
        resp.raise_for_status()
        records = resp.json().get("data", [])
    except Exception as exc:
        print(f"[ibdb] check_workload error ({model}/{hardware}): {exc}")
        return None

    if not records:
        return None

    dates = [_parse_run_date(r) for r in records]
    valid = [d for d in dates if d is not None]
    return max(valid) if valid else None
