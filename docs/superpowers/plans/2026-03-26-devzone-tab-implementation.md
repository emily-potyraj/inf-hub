# Devzone Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/devzone` tab to inf-hub where users compose named Pareto chart "scenes" from IBDB exports, share them for review, and track which scene was published.

**Architecture:** Two new DB tables (`devzone_scenes`, `devzone_curves`) with a pure-Python IBDB HTML parser (`app/devzone_parser.py`) that extracts Plotly trace data. A FastAPI router handles all API endpoints; page routes live in `app/main.py`. Plotly is loaded from CDN in the template; curve data is injected as server-rendered JSON.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Jinja2, HTMX, Plotly (CDN), Python stdlib `json`+`re` for parsing.

**All paths are relative to `.worktrees/infx-hub-build/`.**

---

## File Map

### New
- `alembic/versions/b1c2d3e4_add_devzone_tables.py` — migration
- `app/devzone_parser.py` — IBDB Plotly HTML parser (pure function, no DB)
- `app/routers/devzone.py` — API router (`/devzone/scenes/*`, `/devzone/curves/*`)
- `app/templates/devzone.html` — main tab (sidebar + chart panel)
- `app/templates/devzone_compare.html` — side-by-side compare view
- `tests/test_devzone_parser.py` — parser unit tests
- `tests/test_devzone.py` — API integration tests

### Modified
- `app/models.py` — add `DevzoneScene`, `DevzoneCurve`
- `app/schemas.py` — add devzone schemas
- `app/main.py` — register router, add `/devzone` and `/devzone/compare` page routes, add `_build_plotly_traces` helper
- `app/templates/base.html` — add Devzone nav link

---

## Task 1: Alembic Migration

**Files:**
- Create: `alembic/versions/b1c2d3e4_add_devzone_tables.py`

- [ ] **Step 1: Create migration file**

```python
"""add devzone tables

Revision ID: b1c2d3e4
Revises: a2c3d4e5
Create Date: 2026-03-26 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4'
down_revision: Union[str, None] = 'a2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'devzone_scenes',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('seqlen', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=True),
        sa.Column('created_by_email', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_published', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'devzone_curves',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('scene_id', sa.Text(), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('hardware', sa.Text(), nullable=False),
        sa.Column('framework', sa.Text(), nullable=True),
        sa.Column('precision', sa.Text(), nullable=True),
        sa.Column('color', sa.Text(), nullable=True),
        sa.Column('ibdb_source', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('points', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['scene_id'], ['devzone_scenes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('devzone_curves')
    op.drop_table('devzone_scenes')
```

- [ ] **Step 2: Verify migration applies cleanly**

```bash
cd .worktrees/infx-hub-build && alembic upgrade head
```

Expected: no errors, `Running upgrade a2c3d4e5 -> b1c2d3e4`.

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/b1c2d3e4_add_devzone_tables.py
git commit -m "feat: add devzone_scenes and devzone_curves migration"
```

---

## Task 2: Models and Schemas

**Files:**
- Modify: `app/models.py`
- Modify: `app/schemas.py`

- [ ] **Step 1: Add models to `app/models.py`** (append after `TeamFunction`):

```python
class DevzoneScene(Base):
    __tablename__ = "devzone_scenes"

    id               = Column(Text, primary_key=True)
    name             = Column(Text, nullable=False)
    model            = Column(Text, nullable=False)
    seqlen           = Column(Text, nullable=False)
    created_by       = Column(Text)
    created_by_email = Column(Text)
    created_at       = Column(DateTime, default=_now)
    is_published     = Column(Integer, default=0)
    published_at     = Column(DateTime)


class DevzoneCurve(Base):
    __tablename__ = "devzone_curves"

    id          = Column(Text, primary_key=True)
    scene_id    = Column(Text, ForeignKey("devzone_scenes.id", ondelete="CASCADE"), nullable=False)
    label       = Column(Text, nullable=False)
    hardware    = Column(Text, nullable=False)
    framework   = Column(Text)
    precision   = Column(Text)
    color       = Column(Text)
    ibdb_source = Column(Text)
    uploaded_by = Column(Text)
    uploaded_at = Column(DateTime, default=_now)
    points      = Column(Text, nullable=False)   # JSON string
```

- [ ] **Step 2: Add schemas to `app/schemas.py`** (append at end):

```python
class DevzoneSceneCreate(BaseModel):
    name:   str
    model:  str
    seqlen: str


class DevzoneSceneRow(BaseModel):
    id:               str
    name:             str
    model:            str
    seqlen:           str
    created_by:       Optional[str]
    created_by_email: Optional[str]
    created_at:       Optional[str]
    is_published:     int
    published_at:     Optional[str]
    curve_count:      int = 0

    model_config = {"from_attributes": True}


class DevzoneCurveRow(BaseModel):
    id:          str
    scene_id:    str
    label:       str
    hardware:    str
    framework:   Optional[str]
    precision:   Optional[str]
    color:       Optional[str]
    ibdb_source: Optional[str]
    uploaded_by: Optional[str]
    uploaded_at: Optional[str]

    model_config = {"from_attributes": True}


class DevzoneSeriesPreview(BaseModel):
    label:       str
    hardware:    str
    framework:   Optional[str]
    precision:   Optional[str]
    point_count: int
    duplicate:   bool
```

- [ ] **Step 3: Run existing tests to confirm no regressions**

```bash
cd .worktrees/infx-hub-build && pytest tests/ -v -q
```

Expected: all previously-passing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add app/models.py app/schemas.py
git commit -m "feat: add DevzoneScene and DevzoneCurve models and schemas"
```

---

## Task 3: IBDB HTML Parser (TDD)

**Files:**
- Create: `app/devzone_parser.py`
- Create: `tests/test_devzone_parser.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_devzone_parser.py`:

