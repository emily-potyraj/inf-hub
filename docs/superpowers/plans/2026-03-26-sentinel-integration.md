# Sentinel Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate InferenceX Sentinel's `data.json` into inf-hub to auto-populate `amd_tps` with provenance tracking, surface Sentinel threat-level badges on workload rows and detail pages, and enable AMD curve imports into devzone scenes with one-click workload linkage.

**Architecture:** A new `app/routers/sentinel.py` module contains the core `sync_sentinel(db)` function, two API endpoints (`POST /sentinel/sync`, `GET /sentinel/status`), and an HTMX fragment endpoint for the footer status block. APScheduler (new dep) runs `sync_sentinel` daily in a background thread using a dedicated DB session. Name mapping is a committed JSON config file; results are cached in a JSON sync log on disk. The devzone router gains a `GET /devzone/sentinel-analyses` lookup endpoint and a `POST /devzone/scenes/{id}/curves/sentinel` import endpoint.

**Tech Stack:** FastAPI, SQLAlchemy (sync), Alembic, HTMX, httpx (already installed), APScheduler (new), Jinja2, SQLite, Plotly (existing in devzone)

---

## File Map

### New
- `data/sentinel_mappings.json` — name-mapping config (model/hardware Sentinel→inf-hub)
- `app/routers/sentinel.py` — sync logic, API endpoints, status fragment
- `alembic/versions/<rev>_add_sentinel_columns.py` — migration

### Modified
- `app/models.py` — 7 new columns on `Workload`, 1 new column on `DevzoneCurve`
- `app/schemas.py` — extend `WorkloadRow` + `DevzoneCurveRow` with new fields
- `app/routers/workloads.py` — set `amd_tps_source="manual"` when `amd_tps` is PATCHed
- `app/routers/devzone.py` — `GET /devzone/sentinel-analyses`, `POST /devzone/scenes/{id}/curves/sentinel`
- `app/main.py` — register sentinel router, APScheduler startup/shutdown
- `app/templates/base.html` — Sentinel status block in footer
- `app/templates/index.html` — add `Sentinel` column `<th>`, update colspan
- `app/templates/partials/workload_row.html` — add Sentinel badge `<td>`
- `app/templates/workload_detail.html` — add Sentinel section to right panel
- `app/templates/devzone.html` — Import from Sentinel tab in Add Curves modal + workload link in curve table
- `requirements.txt` — add `apscheduler`

### New Tests
- `tests/test_sentinel.py`

---

## Task 1: Alembic Migration

**Files:**
- Create: `alembic/versions/<rev>_add_sentinel_columns.py`

- [ ] **Step 1: Generate migration file**

```bash
cd /Users/epotyraj/Documents/inf-hub
alembic revision --autogenerate -m "add_sentinel_columns"
```

Note the generated `<rev>` ID in the filename.

- [ ] **Step 2: Replace generated body with explicit column additions**

Open the generated file and replace the `upgrade()` and `downgrade()` functions with:

```python
def upgrade() -> None:
    # Sentinel columns on workloads
    op.add_column('workloads', sa.Column('amd_tps_source', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('amd_tps_sentinel_value', sa.Float(), nullable=True))
    op.add_column('workloads', sa.Column('amd_tps_synced_at', sa.DateTime(), nullable=True))
    op.add_column('workloads', sa.Column('sentinel_threat_level', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('sentinel_summary', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('sentinel_image_url', sa.Text(), nullable=True))
    op.add_column('workloads', sa.Column('sentinel_synced_at', sa.DateTime(), nullable=True))
    # Workload linkage on devzone_curves
    op.add_column('devzone_curves', sa.Column('inf_hub_workload_id', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('devzone_curves', 'inf_hub_workload_id')
    op.drop_column('workloads', 'sentinel_synced_at')
    op.drop_column('workloads', 'sentinel_image_url')
    op.drop_column('workloads', 'sentinel_summary')
    op.drop_column('workloads', 'sentinel_threat_level')
    op.drop_column('workloads', 'amd_tps_synced_at')
    op.drop_column('workloads', 'amd_tps_sentinel_value')
    op.drop_column('workloads', 'amd_tps_source')
```

- [ ] **Step 3: Run migration and verify**

```bash
alembic upgrade head
```

Expected: `Running upgrade ... -> <rev>, add_sentinel_columns`

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add sentinel columns migration"
```

---

## Task 2: SQLAlchemy Models

**Files:**
- Modify: `app/models.py`

- [ ] **Step 1: Add sentinel columns to `Workload` class**

Read `app/models.py` and locate the `Workload` class. After the `amd_tps` column, add:

```python
amd_tps_source          = Column(Text)          # 'manual' | 'sentinel'
amd_tps_sentinel_value  = Column(Float)
amd_tps_synced_at       = Column(DateTime)
sentinel_threat_level   = Column(Text)           # 'GREEN' | 'YELLOW' | 'RED'
sentinel_summary        = Column(Text)
sentinel_image_url      = Column(Text)
sentinel_synced_at      = Column(DateTime)
```

- [ ] **Step 2: Add `inf_hub_workload_id` to `DevzoneCurve` class**

Locate the `DevzoneCurve` class. After `uploaded_at`, add:

```python
inf_hub_workload_id = Column(Text)   # nullable FK to workloads.id, app-enforced
```

- [ ] **Step 3: Verify app starts cleanly**

```bash
python -c "from app.models import Workload, DevzoneCurve; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/models.py
git commit -m "feat: add sentinel columns to Workload and DevzoneCurve models"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Modify: `app/schemas.py`

- [ ] **Step 1: Extend `WorkloadRow` with Sentinel fields**

Read `app/schemas.py`. In the `WorkloadRow` class, after `work_type` and `study_id`, add:

```python
amd_tps_source:         Optional[str]   = None
amd_tps_sentinel_value: Optional[float] = None
amd_tps_synced_at:      Optional[str]   = None  # ISO string
sentinel_threat_level:  Optional[str]   = None
sentinel_summary:       Optional[str]   = None
sentinel_image_url:     Optional[str]   = None
sentinel_synced_at:     Optional[str]   = None  # ISO string
```

- [ ] **Step 2: Update `_to_row()` in workloads.py to serialize new fields**

