# IBDB Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Query the IBDB GraphQL API every 5 minutes to detect whether performance data exists for each workload, store the latest run timestamp, and surface it in the Coverage table with a Sync Now button.

**Architecture:** Follow the Sentinel integration pattern exactly — a `sync_ibdb(db)` function in a dedicated router, a JSON name-map file for translating inf-hub field values to IBDB filter values, and a status log file. APScheduler (already running) gets a second 5-minute job. The Coverage page table gains an IBDB column and a top-right sync widget.

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler, httpx, Jinja2/HTMX, SQLite, Alembic

---

### Task 1: DB migration + model/schema/_to_row() for IBDB columns

Add `ibdb_latest_run_at` and `ibdb_synced_at` to the workloads table and wire them through the ORM, schema, and serializer.

**Files:**
- Modify: `app/models.py`
- Modify: `app/schemas.py`
- Modify: `app/routers/workloads.py:54-67` (_to_row)
- Modify: `app/main.py:205-212` (rows_json)
- Create: `alembic/versions/f1g2h3i4_add_ibdb_columns.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test for new columns**

```python
# tests/test_models.py — add to existing file
def test_workload_has_ibdb_columns(db):
    from app.models import Workload
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    w = Workload(
        model="LLaMA3", hardware="MI300X", framework="vLLM",
        precision="FP16", scenario="agg", seqlens="2k/2k",
        ibdb_latest_run_at=now,
        ibdb_synced_at=now,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    assert w.ibdb_latest_run_at is not None
    assert w.ibdb_synced_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/epotyraj/Documents/inf-hub/.worktrees/infx-hub-build
pytest tests/test_models.py::test_workload_has_ibdb_columns -v
```
Expected: FAIL — `Workload` has no attribute `ibdb_latest_run_at`

- [ ] **Step 3: Add columns to Workload model**

In `app/models.py`, after the `sentinel_synced_at` line (line ~43), add:

```python
    ibdb_latest_run_at = Column(DateTime)   # latest run date from IBDB; null = no data
    ibdb_synced_at     = Column(DateTime)   # when this workload was last checked
```

- [ ] **Step 4: Add fields to WorkloadRow schema**

In `app/schemas.py`, after `sentinel_synced_at` (line ~60), add:

```python
    ibdb_latest_run_at: Optional[str] = None   # ISO string
    ibdb_synced_at:     Optional[str] = None   # ISO string
```

- [ ] **Step 5: Serialize in _to_row()**

In `app/routers/workloads.py`, after the `sentinel_synced_at` line (line ~66), add:

```python
    d["ibdb_latest_run_at"] = w.ibdb_latest_run_at.isoformat() if w.ibdb_latest_run_at else None
    d["ibdb_synced_at"]     = w.ibdb_synced_at.isoformat() if w.ibdb_synced_at else None
```

- [ ] **Step 6: Include in rows_json in main.py**

In `app/main.py`, inside the `rows_json` dict comprehension (around line 205-212), add:

```python
        "ibdb_latest_run_at": r.ibdb_latest_run_at,
        "ibdb_synced_at": r.ibdb_synced_at,
```

- [ ] **Step 7: Run test to verify it passes**

```bash
pytest tests/test_models.py::test_workload_has_ibdb_columns -v
```
Expected: PASS

- [ ] **Step 8: Create Alembic migration**

Create `alembic/versions/f1g2h3i4_add_ibdb_columns.py`:

```python
"""add ibdb columns to workloads

Revision ID: f1g2h3i4
Revises: 7786eec81f8f
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1g2h3i4'
down_revision = '7786eec81f8f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('workloads') as batch_op:
        batch_op.add_column(sa.Column('ibdb_latest_run_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('ibdb_synced_at', sa.DateTime(), nullable=True))


def downgrade():
    pass  # never downgrade in production
```

- [ ] **Step 9: Verify migration reads clean before running**

Confirm the migration file has no `DROP TABLE`, `DROP COLUMN`, or `op.drop_*`. Then run:

```bash
python3 scripts/backup_db.py
alembic upgrade head
```
Expected: `Running upgrade 7786eec81f8f -> f1g2h3i4, add ibdb columns to workloads`

- [ ] **Step 10: Run full test suite**

```bash
pytest
```
Expected: all tests pass

- [ ] **Step 11: Commit**

```bash
git add app/models.py app/schemas.py app/routers/workloads.py app/main.py \
        alembic/versions/f1g2h3i4_add_ibdb_columns.py tests/test_models.py
git commit -m "feat: add ibdb_latest_run_at and ibdb_synced_at columns to workloads"
git push origin feature/infx-hub-build:main
```

---

### Task 2: IBDB GraphQL client + name map

Build the module that queries IBDB and returns existence + latest run date for a workload.

**Files:**
- Create: `app/ibdb_client.py`
- Create: `data/ibdb_name_map.json`
- Test: `tests/test_ibdb_client.py`

- [ ] **Step 1: Probe IBDB API for field names**

Before writing tests, discover the actual GraphQL schema. Run this manually (replace `$TOKEN` with a valid NVAuth token from your environment or `.env`):

```bash
curl -s -X POST https://ibpl-service.nvidia.com/graphql \
  -H "Authorization: Bearer $IBDB_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { queryType { fields { name } } } }"}' | python3 -m json.tool
```

Then probe the `getData` query for available fields:

```bash
curl -s -X POST https://ibpl-service.nvidia.com/graphql \
  -H "Authorization: Bearer $IBDB_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __type(name: \"Query\") { fields { name args { name type { name kind } } } } }"}' | python3 -m json.tool
```

Look for a date/timestamp field (likely `s_run_date`, `s_submission_date`, or similar) and confirm filter argument names (`s_model_name`, `s_accelerator_name`, `s_framework_name`, `s_max_isl_osl`). Use actual field names in all subsequent steps.

- [ ] **Step 2: Write failing tests**

Create `tests/test_ibdb_client.py`:

```python
from unittest.mock import patch, MagicMock
from datetime import datetime


MOCK_RESPONSE_WITH_DATA = {
    "data": {
        "getData": [
            {
                "s_run_date": "2025-03-14T09:32:00Z",   # use actual field name from probe
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
    import json
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
    import json
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
    import json
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
    import json
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_ibdb_client.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ibdb_client'`

- [ ] **Step 4: Create data/ibdb_name_map.json**

```json
{
  "_comment": "Map inf-hub field values to IBDB filter values. Add entries as you discover them.",
  "models": {},
  "hardware": {},
  "frameworks": {}
}
```

Run the probe from Step 1 to discover actual IBDB model/hardware/framework strings and populate this file. Example entry once discovered:
```json
{
  "models": { "DSR1": "DeepSeek-R1-671B" },
  "hardware": { "MI300X": "AMD Instinct MI300X" },
  "frameworks": { "vLLM": "vllm" }
}
```

- [ ] **Step 5: Create app/ibdb_client.py**

Use the actual date field name discovered in Step 1 (placeholder `s_run_date` — replace with real name):

```python
"""IBDB GraphQL client.

Checks whether performance data exists for a workload and returns the
latest run datetime. Returns None if the workload is unmapped, IBDB is
unreachable, or no data exists.
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

NAME_MAP_PATH = os.getenv("IBDB_NAME_MAP_PATH", "data/ibdb_name_map.json")
IBDB_URL = os.getenv("IBDB_URL", "https://ibpl-service.nvidia.com/graphql")

# Replace s_run_date with the actual field name discovered during API probe
_DATE_FIELD = "s_run_date"

_QUERY = """
query GetData($model: String, $hardware: String, $framework: String, $seqlen: String) {
  getData(
    filters: {
      s_model_name: $model
      s_accelerator_name: $hardware
      s_framework_name: $framework
      s_max_isl_osl: $seqlen
    }
    pareto: true
  ) {
    """ + _DATE_FIELD + """
  }
}
"""


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

    try:
        resp = httpx.post(
            IBDB_URL,
            json={
                "query": _QUERY,
                "variables": {
                    "model": ibdb_model,
                    "hardware": ibdb_hw,
                    "framework": ibdb_fw,
                    "seqlen": seqlens,
                },
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        records = resp.json().get("data", {}).get("getData", [])
    except Exception as exc:
        print(f"[ibdb] check_workload error ({model}/{hardware}): {exc}")
        return None

    if not records:
        return None

    dates = [_parse_run_date(r) for r in records]
    valid = [d for d in dates if d is not None]
    return max(valid) if valid else datetime.now(timezone.utc)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_ibdb_client.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 7: Run full test suite**

```bash
pytest
```
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add app/ibdb_client.py data/ibdb_name_map.json tests/test_ibdb_client.py
git commit -m "feat: add IBDB GraphQL client with name-map lookup"
git push origin feature/infx-hub-build:main
```

---

### Task 3: IBDB router + APScheduler 5-min job

Wire the sync logic into a FastAPI router and schedule it every 5 minutes.

**Files:**
- Create: `app/routers/ibdb.py`
- Create: `data/ibdb_sync_log.json` (created at runtime, not committed)
- Modify: `app/main.py`
- Test: `tests/test_ibdb.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ibdb.py`:

```python
import json
from unittest.mock import patch
from datetime import datetime, timezone

WORKLOAD_BASE = {
    "model": "LLaMA3-70B", "hardware": "MI300X", "framework": "vLLM",
    "precision": "FP16", "scenario": "agg", "seqlens": "2k/2k",
}


def _setup_name_map(tmp_path, monkeypatch):
    import app.ibdb_client as ibdb_mod
    map_file = tmp_path / "ibdb_name_map.json"
    map_file.write_text(json.dumps({
        "models": {"LLaMA3-70B": "llama-3-70b"},
        "hardware": {"MI300X": "mi300x"},
        "frameworks": {"vLLM": "vllm"},
    }))
    monkeypatch.setattr(ibdb_mod, "NAME_MAP_PATH", str(map_file))
    return map_file


def test_sync_sets_ibdb_latest_run_at(auth_client, tmp_path, monkeypatch):
    import app.routers.ibdb as ibdb_router
    log_file = tmp_path / "ibdb_sync_log.json"
    monkeypatch.setattr(ibdb_router, "SYNC_LOG_PATH", str(log_file))
    monkeypatch.setenv("IBDB_AUTH_TOKEN", "test-token")
    _setup_name_map(tmp_path, monkeypatch)

    auth_client.post("/workloads", json=WORKLOAD_BASE)
    run_date = datetime(2025, 3, 14, 9, 32, 0, tzinfo=timezone.utc)

    with patch("app.ibdb_client.check_workload", return_value=run_date):
        r = auth_client.post("/ibdb/sync")

    assert r.status_code == 200
    data = r.json()
    assert data["synced"] == 1
    assert data["with_data"] == 1

    wl = auth_client.get("/workloads").json()[0]
    assert wl["ibdb_latest_run_at"] is not None
    assert "2025-03-14" in wl["ibdb_latest_run_at"]


def test_sync_sets_ibdb_synced_at_even_when_no_data(auth_client, tmp_path, monkeypatch):
    import app.routers.ibdb as ibdb_router
    log_file = tmp_path / "ibdb_sync_log.json"
    monkeypatch.setattr(ibdb_router, "SYNC_LOG_PATH", str(log_file))
    monkeypatch.setenv("IBDB_AUTH_TOKEN", "test-token")
    _setup_name_map(tmp_path, monkeypatch)

    auth_client.post("/workloads", json=WORKLOAD_BASE)

    with patch("app.ibdb_client.check_workload", return_value=None):
        r = auth_client.post("/ibdb/sync")

    assert r.status_code == 200
    wl = auth_client.get("/workloads").json()[0]
    assert wl["ibdb_latest_run_at"] is None
    assert wl["ibdb_synced_at"] is not None


def test_sync_writes_log_file(auth_client, tmp_path, monkeypatch):
    import app.routers.ibdb as ibdb_router
    log_file = tmp_path / "ibdb_sync_log.json"
    monkeypatch.setattr(ibdb_router, "SYNC_LOG_PATH", str(log_file))
    monkeypatch.setenv("IBDB_AUTH_TOKEN", "test-token")
    _setup_name_map(tmp_path, monkeypatch)

    with patch("app.ibdb_client.check_workload", return_value=None):
        auth_client.post("/ibdb/sync")

    log = json.loads(log_file.read_text())
    assert "timestamp" in log
    assert "synced" in log


def test_sync_requires_auth(client):
    r = client.post("/ibdb/sync")
    assert r.status_code == 401


def test_get_status_returns_log(auth_client, tmp_path, monkeypatch):
    import app.routers.ibdb as ibdb_router
    log_file = tmp_path / "ibdb_sync_log.json"
    log_file.write_text(json.dumps({"timestamp": "2026-04-06T10:00:00Z", "synced": 3, "with_data": 2}))
    monkeypatch.setattr(ibdb_router, "SYNC_LOG_PATH", str(log_file))

    r = auth_client.get("/ibdb/status")
    assert r.status_code == 200
    assert r.json()["synced"] == 3


def test_get_status_when_no_log(auth_client, tmp_path, monkeypatch):
    import app.routers.ibdb as ibdb_router
    monkeypatch.setattr(ibdb_router, "SYNC_LOG_PATH", str(tmp_path / "nonexistent.json"))

    r = auth_client.get("/ibdb/status")
    assert r.status_code == 200
    assert r.json()["synced"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ibdb.py -v
```
Expected: FAIL — `No module named 'app.routers.ibdb'`

- [ ] **Step 3: Create app/routers/ibdb.py**

```python
"""IBDB sync router.

POST /ibdb/sync  — trigger immediate sync (auth required)
GET  /ibdb/status — return last sync result from log file
"""
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.models import Workload
from app import ibdb_client

router = APIRouter(prefix="/ibdb", tags=["ibdb"])

SYNC_LOG_PATH = os.getenv("IBDB_SYNC_LOG_PATH", "data/ibdb_sync_log.json")


def _write_log(result: dict) -> None:
    log_dir = os.path.dirname(SYNC_LOG_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    with open(SYNC_LOG_PATH, "w") as f:
        json.dump(result, f, indent=2)


def sync_ibdb(db: Session) -> dict:
    """Check all workloads against IBDB. Safe to call even if IBDB is unreachable."""
    token = os.getenv("IBDB_AUTH_TOKEN", "")
    workloads = db.query(Workload).all()
    now = datetime.now(timezone.utc)
    synced = 0
    with_data = 0

    for w in workloads:
        latest_run_at = ibdb_client.check_workload(
            model=w.model,
            hardware=w.hardware,
            framework=w.framework,
            seqlens=w.seqlens or "",
            token=token,
        )
        w.ibdb_synced_at = now
        if latest_run_at is not None:
            w.ibdb_latest_run_at = latest_run_at
            with_data += 1
        synced += 1

    db.commit()

    result = {
        "timestamp": now.isoformat(),
        "synced": synced,
        "with_data": with_data,
    }
    _write_log(result)
    return result


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db), user=Depends(require_auth)):
    return sync_ibdb(db)


@router.get("/status")
def get_status():
    if os.path.exists(SYNC_LOG_PATH):
        with open(SYNC_LOG_PATH) as f:
            return json.load(f)
    return {"timestamp": None, "synced": 0, "with_data": 0}
```

- [ ] **Step 4: Register router and add 5-min scheduler job in main.py**

In `app/main.py`:

a) Add import alongside other router imports:
```python
from app.routers import ibdb as ibdb_router
```

b) Add router registration after the sentinel router line:
```python
app.include_router(ibdb_router.router)
```

c) Add `_run_ibdb_sync` function after `_run_daily_sentinel_sync`:
```python
def _run_ibdb_sync() -> None:
    """Called by APScheduler every 5 minutes."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        ibdb_router.sync_ibdb(db)
    except Exception as exc:
        print(f"[ibdb] scheduled sync error: {exc}")
    finally:
        db.close()
```

d) In `start_sentinel_scheduler()`, add the IBDB job after the sentinel job:
```python
_scheduler.add_job(_run_ibdb_sync, "interval", minutes=5)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_ibdb.py -v
```
Expected: all 6 tests PASS

- [ ] **Step 6: Run full test suite**

```bash
pytest
```
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add app/routers/ibdb.py app/main.py tests/test_ibdb.py
git commit -m "feat: add IBDB sync router and 5-minute APScheduler job"
git push origin feature/infx-hub-build:main
```

---

### Task 4: UI — IBDB column in table + Sync Now widget

Add the IBDB column to the Coverage table and a sync status widget to the top-right corner.

**Files:**
- Modify: `app/templates/index.html`

No new tests needed — UI is Jinja2/JS with no server-side logic to test.

- [ ] **Step 1: Add IBDB column to the table**

In `app/templates/index.html`, find the `_tableCols` array definition (it contains entries like `{key:'model', label:'Model'}`).

Add an IBDB column entry — insert after `last_run_date`:

```js
{key:'ibdb_latest_run_at', label:'IBDB Data'},
```

Then find the cell-rendering function (look for where `r[col.key]` is displayed). Add a special case for `ibdb_latest_run_at` so it formats the datetime nicely:

In the table row rendering logic, add a branch like:

```js
if (col.key === 'ibdb_latest_run_at') {
  const val = r[col.key];
  td.innerHTML = val
    ? `<span class="text-green-600 text-xs">${val.replace('T',' ').slice(0,16)}</span>`
    : `<span class="text-gray-400">—</span>`;
}
```

- [ ] **Step 2: Add Sync Now widget to top-right of Coverage page**

In `app/templates/index.html`, find the page header area (near the `<h1>` or stats bar). Add a sync status widget:

```html
<div id="ibdb-sync-widget" class="flex items-center gap-2 text-xs text-gray-500">
  <span id="ibdb-sync-status">Checking IBDB sync...</span>
  <button
    onclick="triggerIbdbSync()"
    class="px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-600 border border-gray-300 text-xs"
  >Sync Now</button>
</div>
```

Add the following JavaScript (in the existing `<script>` block):

```js
async function loadIbdbStatus() {
  try {
    const r = await fetch('/ibdb/status');
    const data = await r.json();
    const el = document.getElementById('ibdb-sync-status');
    if (!el) return;
    if (data.timestamp) {
      const dt = new Date(data.timestamp);
      const diffMin = Math.round((Date.now() - dt.getTime()) / 60000);
      const ago = diffMin < 1 ? 'just now' : diffMin === 1 ? '1 min ago' : `${diffMin} min ago`;
      el.textContent = `IBDB synced ${ago} (${data.with_data}/${data.synced} with data)`;
    } else {
      el.textContent = 'IBDB not yet synced';
    }
  } catch (e) {
    const el = document.getElementById('ibdb-sync-status');
    if (el) el.textContent = 'IBDB status unavailable';
  }
}

async function triggerIbdbSync() {
  const el = document.getElementById('ibdb-sync-status');
  if (el) el.textContent = 'Syncing...';
  try {
    await fetch('/ibdb/sync', { method: 'POST' });
    await loadIbdbStatus();
  } catch (e) {
    if (el) el.textContent = 'Sync failed';
  }
}

loadIbdbStatus();
setInterval(loadIbdbStatus, 60000);
```

- [ ] **Step 3: Verify UI in browser**

Start the dev server and open the Coverage page:

```bash
uvicorn app.main:app --reload --port 8000
```

Check:
- Table shows "IBDB Data" column with `—` for rows not yet synced
- Top-right shows sync widget with "IBDB not yet synced" or last sync time
- "Sync Now" button triggers a POST and updates the status text

- [ ] **Step 4: Run full test suite**

```bash
pytest
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: add IBDB column to Coverage table and Sync Now widget"
git push origin feature/infx-hub-build:main
```

---

## Post-Implementation Checklist

- [ ] Populate `data/ibdb_name_map.json` with real model/hardware/framework mappings by running the API probe from Task 2, Step 1
- [ ] Set `IBDB_AUTH_TOKEN` in production `.env`
- [ ] Confirm the date field name used in `app/ibdb_client.py` (`_DATE_FIELD`) matches the real IBDB response
- [ ] Run `alembic upgrade head` on the production server after deploying