```python
import pytest
from app.devzone_parser import parse_ibdb_export, _parse_hover_text, _extract_framework

# Minimal Plotly HTML that mirrors the IBDB export format.
MINIMAL_HTML = '''<div>
<div id="test-chart" class="plotly-graph-div"></div>
<script type="text/javascript">
Plotly.newPlot(
  "test-chart",
  [
    {
      "legendgroup": "H200",
      "name": "Accelerator: H200",
      "x": [50.0, 100.0, 200.0],
      "y": [30.0, 20.0, 10.0],
      "text": [
        "SGLang-H200<br> Precision: FP8<br> Concurrency: 4<br> Model: deepseek-r1<br> Date: 2026-03-13",
        "SGLang-H200<br> Precision: FP8<br> Concurrency: 8<br> Model: deepseek-r1<br> Date: 2026-03-13",
        "SGLang-H200<br> Precision: FP8<br> Concurrency: 16<br> Model: deepseek-r1<br> Date: 2026-03-13"
      ]
    },
    {
      "legendgroup": "B200",
      "name": "Accelerator: B200",
      "x": [80.0, 160.0, 320.0],
      "y": [50.0, 35.0, 18.0],
      "text": [
        "SGLang-B200<br> Precision: FP8<br> Concurrency: 4<br> Model: deepseek-r1<br> Date: 2026-03-13",
        "SGLang-B200<br> Precision: FP8<br> Concurrency: 8<br> Model: deepseek-r1<br> Date: 2026-03-13",
        "SGLang-B200<br> Precision: FP8<br> Concurrency: 16<br> Model: deepseek-r1<br> Date: 2026-03-13"
      ]
    }
  ],
  {},
  {}
)
</script>
</div>'''


def test_parse_finds_two_series():
    result = parse_ibdb_export(MINIMAL_HTML)
    assert len(result) == 2


def test_parse_extracts_hardware_from_legendgroup():
    result = parse_ibdb_export(MINIMAL_HTML)
    labels = {c["hardware"] for c in result}
    assert labels == {"H200", "B200"}


def test_parse_strips_accelerator_prefix_from_label():
    result = parse_ibdb_export(MINIMAL_HTML)
    labels = {c["label"] for c in result}
    assert labels == {"H200", "B200"}


def test_parse_extracts_xy_points():
    result = parse_ibdb_export(MINIMAL_HTML)
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert len(h200["points"]) == 3
    assert h200["points"][0]["x"] == 50.0
    assert h200["points"][0]["y"] == 30.0


def test_parse_extracts_metadata_from_hover_text():
    result = parse_ibdb_export(MINIMAL_HTML)
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert h200["points"][0]["concurrency"] == "4"
    assert h200["points"][0]["model"] == "deepseek-r1"


def test_parse_extracts_precision():
    result = parse_ibdb_export(MINIMAL_HTML)
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert h200["precision"] == "FP8"


def test_parse_returns_empty_for_non_plotly_html():
    result = parse_ibdb_export("<html><body>no chart here</body></html>")
    assert result == []


def test_parse_returns_empty_for_malformed_json():
    bad_html = "Plotly.newPlot('x', [{broken json"
    result = parse_ibdb_export(bad_html)
    assert result == []


def test_parse_hover_text_extracts_key_value():
    text = "Label<br> Precision: FP8<br> Concurrency: 8<br> Model: deepseek-r1"
    meta = _parse_hover_text(text)
    assert meta["precision"] == "FP8"
    assert meta["concurrency"] == "8"
    assert meta["model"] == "deepseek-r1"


def test_parse_hover_text_ignores_na_values():
    text = "Label<br> KV Precision: N/A<br> Precision: FP8"
    meta = _parse_hover_text(text)
    assert "kv_precision" not in meta
    assert meta["precision"] == "FP8"


def test_extract_framework_strips_hardware_suffix():
    assert _extract_framework("SGLang-Public-H200", "H200") == "SGLang"


def test_extract_framework_returns_none_if_no_match():
    assert _extract_framework("Accelerator: H200", "H200") is None
```

- [ ] **Step 2: Run to confirm tests fail**

```bash
cd .worktrees/infx-hub-build && pytest tests/test_devzone_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.devzone_parser'`

- [ ] **Step 3: Implement `app/devzone_parser.py`**

```python
import json
import re
import html as html_lib
from typing import Any


CURVE_COLORS = [
    "#76b900", "#00b4d8", "#fbbf24", "#f87171",
    "#a78bfa", "#34d399", "#fb923c", "#e879f9",
]


def parse_ibdb_export(html_content: str) -> list[dict[str, Any]]:
    """
    Parse an IBDB Plotly HTML export and return a list of curve dicts.

    Each dict: {label, hardware, framework, precision, points}
    points: list of {x, y, ...metadata from hover text}

    Returns [] if no Plotly.newPlot call found or JSON is malformed.
    """
    match = re.search(
        r'Plotly\.newPlot\s*\(\s*["\'][^"\']*["\']\s*,\s*(\[)',
        html_content,
    )
    if not match:
        return []

    start = match.start(1)
    try:
        decoder = json.JSONDecoder()
        traces, _ = decoder.raw_decode(html_content, start)
    except (json.JSONDecodeError, ValueError):
        return []

    result = []
    for trace in traces:
        if not isinstance(trace, dict):
            continue

        hardware = trace.get("legendgroup", "")
        name = trace.get("name", "")
        label = name.replace("Accelerator: ", "").strip() if "Accelerator: " in name else (hardware or name)

        x_vals = trace.get("x", [])
        y_vals = trace.get("y", [])
        texts = trace.get("text", [])

        points = []
        for i, (x, y) in enumerate(zip(x_vals, y_vals)):
            meta = _parse_hover_text(texts[i]) if i < len(texts) else {}
            points.append({"x": float(x), "y": float(y), **meta})

        first = points[0] if points else {}
        result.append({
            "label": label,
            "hardware": hardware,
            "framework": _extract_framework(name, hardware),
            "precision": first.get("precision"),
            "points": points,
        })

    return result


def _parse_hover_text(html_text: str) -> dict[str, str]:
    """Extract key-value metadata from IBDB hover HTML text."""
    meta = {}
    parts = re.split(r'<br\s*/?>', html_text, flags=re.IGNORECASE)
    for part in parts:
        clean = re.sub(r'<[^>]+>', '', part).strip()
        clean = html_lib.unescape(clean)
        if ': ' in clean:
            key, _, val = clean.partition(': ')
            key_norm = key.strip().lower().replace(' ', '_').replace('/', '_')
            val = val.strip()
            if key_norm and val and val != 'N/A':
                meta[key_norm] = val
    return meta


def _extract_framework(series_name: str, hardware: str) -> str | None:
    """
    Extract framework from a series name like 'SGLang-Public-H200'.
    Strips the hardware suffix, returns the first dash-separated segment.
    Returns None if pattern doesn't match.
    """
    if not hardware or not series_name:
        return None
    name = series_name.replace("Accelerator: ", "").strip()
    if name.endswith(f"-{hardware}"):
        prefix = name[: -len(hardware) - 1]
        parts = prefix.split("-")
        return parts[0] if parts else None
    return None
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd .worktrees/infx-hub-build && pytest tests/test_devzone_parser.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/devzone_parser.py tests/test_devzone_parser.py
git commit -m "feat: add IBDB Plotly HTML parser with tests"
```

---

## Task 4: Devzone API Router (TDD)

**Files:**
- Create: `tests/test_devzone.py`
- Create: `app/routers/devzone.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_devzone.py`:

```python
import io
import json
import pytest

# Minimal IBDB HTML with 2 hardware series.
IBDB_HTML = '''<div><div id="c" class="plotly-graph-div"></div>
<script>Plotly.newPlot("c",[
  {"legendgroup":"H200","name":"Accelerator: H200","x":[50.0,100.0],"y":[30.0,20.0],
   "text":["H200<br> Precision: FP8<br> Concurrency: 4","H200<br> Precision: FP8<br> Concurrency: 8"]},
  {"legendgroup":"B200","name":"Accelerator: B200","x":[80.0,160.0],"y":[50.0,35.0],
   "text":["B200<br> Precision: FP8<br> Concurrency: 4","B200<br> Precision: FP8<br> Concurrency: 8"]}
],{},{})</script></div>'''

SCENE_BASE = {"name": "Test Scene", "model": "deepseek-r1", "seqlen": "128K/8K"}


def _upload_file(client, scene_id, selected_labels=None, html=IBDB_HTML):
    if selected_labels is None:
        selected_labels = ["H200", "B200"]
    return client.post(
        f"/devzone/scenes/{scene_id}/curves",
        files={"file": ("export.html", io.BytesIO(html.encode()), "text/html")},
        data={"selected_labels": json.dumps(selected_labels)},
    )


# --- Scene CRUD ---

def test_create_scene_requires_auth(client):
    r = client.post("/devzone/scenes", json=SCENE_BASE)
    assert r.status_code == 401


def test_create_scene_success(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Test Scene"
    assert data["model"] == "deepseek-r1"
    assert data["seqlen"] == "128K/8K"
    assert "id" in data


def test_list_scenes_open(auth_client, client):
    auth_client.post("/devzone/scenes", json=SCENE_BASE)
    r = client.get("/devzone/scenes")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Scene"


def test_list_scenes_empty(client):
    r = client.get("/devzone/scenes")
    assert r.status_code == 200
    assert r.json() == []


def test_patch_scene_name_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = client.patch(f"/devzone/scenes/{scene_id}/name", json={"name": "New Name"})
    assert r2.status_code == 401


def test_patch_scene_name_any_authenticated_user(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = auth_client.patch(f"/devzone/scenes/{scene_id}/name", json={"name": "Renamed"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "Renamed"


def test_patch_scene_name_404(auth_client):
    r = auth_client.patch("/devzone/scenes/nonexistent/name", json={"name": "x"})
    assert r.status_code == 404


def test_delete_scene_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = client.delete(f"/devzone/scenes/{scene_id}")
    assert r2.status_code == 401


def test_delete_scene_creator_can_delete(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = auth_client.delete(f"/devzone/scenes/{scene_id}")
    assert r2.status_code == 200
    # Verify gone
    r3 = auth_client.get("/devzone/scenes")
    assert r3.json() == []


def test_delete_scene_non_creator_forbidden(auth_client, db):
    # Create scene attributed to a different user
    from app.models import DevzoneScene
    import uuid
    scene = DevzoneScene(
        id=str(uuid.uuid4()),
        name="Other's scene",
        model="deepseek-r1",
        seqlen="1K/1K",
        created_by="Other User",
        created_by_email="other@nvidia.com",
    )
    db.add(scene)
    db.commit()

    r = auth_client.delete(f"/devzone/scenes/{scene.id}")
    assert r.status_code == 403


def test_publish_scene(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = auth_client.patch(f"/devzone/scenes/{scene_id}/publish")
    assert r2.status_code == 200
    assert r2.json()["is_published"] == 1
    assert r2.json()["published_at"] is not None


def test_publish_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = client.patch(f"/devzone/scenes/{scene_id}/publish")
    assert r2.status_code == 401


# --- Curves ---

def test_preview_curves_returns_series(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = auth_client.post(
        f"/devzone/scenes/{scene_id}/curves/preview",
        files={"file": ("export.html", io.BytesIO(IBDB_HTML.encode()), "text/html")},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert len(data) == 2
    labels = {s["label"] for s in data}
    assert labels == {"H200", "B200"}
    assert all(s["point_count"] == 2 for s in data)
    assert all(s["duplicate"] is False for s in data)


def test_preview_curves_flags_duplicate(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    # Add H200 curve first
    _upload_file(auth_client, scene_id, selected_labels=["H200"])
    # Preview again — H200 should now be flagged as duplicate
    r2 = auth_client.post(
        f"/devzone/scenes/{scene_id}/curves/preview",
        files={"file": ("export.html", io.BytesIO(IBDB_HTML.encode()), "text/html")},
    )
    data = r2.json()
    h200 = next(s for s in data if s["label"] == "H200")
    b200 = next(s for s in data if s["label"] == "B200")
    assert h200["duplicate"] is True
    assert b200["duplicate"] is False


def test_add_curves_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = client.post(
        f"/devzone/scenes/{scene_id}/curves",
        files={"file": ("export.html", io.BytesIO(IBDB_HTML.encode()), "text/html")},
        data={"selected_labels": json.dumps(["H200"])},
    )
    assert r2.status_code == 401


def test_add_curves_success(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = _upload_file(auth_client, scene_id)
    assert r2.status_code == 200
    data = r2.json()
    assert len(data) == 2
    labels = {c["label"] for c in data}
    assert labels == {"H200", "B200"}


def test_add_curves_respects_selected_labels(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    r2 = _upload_file(auth_client, scene_id, selected_labels=["H200"])
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["label"] == "H200"


def test_add_curves_duplicate_adds_second(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    _upload_file(auth_client, scene_id, selected_labels=["H200"])
    # Add H200 again — should succeed, yielding 2 H200 curves
    r2 = _upload_file(auth_client, scene_id, selected_labels=["H200"])
    assert r2.status_code == 200
    assert len(r2.json()) == 2
    assert all(c["label"].startswith("H200") for c in r2.json())


def test_add_curves_scene_not_found(auth_client):
    r = _upload_file(auth_client, "nonexistent-id")
    assert r.status_code == 404


def test_delete_curve_requires_auth(auth_client, client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    curves = _upload_file(auth_client, scene_id, selected_labels=["H200"]).json()
    curve_id = curves[0]["id"]
    r2 = client.delete(f"/devzone/curves/{curve_id}")
    assert r2.status_code == 401


def test_delete_curve_success(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    curves = _upload_file(auth_client, scene_id, selected_labels=["H200"]).json()
    curve_id = curves[0]["id"]
    r2 = auth_client.delete(f"/devzone/curves/{curve_id}")
    assert r2.status_code == 200


def test_export_scene_json(auth_client):
    r = auth_client.post("/devzone/scenes", json=SCENE_BASE)
    scene_id = r.json()["id"]
    _upload_file(auth_client, scene_id)
    r2 = auth_client.get(f"/devzone/scenes/{scene_id}/export")
    assert r2.status_code == 200
    data = r2.json()
    assert data["scene_name"] == "Test Scene"
    assert data["model"] == "deepseek-r1"
    assert len(data["curves"]) == 2
    assert "points" in data["curves"][0]
```

- [ ] **Step 2: Run to confirm tests fail**

```bash
cd .worktrees/infx-hub-build && pytest tests/test_devzone.py -v 2>&1 | head -20
```