Read `app/routers/workloads.py` and find `_to_row(w: Workload) -> WorkloadRow`. The function constructs a `WorkloadRow` from a `Workload`. Extend it to include the new fields:

```python
amd_tps_source=w.amd_tps_source,
amd_tps_sentinel_value=w.amd_tps_sentinel_value,
amd_tps_synced_at=w.amd_tps_synced_at.isoformat() if w.amd_tps_synced_at else None,
sentinel_threat_level=w.sentinel_threat_level,
sentinel_summary=w.sentinel_summary,
sentinel_image_url=w.sentinel_image_url,
sentinel_synced_at=w.sentinel_synced_at.isoformat() if w.sentinel_synced_at else None,
```

- [ ] **Step 3: Extend `DevzoneCurveRow` with `inf_hub_workload_id`**

In `app/schemas.py`, in `DevzoneCurveRow`, add:

```python
inf_hub_workload_id: Optional[str] = None
```

- [ ] **Step 4: Run existing tests to confirm no regressions**

```bash
pytest tests/ -x -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py app/routers/workloads.py
git commit -m "feat: extend WorkloadRow and DevzoneCurveRow schemas with sentinel fields"
```

---

## Task 4: Create Sentinel Mappings Config

**Files:**
- Create: `data/sentinel_mappings.json`

- [ ] **Step 1: Create the mappings file**

```bash
mkdir -p data
```

Create `data/sentinel_mappings.json` with this content:

```json
{
  "models": {
    "DeepSeek-R1": "DSR1",
    "Llama 3.1 70B": "Llama3-70B",
    "Llama 3.1 8B": "Llama3-8B",
    "Llama 3.1 405B": "Llama3-405B",
    "Mistral 7B": "Mistral7B",
    "Mixtral 8x7B": "Mixtral8x7B",
    "Qwen2.5 72B": "Qwen2.5-72B"
  },
  "hardware": {
    "B200": "B200",
    "H200": "H200",
    "H100": "H100",
    "GB200": "GB200",
    "GB300": "GB300",
    "GB300 NVL": "GB300",
    "B100": "B100",
    "B300": "B300"
  }
}
```

Note: this is a starter set. Engineers add entries as unmatched names appear in `sentinel_sync_log.json`.

- [ ] **Step 2: Commit**

```bash
git add data/sentinel_mappings.json
git commit -m "feat: add initial sentinel_mappings.json config"
```

---

## Task 5: Patch `amd_tps` to Set `amd_tps_source = "manual"`

**Files:**
- Modify: `app/routers/workloads.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_workloads.py`:

```python
def test_patch_amd_tps_sets_source_manual(auth_client):
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/amd_tps", json={"value": 1500.0})
    r2 = auth_client.get(f"/workloads/{w_id}")
    assert r2.json()["amd_tps_source"] == "manual"
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_workloads.py::test_patch_amd_tps_sets_source_manual -v
```

Expected: FAIL (field not set or KeyError).

- [ ] **Step 3: Update `update_field()` in workloads.py**

In `app/routers/workloads.py`, locate the `update_field()` function. Find the line where `setattr(workload, field, typed_value)` is called (or wherever the field value is applied to the workload object). Immediately after that line, add:

```python
if field == "amd_tps":
    workload.amd_tps_source = "manual"
```

- [ ] **Step 4: Run to verify it passes**

```bash
pytest tests/test_workloads.py::test_patch_amd_tps_sets_source_manual -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
pytest tests/ -x -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/routers/workloads.py tests/test_workloads.py
git commit -m "feat: set amd_tps_source=manual when amd_tps is patched by a user"
```

---

## Task 6: `app/routers/sentinel.py`

**Files:**
- Create: `app/routers/sentinel.py`
- Create: `tests/test_sentinel.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sentinel.py`:

```python
import json
import os
import pytest
from unittest.mock import patch, MagicMock

WORKLOAD_BASE = {
    "model": "DSR1", "hardware": "B200", "framework": "TRT-LLM",
    "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
}

MOCK_SENTINEL_DATA = {
    "analyses": [
        {
            "model_tested": "DeepSeek-R1",
            "nvidia_gpus": ["B200"],
            "amd_gpus": ["MI300X"],
            "isl": "1K / 1K",
            "overall_threat_level": "RED",
            "summary": "AMD ahead on throughput by ~14%",
            "image_url": "images/chart_dsr1_b200.jpg",
            "tab": "Inference Performance",
            "comparisons": [
                {
                    "nvidia_gpu": "B200",
                    "amd_gpu": "MI300X",
                    "metric": "throughput",
                    "nvidia_value": "1840",
                    "amd_value": "2100",
                    "winner": "AMD_WINNING",
                    "delta_description": "AMD ahead by ~14%",
                }
            ],
        }
    ]
}

MOCK_MAPPINGS = {
    "models": {"DeepSeek-R1": "DSR1"},
    "hardware": {"B200": "B200"},
}


@pytest.fixture(autouse=True)
def mock_mappings_and_log(tmp_path, monkeypatch):
    mappings_file = tmp_path / "sentinel_mappings.json"
    mappings_file.write_text(json.dumps(MOCK_MAPPINGS))
    log_file = tmp_path / "sentinel_sync_log.json"
    monkeypatch.setenv("SENTINEL_DATA_URL", "https://sentinel.example.com")
    import app.routers.sentinel as sentinel_mod
    monkeypatch.setattr(sentinel_mod, "MAPPINGS_PATH", str(mappings_file))
    monkeypatch.setattr(sentinel_mod, "SYNC_LOG_PATH", str(log_file))
    yield log_file


def _mock_httpx_get(url, timeout=30):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = MOCK_SENTINEL_DATA
    return mock


def test_sync_populates_sentinel_fields(auth_client, db, monkeypatch):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    with patch("httpx.get", side_effect=_mock_httpx_get):
        r = auth_client.post("/sentinel/sync")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] == 1
    wl = auth_client.get("/workloads/1").json()
    assert wl["sentinel_threat_level"] == "RED"
    assert wl["sentinel_summary"] == "AMD ahead on throughput by ~14%"
    assert "images/chart_dsr1_b200.jpg" in wl["sentinel_image_url"]
    assert wl["sentinel_synced_at"] is not None


def test_sync_sets_amd_tps_when_null(auth_client, db, monkeypatch):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    wl = auth_client.get("/workloads/1").json()
    assert wl["amd_tps"] == 2100.0
    assert wl["amd_tps_source"] == "sentinel"
    assert wl["amd_tps_sentinel_value"] == 2100.0


def test_sync_does_not_overwrite_manual_amd_tps(auth_client, db, monkeypatch):
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/amd_tps", json={"value": 9999.0})
    # amd_tps_source is now "manual"
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    wl = auth_client.get(f"/workloads/{w_id}").json()
    assert wl["amd_tps"] == 9999.0            # unchanged
    assert wl["amd_tps_source"] == "manual"   # unchanged
    assert wl["amd_tps_sentinel_value"] == 2100.0  # Sentinel value stored separately


def test_sync_records_divergence_in_log(auth_client, db, monkeypatch, mock_mappings_and_log):
    r = auth_client.post("/workloads", json=WORKLOAD_BASE)
    w_id = r.json()["id"]
    auth_client.patch(f"/workloads/{w_id}/amd_tps", json={"value": 9999.0})
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    log = json.loads(mock_mappings_and_log.read_text())
    assert len(log["manual_divergences"]) == 1
    assert log["manual_divergences"][0]["manual_value"] == 9999.0
    assert log["manual_divergences"][0]["sentinel_value"] == 2100.0


def test_sync_writes_audit_log_entry(auth_client, db, monkeypatch):
    auth_client.post("/workloads", json=WORKLOAD_BASE)
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    audit = auth_client.get("/workloads/1/audit").json()
    amd_entries = [e for e in audit if e["field_name"] == "amd_tps"]
    assert any(e["user_name"] == "sentinel-sync" for e in amd_entries)


def test_sync_records_unmatched_model(auth_client, monkeypatch, mock_mappings_and_log, tmp_path):
    # Mappings have no entry for "UnknownModel"
    import app.routers.sentinel as sentinel_mod
    bad_mappings = tmp_path / "bad_mappings.json"
    bad_mappings.write_text(json.dumps({"models": {}, "hardware": {}}))
    monkeypatch.setattr(sentinel_mod, "MAPPINGS_PATH", str(bad_mappings))
    with patch("httpx.get", side_effect=_mock_httpx_get):
        auth_client.post("/sentinel/sync")
    log = json.loads(mock_mappings_and_log.read_text())
    assert "DeepSeek-R1" in log["unmatched_models"]


def test_sync_fetch_failure_writes_error_log(auth_client, monkeypatch, mock_mappings_and_log):
    def fail(*a, **kw):
        raise Exception("connection refused")
    with patch("httpx.get", side_effect=fail):
        r = auth_client.post("/sentinel/sync")
    assert r.status_code == 200
    log = json.loads(mock_mappings_and_log.read_text())
    assert "error" in log


def test_sync_requires_auth(client):
    r = client.post("/sentinel/sync")
    assert r.status_code == 401


def test_get_status_returns_log(auth_client, monkeypatch, mock_mappings_and_log):
    mock_mappings_and_log.write_text(json.dumps({"timestamp": "2026-03-26T06:00:00Z", "matched": 5}))
    r = auth_client.get("/sentinel/status")
    assert r.status_code == 200
    assert r.json()["matched"] == 5


def test_get_status_when_no_log(auth_client, monkeypatch, tmp_path):
    import app.routers.sentinel as sentinel_mod
    monkeypatch.setattr(sentinel_mod, "SYNC_LOG_PATH", str(tmp_path / "nonexistent.json"))
    r = auth_client.get("/sentinel/status")
    assert r.status_code == 200
    assert r.json()["matched"] == 0
```

- [ ] **Step 2: Run to verify all fail**

```bash
pytest tests/test_sentinel.py -v
```

Expected: all FAIL (module not found).

- [ ] **Step 3: Check how `database.py` exports `SessionLocal`**

```bash
grep -n "SessionLocal\|sessionmaker" app/database.py
```

If `SessionLocal` is not exported, note the session factory name — you'll use it in Step 4.

- [ ] **Step 4: Create `app/routers/sentinel.py`**

