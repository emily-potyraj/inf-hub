"""IBDB REST client.

Checks whether performance data exists for a workload and returns the
latest run datetime. Returns None if the workload is unmapped, IBDB is
unreachable, or no data exists.

Name resolution order:
  1. Exact match in ibdb_name_map.json
  2. Normalized fuzzy match against live IBDB model list (cached 1h)
  3. Return None (unmapped/no data)
"""
import json
import os
import re
import time
from datetime import datetime
from difflib import get_close_matches
from typing import Optional

import httpx

NAME_MAP_PATH = os.getenv("IBDB_NAME_MAP_PATH", "data/ibdb_name_map.json")
IBDB_URL = os.getenv("IBDB_URL", "https://ibpl-service.nvidia.com/data")

_DATE_FIELD = "ts_timestamp"
_FUZZY_CUTOFF = 0.7
_CACHE_TTL = 3600  # seconds

# Module-level cache for IBDB model names
_model_cache: list = []
_model_cache_time: float = 0


def _normalize(s: str) -> str:
    """Lowercase, strip all non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _load_name_map() -> dict:
    if not os.path.exists(NAME_MAP_PATH):
        return {"models": {}, "hardware": {}, "frameworks": {}}
    with open(NAME_MAP_PATH) as f:
        return json.load(f)


def _fetch_ibdb_models(token: str) -> list:
    """Return all model names available in IBDB. Paginates fully. Cached for _CACHE_TTL seconds."""
    global _model_cache, _model_cache_time
    if _model_cache and (time.time() - _model_cache_time) < _CACHE_TTL:
        return _model_cache
    try:
        all_models: set = set()
        cursor = None
        while True:
            body: dict = {"session_id": token, "filters": {}, "page_size": 500}
            if cursor:
                body["cursor"] = cursor
            resp = httpx.post(IBDB_URL, json=body, timeout=15)
            resp.raise_for_status()
            j = resp.json()
            records = j.get("records", [])
            for r in records:
                m = r.get("s_model_name")
                if m:
                    all_models.add(m)
            cursor = j.get("pagination", {}).get("next_cursor")
            if not cursor or not records:
                break
        _model_cache = list(all_models)
        _model_cache_time = time.time()
    except Exception as exc:
        print(f"[ibdb] failed to fetch model list: {exc}")
    return _model_cache


def _fuzzy_model_match(name: str, token: str) -> Optional[str]:
    """Try to find the best IBDB model name for a given inf-hub model name."""
    ibdb_models = _fetch_ibdb_models(token)
    if not ibdb_models:
        return None

    norm_input = _normalize(name)
    norm_map = {m: _normalize(m) for m in ibdb_models}

    # Substring match: inf-hub name contained in IBDB name or vice versa
    for ibdb_name, norm in norm_map.items():
        if norm_input and (norm_input in norm or norm in norm_input):
            return ibdb_name

    # Difflib closest match on normalized names
    norm_values = list(norm_map.values())
    ibdb_names = list(norm_map.keys())
    matches = get_close_matches(norm_input, norm_values, n=1, cutoff=_FUZZY_CUTOFF)
    if matches:
        return ibdb_names[norm_values.index(matches[0])]

    return None


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

    # Resolve model name: exact map → fuzzy fallback
    ibdb_model = name_map.get("models", {}).get(model)
    if not ibdb_model:
        ibdb_model = _fuzzy_model_match(model, token)

    # Resolve hardware: exact map only (names are stable)
    ibdb_hw = name_map.get("hardware", {}).get(hardware)

    # Resolve framework: exact map only
    ibdb_fw = name_map.get("frameworks", {}).get(framework)

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
        records = resp.json().get("records", [])
    except Exception as exc:
        print(f"[ibdb] check_workload error ({model}/{hardware}): {exc}")
        return None

    if not records:
        return None

    dates = [_parse_run_date(r) for r in records]
    valid = [d for d in dates if d is not None]
    return max(valid) if valid else None