Expected: errors about missing routes / 404s.

- [ ] **Step 3: Implement `app/routers/devzone.py`**

```python
import json
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DevzoneScene, DevzoneCurve
from app.schemas import (
    DevzoneSceneCreate, DevzoneSceneRow, DevzoneCurveRow, DevzoneSeriesPreview,
)
from app.auth import require_auth
from app.devzone_parser import parse_ibdb_export, CURVE_COLORS

router = APIRouter(prefix="/devzone", tags=["devzone"])


def _now():
    return datetime.now(timezone.utc)


def _scene_row(scene: DevzoneScene, curve_count: int = 0) -> dict:
    return {
        "id": scene.id,
        "name": scene.name,
        "model": scene.model,
        "seqlen": scene.seqlen,
        "created_by": scene.created_by,
        "created_by_email": scene.created_by_email,
        "created_at": scene.created_at.isoformat() if scene.created_at else None,
        "is_published": scene.is_published or 0,
        "published_at": scene.published_at.isoformat() if scene.published_at else None,
        "curve_count": curve_count,
    }


def _curve_row(curve: DevzoneCurve) -> dict:
    return {
        "id": curve.id,
        "scene_id": curve.scene_id,
        "label": curve.label,
        "hardware": curve.hardware,
        "framework": curve.framework,
        "precision": curve.precision,
        "color": curve.color,
        "ibdb_source": curve.ibdb_source,
        "uploaded_by": curve.uploaded_by,
        "uploaded_at": curve.uploaded_at.isoformat() if curve.uploaded_at else None,
    }


# --- Scenes ---

@router.post("/scenes")
def create_scene(
    payload: DevzoneSceneCreate,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = DevzoneScene(
        id=str(uuid.uuid4()),
        name=payload.name,
        model=payload.model,
        seqlen=payload.seqlen,
        created_by=user.get("name"),
        created_by_email=user.get("email"),
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return _scene_row(scene)


@router.get("/scenes")
def list_scenes(db: Session = Depends(get_db)):
    scenes = db.query(DevzoneScene).order_by(DevzoneScene.created_at.desc()).all()
    result = []
    for s in scenes:
        count = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == s.id).count()
        result.append(_scene_row(s, count))
    return result


@router.patch("/scenes/{scene_id}/name")
def rename_scene(
    scene_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    scene.name = payload.get("name", scene.name)
    db.commit()
    db.refresh(scene)
    return _scene_row(scene)


@router.delete("/scenes/{scene_id}")
def delete_scene(
    scene_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    if scene.created_by_email and scene.created_by_email != user.get("email"):
        raise HTTPException(status_code=403, detail="Only the creator can delete this scene")
    db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).delete()
    db.delete(scene)
    db.commit()
    return {"deleted": scene_id}


@router.patch("/scenes/{scene_id}/publish")
def publish_scene(
    scene_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    scene.is_published = 1
    scene.published_at = _now()
    db.commit()
    db.refresh(scene)
    return _scene_row(scene)


@router.get("/scenes/{scene_id}/export")
def export_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    curves = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
    return {
        "scene_name": scene.name,
        "model": scene.model,
        "seqlen": scene.seqlen,
        "exported_at": _now().isoformat(),
        "curves": [
            {
                "label": c.label,
                "hardware": c.hardware,
                "framework": c.framework,
                "precision": c.precision,
                "ibdb_source": c.ibdb_source,
                "points": json.loads(c.points),
            }
            for c in curves
        ],
    }


# --- Curves ---

@router.post("/scenes/{scene_id}/curves/preview")
async def preview_curves(
    scene_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    html_content = (await file.read()).decode("utf-8", errors="replace")
    parsed = parse_ibdb_export(html_content)

    # Build set of existing (hardware, framework, precision) for duplicate detection
    existing = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
    existing_sigs = {
        (c.hardware, c.framework, c.precision) for c in existing
    }

    result = []
    for series in parsed:
        sig = (series["hardware"], series["framework"], series["precision"])
        result.append({
            "label": series["label"],
            "hardware": series["hardware"],
            "framework": series["framework"],
            "precision": series["precision"],
            "point_count": len(series["points"]),
            "duplicate": sig in existing_sigs,
        })
    return result


@router.post("/scenes/{scene_id}/curves")
async def add_curves(
    scene_id: str,
    file: UploadFile = File(...),
    selected_labels: str = Form(...),   # JSON array of label strings
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    scene = db.get(DevzoneScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    try:
        labels_to_add = set(json.loads(selected_labels))
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=422, detail="selected_labels must be a JSON array")

    html_content = (await file.read()).decode("utf-8", errors="replace")
    parsed = parse_ibdb_export(html_content)

    existing_count = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).count()

    added = []
    for i, series in enumerate(parsed):
        if series["label"] not in labels_to_add:
            continue

        # Check for duplicate label and suffix with date if needed
        label = series["label"]
        existing_labels = [
            c.label for c in db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
        ]
        if label in existing_labels:
            # Append date from first point's metadata if available
            date = series["points"][0].get("date", "") if series["points"] else ""
            label = f"{label} ({date})" if date else f"{label} (2)"

        color_idx = (existing_count + len(added)) % len(CURVE_COLORS)
        curve = DevzoneCurve(
            id=str(uuid.uuid4()),
            scene_id=scene_id,
            label=label,
            hardware=series["hardware"],
            framework=series["framework"],
            precision=series["precision"],
            color=CURVE_COLORS[color_idx],
            ibdb_source=file.filename,
            uploaded_by=user.get("name"),
            points=json.dumps(series["points"]),
        )
        db.add(curve)
        added.append(curve)

    db.commit()
    for c in added:
        db.refresh(c)
    return [_curve_row(c) for c in added]


@router.delete("/curves/{curve_id}")
def delete_curve(
    curve_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    curve = db.get(DevzoneCurve, curve_id)
    if not curve:
        raise HTTPException(status_code=404, detail="Curve not found")
    db.delete(curve)
    db.commit()
    return {"deleted": curve_id}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd .worktrees/infx-hub-build && pytest tests/test_devzone.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routers/devzone.py tests/test_devzone.py
git commit -m "feat: add devzone API router with full test coverage"
```

---

## Task 5: Wire Up main.py and Add Page Routes

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add imports and router registration**

At the top of `app/main.py`, update the imports block (add to existing import lines):

```python
import json as _json

from app.models import Workload, ConfigVersion, AuditLog, TeamFunction, DevzoneScene, DevzoneCurve
from app.routers import devzone as devzone_router
```

After `app.include_router(breadth_studies_router.router)`, add:

```python
app.include_router(devzone_router.router)
```

- [ ] **Step 2: Add the Plotly trace builder helper** (add before the route definitions):