```python
import json
import os
import re
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth import require_auth
from app.database import get_db
from app.models import AuditLog, Workload

router = APIRouter(prefix="/sentinel", tags=["sentinel"])
templates = Jinja2Templates(directory="app/templates")

MAPPINGS_PATH = os.getenv("SENTINEL_MAPPINGS_PATH", "data/sentinel_mappings.json")
SYNC_LOG_PATH = os.getenv("SENTINEL_SYNC_LOG_PATH", "data/sentinel_sync_log.json")


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_mappings() -> dict:
    if not os.path.exists(MAPPINGS_PATH):
        return {"models": {}, "hardware": {}}
    with open(MAPPINGS_PATH) as f:
        return json.load(f)


def _normalize_seqlen(s: str) -> str:
    """'8K / 1K' -> '8k/1k'"""
    return s.replace(" ", "").lower()


def _parse_numeric(s) -> Optional[float]:
    """Extract first number from a string: '1840 tok/s' -> 1840.0, 94.3 -> 94.3"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"[\d]+(?:\.\d+)?", str(s))
    return float(m.group()) if m else None


def _write_log(result: dict) -> None:
    os.makedirs(os.path.dirname(SYNC_LOG_PATH) or ".", exist_ok=True)
    with open(SYNC_LOG_PATH, "w") as f:
        json.dump(result, f, indent=2)


# ── Core sync ──────────────────────────────────────────────────────────────

def sync_sentinel(db: Session) -> dict:
    """Fetch Sentinel data.json, match to workloads, write sentinel fields.
    Returns the sync result dict (also written to SYNC_LOG_PATH).
    Safe to call even if Sentinel is unreachable — failure is logged, no DB writes occur.
    """
    sentinel_url = os.getenv("SENTINEL_DATA_URL", "").rstrip("/")
    if not sentinel_url:
        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": "SENTINEL_DATA_URL not configured",
            "analyses_total": 0,
            "matched": 0,
            "unmatched_models": [],
            "unmatched_hardware": [],
            "manual_divergences": [],
        }
        _write_log(result)
        return result

    # Step 1: Fetch
    try:
        resp = httpx.get(f"{sentinel_url}/data/data.json", timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": str(exc),
            "analyses_total": 0,
            "matched": 0,
            "unmatched_models": [],
            "unmatched_hardware": [],
            "manual_divergences": [],
        }
        _write_log(result)
        return result

    # Step 2: Mappings
    mappings = _load_mappings()
    model_map: dict = mappings.get("models", {})
    hw_map: dict = mappings.get("hardware", {})

    analyses = data.get("analyses", [])
    matched = 0
    unmatched_models: set = set()
    unmatched_hardware: set = set()
    manual_divergences: list = []

    # Step 3+4: Match and write
    now = datetime.utcnow()

    for analysis in analyses:
        raw_model = (analysis.get("model_tested") or "").strip()
        inf_model = model_map.get(raw_model)
        if not inf_model:
            if raw_model:
                unmatched_models.add(raw_model)
            continue

        raw_isl = analysis.get("isl", "")
        inf_seqlen = _normalize_seqlen(raw_isl) if raw_isl else None

        for raw_hw in analysis.get("nvidia_gpus", []):
            inf_hw = hw_map.get(raw_hw.strip())
            if not inf_hw:
                unmatched_hardware.add(raw_hw.strip())
                continue

            # Match workload: model + hardware required; seqlen tiebreaker
            q = db.query(Workload).filter(
                Workload.model == inf_model,
                Workload.hardware == inf_hw,
            )
            if inf_seqlen:
                workload = q.filter(Workload.seqlens == inf_seqlen).first() or q.first()
            else:
                workload = q.first()

            if not workload:
                continue

            # Find best amd_value: prefer comparison whose amd_gpu maps to a known hw
            best_amd_value: Optional[float] = None
            for comp in analysis.get("comparisons", []):
                val = _parse_numeric(comp.get("amd_value"))
                if val is None:
                    continue
                if best_amd_value is None:
                    best_amd_value = val
                if hw_map.get((comp.get("amd_gpu") or "").strip()):
                    best_amd_value = val
                    break

            # Always write sentinel metadata fields
            image_url = analysis.get("image_url", "")
            if image_url and not image_url.startswith("http"):
                image_url = f"{sentinel_url}/{image_url.lstrip('/')}"

            workload.sentinel_threat_level = analysis.get("overall_threat_level")
            workload.sentinel_summary = (analysis.get("summary") or "")[:500]
            workload.sentinel_image_url = image_url
            workload.sentinel_synced_at = now

            if best_amd_value is not None:
                workload.amd_tps_sentinel_value = best_amd_value
                workload.amd_tps_synced_at = now

                if workload.amd_tps_source in (None, "sentinel"):
                    old_val = workload.amd_tps
                    workload.amd_tps = best_amd_value
                    workload.amd_tps_source = "sentinel"
                    db.add(AuditLog(
                        workload_id=workload.id,
                        user_name="sentinel-sync",
                        user_email="sentinel-sync",
                        field_name="amd_tps",
                        old_value=str(old_val) if old_val is not None else None,
                        new_value=str(best_amd_value),
                    ))
                else:
                    # Manual value — check divergence
                    if workload.amd_tps is not None:
                        diff = abs(best_amd_value - workload.amd_tps) / workload.amd_tps
                        if diff > 0.05:
                            manual_divergences.append({
                                "workload_id": workload.id,
                                "sentinel_value": best_amd_value,
                                "manual_value": workload.amd_tps,
                            })

            matched += 1

    db.commit()

    result = {
        "timestamp": now.isoformat() + "Z",
        "analyses_total": len(analyses),
        "matched": matched,
        "unmatched_models": sorted(unmatched_models),
        "unmatched_hardware": sorted(unmatched_hardware),
        "manual_divergences": manual_divergences,
    }
    _write_log(result)
    return result


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db), user=Depends(require_auth)):
    return sync_sentinel(db)


@router.get("/status")
def get_status():
    if os.path.exists(SYNC_LOG_PATH):
        with open(SYNC_LOG_PATH) as f:
            return json.load(f)
    return {
        "timestamp": None,
        "analyses_total": 0,
        "matched": 0,
        "unmatched_models": [],
        "unmatched_hardware": [],
        "manual_divergences": [],
    }


@router.get("/status-fragment", response_class=HTMLResponse)
def status_fragment(request: Request):
    status = get_status()
    user = getattr(request.state, "user", None)
    return templates.TemplateResponse(
        "partials/sentinel_status.html",
        {"request": request, "status": status, "user": user},
    )
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_sentinel.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/sentinel.py tests/test_sentinel.py
git commit -m "feat: add sentinel sync module with provenance tracking"
```

---

## Task 7: Register Sentinel Router + APScheduler

**Files:**
- Modify: `app/main.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add `apscheduler` to requirements.txt**

Open `requirements.txt` and add:

```
apscheduler==3.10.4
```

Then install:

```bash
pip install apscheduler==3.10.4
```

- [ ] **Step 2: Register sentinel router and APScheduler in `main.py`**

Read `app/main.py`. Add the following imports near the top with the other router imports:

```python
import os
from apscheduler.schedulers.background import BackgroundScheduler
from app.routers import sentinel as sentinel_router
from app.database import SessionLocal
```

Register the router (with the other `app.include_router` calls):

```python
app.include_router(sentinel_router.router)
```

Add scheduler startup/shutdown (using FastAPI lifespan events; if the app uses `@app.on_event`, follow that pattern — otherwise use `lifespan`):

```python
_scheduler = BackgroundScheduler(daemon=True)


def _run_daily_sentinel_sync() -> None:
    """Called by APScheduler in a background thread."""
    db = SessionLocal()
    try:
        sentinel_router.sync_sentinel(db)
    except Exception as exc:
        print(f"[sentinel] daily sync error: {exc}")
    finally:
        db.close()


@app.on_event("startup")
def start_sentinel_scheduler() -> None:
    hour = int(os.getenv("SENTINEL_SYNC_HOUR", "6"))
    _scheduler.add_job(_run_daily_sentinel_sync, "cron", hour=hour, minute=0)
    _scheduler.start()