```python
_CURVE_COLORS = [
    "#76b900", "#00b4d8", "#fbbf24", "#f87171",
    "#a78bfa", "#34d399", "#fb923c", "#e879f9",
]

def _build_plotly_traces(curves):
    traces = []
    for i, c in enumerate(curves):
        try:
            points = _json.loads(c.points)
        except (ValueError, TypeError):
            points = []
        color = c.color or _CURVE_COLORS[i % len(_CURVE_COLORS)]
        traces.append({
            "name": c.label,
            "x": [p["x"] for p in points],
            "y": [p["y"] for p in points],
            "mode": "markers+lines",
            "line": {"color": color, "width": 3},
            "marker": {"color": color, "size": 8},
            "hovertemplate": "%{text}<extra></extra>",
            "text": [
                f"<b>{c.label}</b><br>Concurrency: {p.get('concurrency', '?')}"
                f"<br>Date: {p.get('date', '?')}"
                for p in points
            ],
        })
    return traces
```

- [ ] **Step 3: Add `/devzone` and `/devzone/compare` page routes** (add after the `/overview` route):

```python
@app.get("/devzone")
def devzone_page(
    request: Request,
    scene: str = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    scenes = db.query(DevzoneScene).order_by(DevzoneScene.created_at.desc()).all()
    selected = None
    curves = []
    traces_json = "[]"

    if scene:
        selected = db.get(DevzoneScene, scene)
        if selected:
            curves = (
                db.query(DevzoneCurve)
                .filter(DevzoneCurve.scene_id == scene)
                .all()
            )
            traces_json = _json.dumps(_build_plotly_traces(curves))

    return templates.TemplateResponse("devzone.html", {
        "request": request,
        "user": user,
        "scenes": scenes,
        "selected": selected,
        "curves": curves,
        "traces_json": traces_json,
    })


@app.get("/devzone/compare")
def devzone_compare_page(
    request: Request,
    a: str = None,
    b: str = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    scene_a = db.get(DevzoneScene, a) if a else None
    scene_b = db.get(DevzoneScene, b) if b else None

    def _traces(scene_id):
        if not scene_id:
            return "[]"
        cs = db.query(DevzoneCurve).filter(DevzoneCurve.scene_id == scene_id).all()
        return _json.dumps(_build_plotly_traces(cs))

    all_scenes = db.query(DevzoneScene).order_by(DevzoneScene.created_at.desc()).all()

    return templates.TemplateResponse("devzone_compare.html", {
        "request": request,
        "user": user,
        "scene_a": scene_a,
        "scene_b": scene_b,
        "traces_a": _traces(a),
        "traces_b": _traces(b),
        "all_scenes": all_scenes,
    })
```

- [ ] **Step 4: Run full test suite to confirm no regressions**

```bash
cd .worktrees/infx-hub-build && pytest tests/ -v -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat: register devzone router and add /devzone page routes"
```

---

## Task 6: devzone.html Template

**Files:**
- Create: `app/templates/devzone.html`

- [ ] **Step 1: Create the template**

```html
{% extends "base.html" %}
{% block title %}Devzone · inf-hub{% endblock %}

{% block content %}
<div class="flex gap-6" style="min-height: calc(100vh - 120px)">

  <!-- Sidebar: scene list -->
  <aside style="width:280px; flex-shrink:0; border-right:1px solid var(--border); padding-right:1.5rem">
    <div class="flex items-center justify-between mb-4">
      <h2 class="font-metric text-sm font-semibold" style="color:var(--text-muted); letter-spacing:0.08em; text-transform:uppercase">Scenes</h2>
      {% if user %}
      <button onclick="document.getElementById('new-scene-modal').style.display='flex'"
              class="text-xs px-2 py-1 rounded"
              style="background:var(--green); color:#000; font-weight:600">+ New</button>
      {% endif %}
    </div>

    {% if scenes %}
      {% for s in scenes %}
      <a href="/devzone?scene={{ s.id }}"
         class="block rounded-lg mb-2 p-3 cursor-pointer"
         style="background:{% if selected and selected.id == s.id %}var(--row-alt){% else %}transparent{% endif %}; border:1px solid {% if selected and selected.id == s.id %}var(--border){% else %}transparent{% endif %}; text-decoration:none">
        <div class="flex items-center justify-between">
          <span class="text-sm font-medium" style="color:var(--text)">{{ s.name }}</span>
          {% if s.is_published %}
          <span style="width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block" title="Published"></span>
          {% endif %}
        </div>
        <div class="text-xs mt-1" style="color:var(--text-muted)">{{ s.model }} · {{ s.seqlen }}</div>
        <div class="text-xs mt-1" style="color:var(--text-muted)">
          {{ s.curve_count }} curve{% if s.curve_count != 1 %}s{% endif %} ·
          by {{ s.created_by or 'unknown' }}
        </div>
        {% if user and selected and selected.id == s.id %}
        <div class="flex gap-2 mt-2">
          <button onclick="openCompareModal('{{ s.id }}')"
                  class="text-xs px-2 py-1 rounded"
                  style="background:var(--row-alt); color:var(--text-muted); border:1px solid var(--border)">
            Compare
          </button>
        </div>
        {% endif %}
      </a>
      {% endfor %}
    {% else %}
      <p class="text-sm" style="color:var(--text-muted)">No scenes yet. Create one to start staging curves.</p>
    {% endif %}
  </aside>

  <!-- Main panel -->
  <main class="flex-1 min-w-0">
    {% if selected %}

    <!-- Scene header -->
    <div class="flex items-start justify-between mb-4">
      <div>
        {% if user %}
        <input type="text"
               value="{{ selected.name }}"
               class="text-xl font-semibold bg-transparent border-none outline-none"
               style="color:var(--text); font-family:inherit; width:100%"
               hx-patch="/devzone/scenes/{{ selected.id }}/name"
               hx-trigger="blur"
               hx-vals="js:{name: event.target.value}"
               hx-swap="none"
               title="Click to rename" />
        {% else %}
        <h1 class="text-xl font-semibold" style="color:var(--text)">{{ selected.name }}</h1>
        {% endif %}
        <p class="text-sm mt-1" style="color:var(--text-muted)">{{ selected.model }} · {{ selected.seqlen }}</p>
      </div>
      <div class="flex gap-2">
        <a href="/devzone/scenes/{{ selected.id }}/export"
           class="text-xs px-3 py-1.5 rounded"
           style="background:var(--row-alt); color:var(--text-muted); border:1px solid var(--border); text-decoration:none">
          Export JSON
        </a>
        {% if user %}
        {% if not selected.is_published %}
        <button hx-patch="/devzone/scenes/{{ selected.id }}/publish"
                hx-swap="none"
                hx-on::after-request="window.location.reload()"
                class="text-xs px-3 py-1.5 rounded"
                style="background:var(--green); color:#000; font-weight:600">
          Mark Published
        </button>
        {% else %}
        <span class="text-xs px-3 py-1.5 rounded" style="background:var(--row-alt); color:var(--green); border:1px solid var(--green)">
          ✓ Published
        </span>
        {% endif %}
        {% endif %}
      </div>
    </div>

    <!-- Plotly chart -->
    <div id="devzone-chart" style="height:400px; width:100%; border-radius:8px; overflow:hidden; background:var(--row-alt); border:1px solid var(--border)"></div>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <script>
    (function() {
      var traces = {{ traces_json | safe }};
      var layout = {
        xaxis: {title: 'Interactivity (tokens/sec/user)', color: '#e2e8f0', gridcolor: '#333'},
        yaxis: {title: 'Throughput (tokens/sec/GPU)', color: '#e2e8f0', gridcolor: '#333'},
        paper_bgcolor: '#23262d',
        plot_bgcolor: '#23262d',
        font: {color: '#e2e8f0', family: 'Inter, sans-serif'},
        legend: {bgcolor: 'rgba(0,0,0,0)', bordercolor: '#444'},
        margin: {l: 60, r: 20, t: 20, b: 60},
      };
      Plotly.newPlot('devzone-chart', traces, layout, {responsive: true, displayModeBar: false});
    })();
    </script>

    <!-- Comparison placeholder -->
    <div class="rounded-lg mt-6 p-4 flex items-center gap-3"
         style="background:var(--row-alt); border:1px solid var(--border); opacity:0.5">
      <span style="font-size:1.25rem">🔒</span>
      <div>
        <p class="text-sm font-medium" style="color:var(--text)">Curve comparison</p>
        <p class="text-xs" style="color:var(--text-muted)">Select two curves to see x-factor differences along the full Pareto. Coming soon.</p>
      </div>
    </div>

    <!-- Curve list -->
    <div class="mt-6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold" style="color:var(--text-muted); text-transform:uppercase; letter-spacing:0.08em">Curves</h3>
        {% if user %}
        <button onclick="document.getElementById('add-curves-modal').style.display='flex'"
                class="text-xs px-2 py-1 rounded"
                style="background:var(--row-alt); color:var(--text); border:1px solid var(--border)">
          + Add Curves
        </button>
        {% endif %}
      </div>
      {% if curves %}
      <table class="w-full text-sm">
        <thead>
          <tr style="color:var(--text-muted); border-bottom:1px solid var(--border)">
            <th class="text-left py-2 pr-4">Label</th>
            <th class="text-left py-2 pr-4">Hardware</th>
            <th class="text-left py-2 pr-4">Framework</th>
            <th class="text-left py-2 pr-4">Precision</th>
            <th class="text-left py-2 pr-4">Source</th>
            <th class="text-left py-2 pr-4">Uploaded by</th>
            <th class="text-left py-2"></th>
          </tr>
        </thead>
        <tbody>
          {% for c in curves %}
          <tr style="border-bottom:1px solid var(--border)">
            <td class="py-2 pr-4">
              <span class="inline-block w-3 h-3 rounded-full mr-2" style="background:{{ c.color or '#76b900' }}"></span>
              {{ c.label }}
            </td>
            <td class="py-2 pr-4" style="color:var(--text-muted)">{{ c.hardware }}</td>
            <td class="py-2 pr-4" style="color:var(--text-muted)">{{ c.framework or '—' }}</td>
            <td class="py-2 pr-4" style="color:var(--text-muted)">{{ c.precision or '—' }}</td>
            <td class="py-2 pr-4 text-xs" style="color:var(--text-muted)">{{ c.ibdb_source or '—' }}</td>
            <td class="py-2 pr-4 text-xs" style="color:var(--text-muted)">{{ c.uploaded_by or '—' }}</td>
            <td class="py-2">
              {% if user %}
              <button hx-delete="/devzone/curves/{{ c.id }}"
                      hx-confirm="Remove this curve?"
                      hx-swap="none"
                      hx-on::after-request="window.location.reload()"
                      class="text-xs"
                      style="color:var(--text-muted)">✕</button>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <p class="text-sm" style="color:var(--text-muted)">No curves yet. Upload an IBDB export to add curves.</p>
      {% endif %}
    </div>

    {% else %}
    <div class="flex items-center justify-center h-64" style="color:var(--text-muted)">
      <p class="text-sm">Select a scene from the sidebar, or create a new one.</p>
    </div>
    {% endif %}
  </main>
</div>

<!-- New Scene Modal -->
<div id="new-scene-modal"
     style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:100; align-items:center; justify-content:center">
  <div style="background:var(--bg); border:1px solid var(--border); border-radius:12px; padding:2rem; width:400px; max-width:90vw">
    <h3 class="text-lg font-semibold mb-4" style="color:var(--text)">New Scene</h3>
    <form id="new-scene-form">
      <div class="mb-3">
        <label class="text-xs" style="color:var(--text-muted)">Name</label>
        <input type="text" name="name" required placeholder="e.g. DSR1 B200 vs GB300 FP8 staging"
               class="w-full mt-1 px-3 py-2 rounded text-sm"
               style="background:var(--row-alt); border:1px solid var(--border); color:var(--text)">
      </div>
      <div class="mb-3">
        <label class="text-xs" style="color:var(--text-muted)">Model</label>
        <input type="text" name="model" required placeholder="e.g. deepseek-r1"
               class="w-full mt-1 px-3 py-2 rounded text-sm"
               style="background:var(--row-alt); border:1px solid var(--border); color:var(--text)">
      </div>
      <div class="mb-4">
        <label class="text-xs" style="color:var(--text-muted)">Seqlen</label>
        <input type="text" name="seqlen" required placeholder="e.g. 128K/8K"
               class="w-full mt-1 px-3 py-2 rounded text-sm"
               style="background:var(--row-alt); border:1px solid var(--border); color:var(--text)">
      </div>
      <div class="flex gap-2 justify-end">
        <button type="button" onclick="document.getElementById('new-scene-modal').style.display='none'"
                class="text-sm px-3 py-1.5 rounded" style="color:var(--text-muted)">Cancel</button>
        <button type="submit" class="text-sm px-3 py-1.5 rounded font-semibold"
                style="background:var(--green); color:#000">Create</button>
      </div>
    </form>
  </div>
</div>

<!-- Add Curves Modal -->
{% if selected %}
<div id="add-curves-modal"
     style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:100; align-items:center; justify-content:center">
  <div style="background:var(--bg); border:1px solid var(--border); border-radius:12px; padding:2rem; width:520px; max-width:90vw">
    <h3 class="text-lg font-semibold mb-4" style="color:var(--text)">Add Curves from IBDB</h3>
    <div id="modal-step-1">
      <p class="text-sm mb-3" style="color:var(--text-muted)">Upload an IBDB Plotly HTML export (.html) to preview available curves.</p>
      <input type="file" id="ibdb-file-input" accept=".html"
             class="text-sm mb-4" style="color:var(--text)">
      <div class="mb-3">
        <label class="text-xs" style="color:var(--text-muted)">Paste IBDB URL</label>
        <input type="text" placeholder="API integration coming soon" disabled
               class="w-full mt-1 px-3 py-2 rounded text-sm"
               style="background:var(--row-alt); border:1px solid var(--border); color:var(--text-muted); cursor:not-allowed"
               title="IBDB API integration coming soon">
      </div>
      <div class="flex gap-2 justify-end">
        <button type="button" onclick="document.getElementById('add-curves-modal').style.display='none'"
                class="text-sm px-3 py-1.5 rounded" style="color:var(--text-muted)">Cancel</button>
        <button type="button" onclick="previewCurves()"
                class="text-sm px-3 py-1.5 rounded font-semibold"
                style="background:var(--green); color:#000">Preview</button>
      </div>
    </div>
    <div id="modal-step-2" style="display:none">
      <div id="series-checklist" class="mb-4"></div>
      <div id="duplicate-warning" style="display:none" class="text-xs mb-3 p-2 rounded"
           style="background:#3b1f00; color:#fbbf24; border:1px solid #fbbf24">
        One or more curves already exist in this scene and will be added with a date suffix.
      </div>
      <div class="flex gap-2 justify-end">
        <button type="button" onclick="document.getElementById('modal-step-2').style.display='none'; document.getElementById('modal-step-1').style.display='block'"
                class="text-sm px-3 py-1.5 rounded" style="color:var(--text-muted)">Back</button>
        <button type="button" onclick="confirmAddCurves()"
                class="text-sm px-3 py-1.5 rounded font-semibold"
                style="background:var(--green); color:#000">Add Selected</button>
      </div>
    </div>
  </div>
</div>
{% endif %}

<!-- Compare Modal -->
<div id="compare-modal"
     style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:100; align-items:center; justify-content:center">
  <div style="background:var(--bg); border:1px solid var(--border); border-radius:12px; padding:2rem; width:420px; max-width:90vw">
    <h3 class="text-lg font-semibold mb-4" style="color:var(--text)">Compare with Scene</h3>
    <select id="compare-scene-select" class="w-full px-3 py-2 rounded text-sm mb-4"
            style="background:var(--row-alt); border:1px solid var(--border); color:var(--text)">
      <option value="">Select a scene…</option>
      {% for s in scenes %}
      {% if not selected or s.id != selected.id %}
      <option value="{{ s.id }}">{{ s.name }}</option>
      {% endif %}
      {% endfor %}
    </select>
    <div class="flex gap-2 justify-end">
      <button onclick="document.getElementById('compare-modal').style.display='none'"
              class="text-sm px-3 py-1.5 rounded" style="color:var(--text-muted)">Cancel</button>
      <button onclick="goCompare()" class="text-sm px-3 py-1.5 rounded font-semibold"
              style="background:var(--green); color:#000">Open Side by Side</button>
    </div>
  </div>
</div>

<script>
var currentSceneId = "{{ selected.id if selected else '' }}";

function openCompareModal(sceneId) {
  currentSceneId = sceneId;
  document.getElementById('compare-modal').style.display = 'flex';
}

function goCompare() {
  var otherId = document.getElementById('compare-scene-select').value;
  if (!otherId) return;
  window.location.href = '/devzone/compare?a=' + currentSceneId + '&b=' + otherId;
}

// New scene form
document.getElementById('new-scene-form').addEventListener('submit', function(e) {
  e.preventDefault();
  var fd = new FormData(this);
  fetch('/devzone/scenes', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      name: fd.get('name'),
      model: fd.get('model'),
      seqlen: fd.get('seqlen'),
    }),
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    window.location.href = '/devzone?scene=' + data.id;
  });
});

// Add curves preview
var _previewData = [];

function previewCurves() {
  var fileInput = document.getElementById('ibdb-file-input');
  if (!fileInput.files.length) { alert('Please select a file.'); return; }
  var fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fetch('/devzone/scenes/' + currentSceneId + '/curves/preview', {method: 'POST', body: fd})
  .then(function(r) { return r.json(); })
  .then(function(series) {
    _previewData = series;
    var hasDuplicate = series.some(function(s) { return s.duplicate; });
    document.getElementById('duplicate-warning').style.display = hasDuplicate ? 'block' : 'none';
    var html = series.map(function(s) {
      return '<label class="flex items-center gap-2 mb-2 text-sm" style="color:var(--text)">'
        + '<input type="checkbox" value="' + s.label + '" checked> '
        + '<strong>' + s.label + '</strong>'
        + ' &nbsp;<span style="color:var(--text-muted)">'
        + (s.framework || '') + ' · ' + (s.precision || '') + ' · ' + s.point_count + ' pts'
        + (s.duplicate ? ' <span style="color:#fbbf24">(already in scene)</span>' : '')
        + '</span></label>';
    }).join('');
    document.getElementById('series-checklist').innerHTML = html;
    document.getElementById('modal-step-1').style.display = 'none';
    document.getElementById('modal-step-2').style.display = 'block';
  });
}

function confirmAddCurves() {
  var checked = Array.from(document.querySelectorAll('#series-checklist input:checked'))
    .map(function(el) { return el.value; });
  if (!checked.length) return;
  var fileInput = document.getElementById('ibdb-file-input');
  var fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('selected_labels', JSON.stringify(checked));
  fetch('/devzone/scenes/' + currentSceneId + '/curves', {method: 'POST', body: fd})
  .then(function(r) {
    if (r.ok) window.location.reload();
  });
}
</script>
{% endblock %}
```