@app.on_event("shutdown")
def stop_sentinel_scheduler() -> None:
    _scheduler.shutdown(wait=False)
```

Note: if `app/main.py` already uses a `lifespan` context manager instead of `on_event`, add the scheduler start/stop inside that context manager instead.

- [ ] **Step 3: Verify app starts**

```bash
python -m uvicorn app.main:app --port 8001 &
sleep 2
curl -s http://localhost:8001/sentinel/status | python -m json.tool
kill %1
```

Expected: JSON response with `matched: 0`.

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -x -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/main.py requirements.txt
git commit -m "feat: register sentinel router and APScheduler daily sync"
```

---

## Task 8: Workload Matrix UI — Sentinel Column

**Files:**
- Modify: `app/templates/index.html`
- Modify: `app/templates/partials/workload_row.html`

- [ ] **Step 1: Add `Sentinel` column header to `index.html`**

Read `app/templates/index.html`. Locate the `<thead>` row. Find the `<th>Config</th>` header (last column). Add a new `<th>` after it:

```html
<th>Sentinel</th>
```

Then update the empty-state `colspan` from `12` to `13`:

```html
<td colspan="13" ...>
```

- [ ] **Step 2: Add Sentinel badge cell to `workload_row.html`**

Read `app/templates/partials/workload_row.html`. Locate the Config `<td>` (last `<td>` in the data row). Add a new `<td>` after it:

```html
<td>
  {% if w.sentinel_threat_level %}
    {% set pill_color = "var(--green)" if w.sentinel_threat_level == "GREEN" else ("var(--amber)" if w.sentinel_threat_level == "YELLOW" else "var(--red)") %}
    {% set pill_label = "🟢 SA" if w.sentinel_threat_level == "GREEN" else ("🟡 SA" if w.sentinel_threat_level == "YELLOW" else "🔴 SA") %}
    <a href="{{ w.sentinel_image_url }}" target="_blank" rel="noopener"
       title="{{ w.sentinel_summary or '' }}"
       style="display:inline-block;padding:2px 7px;border-radius:4px;font-size:0.74rem;text-decoration:none;background:transparent;border:1px solid {{ pill_color }};color:{{ pill_color }}">
      {{ pill_label }}
      {% if w.sentinel_synced_at %}
        {# Show clock if synced more than 48h ago — JS-free approximation via title #}
      {% endif %}
    </a>
  {% else %}
    <span style="color:var(--text-label)">&#8212;</span>
  {% endif %}
</td>
```

- [ ] **Step 3: Manually verify in browser (smoke test)**

Start the app and visit `/`. Confirm the new Sentinel column appears. For rows without sentinel data, `—` shows. No JS errors.

- [ ] **Step 4: Commit**

```bash
git add app/templates/index.html app/templates/partials/workload_row.html
git commit -m "feat: add Sentinel badge column to workload matrix"
```

---

## Task 9: Workload Detail Page — Sentinel Section

**Files:**
- Modify: `app/templates/workload_detail.html`

- [ ] **Step 1: Read workload_detail.html and locate right panel**

```bash
grep -n "config_history\|right panel\|History\|Sentinel" app/templates/workload_detail.html | head -30
```

Identify where the config history panel ends in the right panel column.

- [ ] **Step 2: Add Sentinel section after config history**

In `app/templates/workload_detail.html`, after the config history include/block in the right panel, add:

```html
{# ── Sentinel section ──────────────────────────────────────────── #}
{% if w.sentinel_threat_level or w.amd_tps_sentinel_value %}
<details open style="margin-top:1.5rem">
  <summary style="cursor:pointer;font-size:0.82rem;font-weight:600;color:var(--text-muted);letter-spacing:0.05em;text-transform:uppercase;user-select:none">
    Sentinel (SemiAnalysis)
  </summary>
  <div style="margin-top:0.75rem;display:flex;flex-direction:column;gap:0.5rem">

    {% if w.sentinel_threat_level %}
      {% set s_color = "var(--green)" if w.sentinel_threat_level == "GREEN" else ("var(--amber)" if w.sentinel_threat_level == "YELLOW" else "var(--red)") %}
      <div style="display:flex;align-items:center;gap:0.5rem">
        <span style="padding:2px 8px;border-radius:4px;border:1px solid {{ s_color }};color:{{ s_color }};font-size:0.78rem">
          {{ w.sentinel_threat_level }}
        </span>
        {% if w.sentinel_summary %}
          <span style="font-size:0.82rem;color:var(--text-muted)">{{ w.sentinel_summary }}</span>
        {% endif %}
      </div>
    {% endif %}

    {% if w.amd_tps_sentinel_value is not none %}
      <div style="font-size:0.82rem">
        <span style="color:var(--text-label)">SA-extracted AMD TPS:</span>
        <span class="font-metric" style="color:var(--text)">{{ "%.0f"|format(w.amd_tps_sentinel_value) }}</span>
        {% if w.amd_tps_synced_at %}
          <span style="color:var(--text-label);font-size:0.76rem">· synced {{ w.amd_tps_synced_at }}</span>
        {% endif %}
      </div>
      {% if w.amd_tps_source == "manual" and w.amd_tps is not none and w.amd_tps_sentinel_value is not none %}
        {% set diff = ((w.amd_tps_sentinel_value - w.amd_tps) / w.amd_tps) | abs %}
        {% if diff > 0.05 %}
          <div style="font-size:0.78rem;color:var(--amber);padding:4px 8px;background:rgba(251,191,36,0.1);border-radius:4px;border:1px solid rgba(251,191,36,0.3)">
            &#9888; Sentinel value ({{ "%.0f"|format(w.amd_tps_sentinel_value) }}) differs from manually-entered AMD TPS ({{ "%.0f"|format(w.amd_tps) }}) by {{ "%.0f"|format(diff * 100) }}% — review
          </div>
        {% endif %}
      {% endif %}
    {% endif %}

    {% if w.sentinel_image_url %}
      <div style="margin-top:0.25rem">
        <a href="{{ w.sentinel_image_url }}" target="_blank" rel="noopener"
           style="font-size:0.80rem;color:var(--blue);text-decoration:none">
          View on Sentinel dashboard &#8599;
        </a>
      </div>
    {% endif %}

    {% if w.sentinel_synced_at %}
      <div style="font-size:0.74rem;color:var(--text-label)">Last synced: {{ w.sentinel_synced_at }}</div>
    {% endif %}

  </div>
</details>
{% endif %}
```