- [ ] **Step 2: Smoke test in browser**

Start the server and visit `http://localhost:8000/devzone`. Verify:
- Sidebar shows "No scenes yet" when empty
- "Create" modal opens and submits correctly
- Redirects to `?scene=<id>` after creation
- Empty chart area renders (no JS errors)

```bash
cd .worktrees/infx-hub-build && uvicorn app.main:app --reload
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/devzone.html
git commit -m "feat: add devzone.html main tab template"
```

---

## Task 7: devzone_compare.html Template

**Files:**
- Create: `app/templates/devzone_compare.html`

- [ ] **Step 1: Create the template**

```html
{% extends "base.html" %}
{% block title %}Compare Scenes · inf-hub{% endblock %}

{% block content %}
<div class="mb-4 flex items-center gap-3">
  <a href="/devzone" style="color:var(--text-muted); text-decoration:none; font-size:0.85rem">← Back to Devzone</a>
  <span style="color:var(--border)">|</span>
  <span class="text-sm" style="color:var(--text-muted)">Side-by-side comparison</span>
</div>

<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>

<div class="grid gap-6" style="grid-template-columns: 1fr 1fr">

  <!-- Scene A -->
  <div>
    {% if scene_a %}
    <div class="flex items-center justify-between mb-3">
      {% if user %}
      <input type="text" value="{{ scene_a.name }}"
             class="text-base font-semibold bg-transparent border-none outline-none"
             style="color:var(--text); font-family:inherit"
             hx-patch="/devzone/scenes/{{ scene_a.id }}/name"
             hx-trigger="blur"
             hx-vals="js:{name: event.target.value}"
             hx-swap="none" />
      {% else %}
      <h2 class="text-base font-semibold" style="color:var(--text)">{{ scene_a.name }}</h2>
      {% endif %}
      {% if scene_a.is_published %}
      <span class="text-xs px-2 py-0.5 rounded" style="background:rgba(118,185,0,0.15); color:var(--green); border:1px solid var(--green)">Published</span>
      {% endif %}
    </div>
    <p class="text-xs mb-3" style="color:var(--text-muted)">{{ scene_a.model }} · {{ scene_a.seqlen }}</p>
    <div id="chart-a" style="height:380px; border-radius:8px; overflow:hidden; background:var(--row-alt); border:1px solid var(--border)"></div>
    <script>
    Plotly.newPlot('chart-a', {{ traces_a | safe }}, {
      xaxis: {title: 'Interactivity (tokens/sec/user)', color:'#e2e8f0', gridcolor:'#333'},
      yaxis: {title: 'Throughput (tokens/sec/GPU)', color:'#e2e8f0', gridcolor:'#333'},
      paper_bgcolor:'#23262d', plot_bgcolor:'#23262d',
      font:{color:'#e2e8f0', family:'Inter, sans-serif'},
      margin:{l:60,r:20,t:20,b:60},
    }, {responsive:true, displayModeBar:false});
    </script>
    <div class="mt-3 flex gap-2">
      <a href="/devzone/scenes/{{ scene_a.id }}/export"
         class="text-xs px-2 py-1 rounded"
         style="background:var(--row-alt); color:var(--text-muted); border:1px solid var(--border); text-decoration:none">
        Export JSON
      </a>
    </div>
    {% else %}
    <div class="flex items-center justify-center h-64 rounded-lg"
         style="border:1px dashed var(--border); color:var(--text-muted)">
      <p class="text-sm">No scene selected (a=)</p>
    </div>
    {% endif %}
  </div>

  <!-- Scene B -->
  <div>
    {% if scene_b %}
    <div class="flex items-center justify-between mb-3">
      {% if user %}
      <input type="text" value="{{ scene_b.name }}"
             class="text-base font-semibold bg-transparent border-none outline-none"
             style="color:var(--text); font-family:inherit"
             hx-patch="/devzone/scenes/{{ scene_b.id }}/name"
             hx-trigger="blur"
             hx-vals="js:{name: event.target.value}"
             hx-swap="none" />
      {% else %}
      <h2 class="text-base font-semibold" style="color:var(--text)">{{ scene_b.name }}</h2>
      {% endif %}
      {% if scene_b.is_published %}
      <span class="text-xs px-2 py-0.5 rounded" style="background:rgba(118,185,0,0.15); color:var(--green); border:1px solid var(--green)">Published</span>
      {% endif %}
    </div>
    <p class="text-xs mb-3" style="color:var(--text-muted)">{{ scene_b.model }} · {{ scene_b.seqlen }}</p>
    <div id="chart-b" style="height:380px; border-radius:8px; overflow:hidden; background:var(--row-alt); border:1px solid var(--border)"></div>
    <script>
    Plotly.newPlot('chart-b', {{ traces_b | safe }}, {
      xaxis: {title: 'Interactivity (tokens/sec/user)', color:'#e2e8f0', gridcolor:'#333'},
      yaxis: {title: 'Throughput (tokens/sec/GPU)', color:'#e2e8f0', gridcolor:'#333'},
      paper_bgcolor:'#23262d', plot_bgcolor:'#23262d',
      font:{color:'#e2e8f0', family:'Inter, sans-serif'},
      margin:{l:60,r:20,t:20,b:60},
    }, {responsive:true, displayModeBar:false});
    </script>
    <div class="mt-3 flex gap-2">
      <a href="/devzone/scenes/{{ scene_b.id }}/export"
         class="text-xs px-2 py-1 rounded"
         style="background:var(--row-alt); color:var(--text-muted); border:1px solid var(--border); text-decoration:none">
        Export JSON
      </a>
    </div>
    {% else %}
    <div class="flex items-center justify-center h-64 rounded-lg"
         style="border:1px dashed var(--border); color:var(--text-muted)">
      <p class="text-sm">No scene selected (b=)</p>
    </div>
    {% endif %}
  </div>

</div>
{% endblock %}
```