- [ ] **Step 3: Verify `w` has sentinel fields in the detail route**

Read `app/main.py` and find the `workload_detail` route. Verify that it passes a `WorkloadRow` (output of `_to_row`) to the template as `w`. Since `_to_row` was updated in Task 3, the sentinel fields should be present. Confirm `w.sentinel_threat_level` etc. are accessible.

- [ ] **Step 4: Commit**

```bash
git add app/templates/workload_detail.html
git commit -m "feat: add Sentinel section to workload detail page"
```

---

## Task 10: Sentinel Status Block in Footer

**Files:**
- Create: `app/templates/partials/sentinel_status.html`
- Modify: `app/templates/base.html`

- [ ] **Step 1: Create `sentinel_status.html` partial**

Create `app/templates/partials/sentinel_status.html`:

```html
<div style="display:flex;align-items:center;gap:0.75rem;font-size:0.74rem;color:var(--text-label)">
  <span>
    {% if status.timestamp %}
      Sentinel: {{ status.matched }} matched · {{ status.timestamp[:10] }}
    {% else %}
      Sentinel: not synced
    {% endif %}
    {% if status.error %}
      <span style="color:var(--red)"> · error</span>
    {% endif %}
  </span>
  {% if user %}
    <button
      hx-post="/sentinel/sync"
      hx-swap="none"
      hx-on::after-request="this.textContent='Synced ✓'; setTimeout(() => this.textContent='Sync now', 2000)"
      style="background:none;border:1px solid var(--border);border-radius:4px;padding:1px 8px;cursor:pointer;color:var(--text-label);font-size:0.74rem">
      Sync now
    </button>
  {% endif %}
</div>
```

- [ ] **Step 2: Add Sentinel status block to `base.html` footer**

Read `app/templates/base.html`. Add a `<footer>` element after the closing `</main>` tag and before the `<div id="toast-container">`:

```html
<footer style="border-top:1px solid var(--border);background:#16181c;padding:0.5rem 1.5rem">
  <div class="max-w-screen-2xl mx-auto"
       hx-get="/sentinel/status-fragment"
       hx-trigger="load"
       hx-swap="innerHTML">
    <span style="font-size:0.74rem;color:var(--text-label)">Loading sentinel status…</span>
  </div>
</footer>
```

- [ ] **Step 3: Verify footer renders in browser**

Start the app and open any page. Confirm the footer appears with the Sentinel status block. The "Sync now" button should appear when signed in.

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -x -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/templates/partials/sentinel_status.html app/templates/base.html
git commit -m "feat: add Sentinel status block to page footer"
```

---

## Task 11: Devzone — Sentinel Analyses Endpoint + Import Curve

**Files:**
- Modify: `app/routers/devzone.py`
- Modify: `app/schemas.py`
- Modify: `app/templates/devzone.html`
- Modify: `tests/test_devzone.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_devzone.py`:

```python
# Assumes WORKLOAD_BASE and helpers already defined in this file.
# If not, add:
WORKLOAD_BASE_DEVZONE = {
    "model": "DSR1", "hardware": "B200", "framework": "TRT-LLM",
    "precision": "FP8", "scenario": "agg", "seqlens": "1k/1k",
}

def test_sentinel_analyses_endpoint_returns_matched_workloads(auth_client, db):
    # Create workload with sentinel data
    r = auth_client.post("/workloads", json=WORKLOAD_BASE_DEVZONE)
    w_id = r.json()["id"]
    # Directly set sentinel fields via DB
    from app.models import Workload
    wl = db.query(Workload).filter(Workload.id == w_id).first()
    wl.sentinel_threat_level = "RED"
    wl.sentinel_summary = "AMD ahead"
    wl.amd_tps_sentinel_value = 2100.0
    db.commit()

    r2 = auth_client.get("/devzone/sentinel-analyses?model=DSR1&seqlen=1k%2F1k")
    assert r2.status_code == 200
    data = r2.json()
    assert len(data) == 1
    assert data[0]["workload_id"] == w_id
    assert data[0]["sentinel_threat_level"] == "RED"
    assert data[0]["amd_tps_sentinel_value"] == 2100.0


def test_sentinel_analyses_endpoint_excludes_workloads_without_sentinel_data(auth_client):
    auth_client.post("/workloads", json=WORKLOAD_BASE_DEVZONE)
    r = auth_client.get("/devzone/sentinel-analyses?model=DSR1&seqlen=1k%2F1k")
    assert r.status_code == 200
    assert r.json() == []


def test_add_sentinel_curve_to_scene(auth_client, db):
    # Create scene
    scene_r = auth_client.post("/devzone/scenes", json={"name": "Test Scene", "model": "DSR1", "seqlen": "1k/1k"})
    scene_id = scene_r.json()["id"]

    # Create workload with sentinel value
    wl_r = auth_client.post("/workloads", json=WORKLOAD_BASE_DEVZONE)
    w_id = wl_r.json()["id"]
    from app.models import Workload
    wl = db.query(Workload).filter(Workload.id == w_id).first()
    wl.sentinel_threat_level = "RED"
    wl.amd_tps_sentinel_value = 2100.0
    wl.sentinel_summary = "AMD ahead"
    db.commit()

    r = auth_client.post(
        f"/devzone/scenes/{scene_id}/curves/sentinel",
        json={"workload_id": w_id},
    )
    assert r.status_code == 200
    curve = r.json()
    assert curve["label"] == "AMD (SA — approximate)"
    assert curve["hardware"] == "B200"
    assert curve["inf_hub_workload_id"] == str(w_id)

    # Points contain the amd_tps value
    import json
    points = json.loads(curve["points"]) if isinstance(curve.get("points"), str) else curve.get("points")
    # points not in CurveRow schema — verify via scene export
    export = auth_client.get(f"/devzone/scenes/{scene_id}/export").json()
    assert any(c["label"] == "AMD (SA — approximate)" for c in export["curves"])