- [ ] **Step 2: Smoke test**

Visit `http://localhost:8000/devzone/compare?a=<id>&b=<id>` with two real scene IDs. Verify both charts render side by side.

- [ ] **Step 3: Commit**

```bash
git add app/templates/devzone_compare.html
git commit -m "feat: add devzone_compare.html side-by-side template"
```

---

## Task 8: Nav Link

**Files:**
- Modify: `app/templates/base.html`

- [ ] **Step 1: Add Devzone nav link**

In `app/templates/base.html`, after the Overview link:

```html
<a href="/overview" class="nav-link {% if request.url.path == '/overview' %}active{% endif %}">Overview</a>
<a href="/devzone" class="nav-link {% if request.url.path.startswith('/devzone') %}active{% endif %}">Devzone</a>
```

- [ ] **Step 2: Verify nav appears on all pages**

Visit `/`, `/team`, `/overview`, `/devzone` and confirm the nav link appears and highlights correctly on `/devzone` and `/devzone/compare`.

- [ ] **Step 3: Commit**

```bash
git add app/templates/base.html
git commit -m "feat: add Devzone nav link to base.html"
```

---

## Task 9: Final Regression

- [ ] **Step 1: Run full test suite**

```bash
cd .worktrees/infx-hub-build && pytest tests/ -v
```

Expected: all tests PASS. Zero failures.

- [ ] **Step 2: Run migration from scratch**

```bash
cd .worktrees/infx-hub-build && alembic downgrade base && alembic upgrade head
```

Expected: no errors.

- [ ] **Step 3: End-to-end smoke test**

With the server running:
1. Visit `/devzone` — sidebar empty, prompt to create scene
2. Sign in → create a scene
3. Upload the IBDB HTML from `~/Documents/context for claude/ui_sw_acc_d_...html`
4. Confirm checklist shows H200, B200 (or whatever series are present)
5. Confirm curves → chart renders
6. Click "Export JSON" → verify JSON downloads with correct structure
7. Create a second scene → click Compare → verify side-by-side at `/devzone/compare?a=...&b=...`
8. Rename a scene → refresh → confirm name persisted

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: devzone tab complete — scene composer, IBDB parser, Plotly chart, compare view"
```