def test_add_sentinel_curve_requires_auth(client, db):
    scene_r = client.post("/devzone/scenes", json={"name": "S", "model": "M", "seqlen": "1k/1k"})
    # If scene creation requires auth, expect 401 here too — adjust accordingly
    # The curve endpoint always requires auth
    r = client.post("/devzone/scenes/fake-id/curves/sentinel", json={"workload_id": 1})
    assert r.status_code == 401


def test_add_sentinel_curve_workload_not_found(auth_client):
    scene_r = auth_client.post("/devzone/scenes", json={"name": "S", "model": "M", "seqlen": "1k/1k"})
    scene_id = scene_r.json()["id"]
    r = auth_client.post(
        f"/devzone/scenes/{scene_id}/curves/sentinel",
        json={"workload_id": 99999},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_devzone.py::test_sentinel_analyses_endpoint_returns_matched_workloads tests/test_devzone.py::test_add_sentinel_curve_to_scene -v
```

Expected: FAIL.

- [ ] **Step 3: Add `inf_hub_workload_id` to `DevzoneCurveRow` serialization**

Read `app/routers/devzone.py`. Find where `DevzoneCurve` ORM objects are converted to `DevzoneCurveRow`. Add `inf_hub_workload_id=curve.inf_hub_workload_id` to that conversion (or update the Pydantic `from_attributes=True` config to include it — verify Task 3's schema change is in place).

- [ ] **Step 4: Add `GET /devzone/sentinel-analyses` endpoint**

In `app/routers/devzone.py`, add the following import if not present:

```python
from app.models import Workload
```

Then add the endpoint:

```python
@router.get("/sentinel-analyses")
def get_sentinel_analyses(
    model: str,
    seqlen: str,
    db: Session = Depends(get_db),
):
    """Return workloads matching model+seqlen that have Sentinel data, for devzone import modal."""
    workloads = (
        db.query(Workload)
        .filter(
            Workload.model == model,
            Workload.seqlens == seqlen,
            Workload.sentinel_threat_level.isnot(None),
        )
        .all()
    )
    return [
        {
            "workload_id": w.id,
            "hardware": w.hardware,
            "framework": w.framework,
            "precision": w.precision,
            "sentinel_threat_level": w.sentinel_threat_level,
            "sentinel_summary": w.sentinel_summary,
            "amd_tps_sentinel_value": w.amd_tps_sentinel_value,
            "pic": w.pic,
        }
        for w in workloads
    ]
```

- [ ] **Step 5: Add `POST /devzone/scenes/{scene_id}/curves/sentinel` endpoint**

In `app/routers/devzone.py`, add:

```python
import uuid
import json as _json
from app.devzone_parser import CURVE_COLORS


class SentinelCurveImport(BaseModel):
    workload_id: int


@router.post("/scenes/{scene_id}/curves/sentinel")
def add_sentinel_curve(
    scene_id: str,
    payload: SentinelCurveImport,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.query(DevzoneScene).filter(DevzoneScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    workload = db.query(Workload).filter(Workload.id == payload.workload_id).first()
    if not workload:
        raise HTTPException(status_code=404, detail="Workload not found")

    if workload.amd_tps_sentinel_value is None:
        raise HTTPException(status_code=422, detail="Workload has no Sentinel AMD TPS value")

    # Count existing curves to pick color
    existing_count = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).count()
    color = CURVE_COLORS[existing_count % len(CURVE_COLORS)]

    # Single-point approximation: y = amd_tps_sentinel_value, x = 0 (approximate)
    points = _json.dumps([{
        "x": 0,
        "y": workload.amd_tps_sentinel_value,
        "concurrency": None,
        "sentinel_approximate": True,
    }])

    curve = DevzoneCurve(
        id=str(uuid.uuid4()),
        scene_id=scene_id,
        label="AMD (SA — approximate)",
        hardware=workload.hardware,
        framework=workload.framework,
        precision=workload.precision,
        color=color,
        ibdb_source=f"Sentinel · {workload.sentinel_summary or ''}",
        uploaded_by=user.name,
        points=points,
        inf_hub_workload_id=str(workload.id),
    )
    db.add(curve)
    db.commit()
    db.refresh(curve)

    return DevzoneCurveRow(
        id=curve.id,
        scene_id=curve.scene_id,
        label=curve.label,
        hardware=curve.hardware,
        framework=curve.framework,
        precision=curve.precision,
        color=curve.color,
        ibdb_source=curve.ibdb_source,
        uploaded_by=curve.uploaded_by,
        uploaded_at=curve.uploaded_at.isoformat() if curve.uploaded_at else None,
        inf_hub_workload_id=curve.inf_hub_workload_id,
    )
```

Note: `SentinelCurveImport` uses `int` for `workload_id` because `Workload.id` is an `Integer` PK. Add `from pydantic import BaseModel` if not already imported, or reuse an existing import.

- [ ] **Step 6: Run devzone tests**

```bash
pytest tests/test_devzone.py -v
```

Expected: all PASS including the new tests.

- [ ] **Step 7: Update `devzone.html` — Import from Sentinel tab in Add Curves modal**

Read `app/templates/devzone.html`. Locate the "+ Add Curves" modal. Inside the modal, there should be tab options for Upload and URL. Add a third tab and panel:

In the tab switcher area of the modal, add:

```html
<button type="button" onclick="switchAddTab('sentinel')"
        id="tab-sentinel"
        style="padding:4px 12px;border-radius:4px;font-size:0.80rem;border:1px solid transparent;cursor:pointer;color:var(--text-muted)">
  Import from Sentinel
</button>
```

Add the Sentinel panel (initially hidden):

```html
<div id="add-panel-sentinel" style="display:none">
  <p style="font-size:0.80rem;color:var(--text-muted);margin-bottom:0.75rem">
    Import an AMD reference curve from InferenceX Sentinel for this scene's model and seqlen.
    Curves are single-point approximations extracted by LLM from SemiAnalysis charts.
  </p>
  <div id="sentinel-analyses-list"
       hx-get="/devzone/sentinel-analyses?model={{ scene.model }}&seqlen={{ scene.seqlen }}"
       hx-trigger="intersect once"
       hx-swap="innerHTML">
    <span style="color:var(--text-muted);font-size:0.80rem">Loading…</span>
  </div>
</div>
```

Create a partial template `app/templates/partials/sentinel_analyses_list.html` for the HTMX response:

```html
{% if analyses %}
  <div style="display:flex;flex-direction:column;gap:0.5rem">
    {% for a in analyses %}
      <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:var(--row-alt);border-radius:4px;font-size:0.80rem">
        <div>
          <span style="color:var(--text)">{{ a.hardware }}</span>
          {% if a.framework %}<span style="color:var(--text-muted)"> · {{ a.framework }}</span>{% endif %}
          {% if a.precision %}<span style="color:var(--text-muted)"> · {{ a.precision }}</span>{% endif %}
          {% if a.sentinel_threat_level %}
            {% set sc = "var(--green)" if a.sentinel_threat_level == "GREEN" else ("var(--amber)" if a.sentinel_threat_level == "YELLOW" else "var(--red)") %}
            <span style="margin-left:6px;padding:1px 6px;border-radius:3px;border:1px solid {{ sc }};color:{{ sc }};font-size:0.72rem">SA: {{ a.sentinel_threat_level }}</span>
          {% endif %}
          {% if a.pic %}<span style="color:var(--text-label);margin-left:6px">owner: {{ a.pic }}</span>{% endif %}
        </div>
        <button type="button"
                hx-post="/devzone/scenes/{{ scene_id }}/curves/sentinel"
                hx-vals='{"workload_id": {{ a.workload_id }}}'
                hx-target="#curves-table-body"
                hx-swap="afterbegin"
                style="padding:3px 10px;border-radius:4px;background:var(--green);color:#000;border:none;cursor:pointer;font-size:0.76rem;font-weight:600">
          Import
        </button>
      </div>
    {% endfor %}
  </div>
{% else %}
  <p style="font-size:0.80rem;color:var(--text-muted)">
    No Sentinel data found for {{ model }} / {{ seqlen }}.
    Run a Sentinel sync or add name mappings in <code>data/sentinel_mappings.json</code>.
  </p>
{% endif %}
```

Add a route to serve this partial:

In `app/routers/sentinel.py`:

```python
@router.get("/analyses-fragment", response_class=HTMLResponse)
def analyses_fragment(request: Request, model: str, seqlen: str, scene_id: str, db: Session = Depends(get_db)):
    from app.models import Workload as W
    workloads = (
        db.query(W)
        .filter(W.model == model, W.seqlens == seqlen, W.sentinel_threat_level.isnot(None))
        .all()
    )
    analyses = [
        {
            "workload_id": w.id,
            "hardware": w.hardware,
            "framework": w.framework,
            "precision": w.precision,
            "sentinel_threat_level": w.sentinel_threat_level,
            "sentinel_summary": w.sentinel_summary,
            "amd_tps_sentinel_value": w.amd_tps_sentinel_value,
            "pic": w.pic,
        }
        for w in workloads
    ]
    return templates.TemplateResponse(
        "partials/sentinel_analyses_list.html",
        {"request": request, "analyses": analyses, "model": model, "seqlen": seqlen, "scene_id": scene_id},
    )
```

Update the Sentinel panel in `devzone.html` to use `/sentinel/analyses-fragment` instead of `/devzone/sentinel-analyses`:

```html
<div id="sentinel-analyses-list"
     hx-get="/sentinel/analyses-fragment?model={{ scene.model }}&seqlen={{ scene.seqlen }}&scene_id={{ scene.id }}"
     hx-trigger="intersect once"
     hx-swap="innerHTML">
```

- [ ] **Step 8: Add workload link to curve table in `devzone.html`**

In `devzone.html`, find where the curve table rows are rendered (the curve label column). If the label is currently a plain text span, update it so that when `inf_hub_workload_id` is set, it renders as a link:

```html
{% if curve.inf_hub_workload_id %}
  <a href="/workloads/{{ curve.inf_hub_workload_id }}" target="_blank"
     style="color:var(--blue);text-decoration:none">{{ curve.label }} &#8599;</a>
{% else %}
  {{ curve.label }}
{% endif %}
```

Also add the Sentinel approximation footnote below the chart if any curve has `inf_hub_workload_id` set:

```html
{% if curves | selectattr("inf_hub_workload_id") | list %}
  <p style="font-size:0.74rem;color:var(--text-label);margin-top:0.25rem;font-style:italic">
    * AMD curves imported from SemiAnalysis via Sentinel are single-point approximations.
  </p>
{% endif %}
```

- [ ] **Step 9: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add app/routers/devzone.py app/routers/sentinel.py app/schemas.py \
        app/templates/devzone.html app/templates/partials/sentinel_analyses_list.html \
        tests/test_devzone.py
git commit -m "feat: add devzone Import from Sentinel with workload linkage"
```

---

## Task 12: Final Regression + Alembic Check

- [ ] **Step 1: Run full migration from scratch on a fresh DB**

```bash
rm -f infhub_test_final.db
INFHUB_DB=infhub_test_final.db alembic upgrade head
```

Expected: all migrations apply cleanly with no errors.

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass. Note the count — should be higher than the pre-integration baseline.

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: Sentinel integration complete — amd_tps sync, threat badges, devzone import"
```

---

## Self-Review Notes

- `_parse_numeric` handles both string ("1840 tok/s") and numeric (1840.0) `amd_value` inputs from Sentinel
- `amd_tps_source` is set to `"manual"` in Task 5 before `sync_sentinel` ever runs — so the conditional write in `sync_sentinel` correctly protects manual entries
- `DevzoneCurveRow.inf_hub_workload_id` added in Task 3 schema step; `_to_row` equivalent for curves done in Task 11 Step 3
- `SentinelCurveImport.workload_id` is `int` to match `Workload.id: Integer` — consistent throughout
- APScheduler uses `daemon=True` so it doesn't block server shutdown
- All file paths (`MAPPINGS_PATH`, `SYNC_LOG_PATH`) are env-var overridable for test isolation
- The devzone "Import from Sentinel" Sentinel panel uses `/sentinel/analyses-fragment` (not `/devzone/sentinel-analyses`) so the partial template receives `scene_id` for the import button HTMX targets
