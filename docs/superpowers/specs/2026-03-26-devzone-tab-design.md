# Devzone Tab Design Spec
*2026-03-26*

---

## Purpose

The Devzone tab is a staging and preview layer between IBDB (raw benchmark results) and the public devzone page (`developer.nvidia.com/deep-learning-performance-training-inference/ai-inference`). It lets engineers and PMs compose named chart "scenes" from IBDB data, share them for team review, and track which scene was actually published — creating an audit trail that doesn't exist today.

---

## Problem

The devzone page shows Pareto frontier charts (Throughput vs. Interactivity per GPU). Getting new IBDB results onto that page today involves:
- Manually exporting data from IBDB
- Doing x-factor comparisons by hand in Excel
- Passing files to Joseph via Slack with no audit trail
- No way to answer "what exact data was published on March 26 and who approved it?"

There's also no staging layer: you can't show colleagues "here's what the updated page would look like" before publishing.

---

## What This Is (and Isn't)

**Is:**
- A scene composer: build named chart compositions from IBDB curve data
- A staging preview: see exactly what curves would appear on the devzone page before publishing
- A sharing tool: stable URLs for team review and sign-off
- A publication record: which scene was marked published and when

**Is not:**
- A replacement for IBDB (link out, don't duplicate)
- A live mirror of IBDB data (intentionally snapshot-based for audit purposes)
- A curve comparison / x-factor analysis tool (deferred — see below)

---

## Chart Structure

The devzone page chart axes:
- **X axis:** Generation TPS / User (interactivity — lower = more responsive per concurrent user)
- **Y axis:** Output TPS / Accelerator (throughput — tokens/sec/GPU)
- **One curve = one hardware platform** (e.g. GB300, B200, H200) at a given model + seqlen
- The Pareto shape emerges from a concurrency sweep — IBDB exports include all concurrency points

---

## Data Model

### New table: `devzone_scenes`

```sql
CREATE TABLE devzone_scenes (
    id               TEXT PRIMARY KEY,   -- UUID v4
    name             TEXT NOT NULL,       -- editable by anyone at any time
    model            TEXT NOT NULL,
    seqlen           TEXT NOT NULL,
    created_by       TEXT,
    created_by_email TEXT,
    created_at       DATETIME,
    is_published     INTEGER DEFAULT 0,  -- bool
    published_at     DATETIME
);
```

### New table: `devzone_curves`

```sql
CREATE TABLE devzone_curves (
    id           TEXT PRIMARY KEY,   -- UUID v4
    scene_id     TEXT NOT NULL,      -- FK → devzone_scenes.id
    label        TEXT NOT NULL,      -- display name, e.g. "GB300" or "GB300 (Mar 13)"
    hardware     TEXT NOT NULL,
    framework    TEXT,
    precision    TEXT,
    color        TEXT,               -- hex color assigned at import
    ibdb_source  TEXT,               -- original filename or URL (provenance)
    uploaded_by  TEXT,
    uploaded_at  DATETIME,
    points       TEXT NOT NULL       -- JSON: [{x, y, concurrency, date, experiment_id, ...}]
);
```

**Name edits on scenes are not audit-logged** — names are labels, not data. Curve additions are attributed to the authenticated uploader.

**Duplicate curve handling:** if a curve with the same `hardware + framework + precision` already exists in a scene, the system warns the user and adds it anyway. The label is auto-suffixed with the date: "GB300 (Mar 13)" vs "GB300 (Mar 26)".

---

## API Endpoints

### GET /devzone
Renders `app/templates/devzone.html`. Open (no auth required to view).

### GET /devzone/compare
Renders `app/templates/devzone_compare.html` with `?a=<scene_id>&b=<scene_id>`. Open.

### POST /devzone/scenes
Creates a new scene. Requires auth.
- Body: `{name, model, seqlen}`
- Response: `{id, name, model, seqlen, created_by, created_at}`

### PATCH /devzone/scenes/{id}/name
Updates scene name. Requires auth. Any authenticated user.
- Body: `{name}`
- Response: updated scene row

### DELETE /devzone/scenes/{id}
Deletes scene and all its curves. Requires auth. Creator only (enforced at app layer).

### POST /devzone/scenes/{id}/curves
Parses an uploaded IBDB Plotly HTML export and adds selected curves to the scene. Requires auth.
- Multipart form: `file` (HTML), `selected_labels` (JSON array of series names to import)
- Parses Plotly JSON embedded in HTML, extracts `x`, `y`, and hover metadata per series
- Returns list of added curves

### DELETE /devzone/curves/{id}
Removes a curve from a scene. Requires auth.

### PATCH /devzone/scenes/{id}/publish
Marks scene as published, sets `published_at = now()`. Requires auth.
- Body: `{}`
- Response: updated scene

### GET /devzone/scenes/{id}/export
Returns the scene as a clean JSON export for handoff:
```json
{
  "scene_name": "DSR1 128K/8K GB300 vs B200 staging",
  "model": "deepseek-r1",
  "seqlen": "128K/8K",
  "exported_at": "2026-03-26T18:31:00Z",
  "curves": [
    {
      "label": "GB300",
      "hardware": "GB300",
      "framework": "SGLang",
      "precision": "FP8",
      "ibdb_source": "ibdb_export_2026-03-26.html",
      "points": [{"x": 53.4, "y": 26.1, "concurrency": 4}, ...]
    }
  ]
}
```

---

## UI: Main Tab (`/devzone`)

### Layout

Two-column layout:

**Left sidebar (~280px):**
- "+ New Scene" button at top
- Scene list, newest first. Each card shows:
  - Scene name — inline-editable by anyone (click to edit in place)
  - Model + seqlen as subtitle
  - "N curves · by X · Mar 26" metadata
  - Green dot if `is_published`
- Clicking a card loads that scene in the main panel
- Each card has a "Compare" button that opens a scene-picker modal to generate a `/devzone/compare?a=...&b=...` URL

**Main panel (selected scene):**
- Scene name at top — also inline-editable
- Pareto chart (Plotly, full width, ~400px tall)
- Curve list table below chart: Label, Hardware, Framework, Precision, Source file, Uploaded by, Date, Remove button (creator only)
- "+ Add Curves" button
- "Export JSON" button (top right)
- "Mark as Published" button — sets `is_published`, stamps date, shows confirmation

**Deferred placeholder below chart:**
> *[grayed card with lock icon]* **Curve comparison** — select two curves to see x-factor differences along the full Pareto. Coming soon.

### Add Curves Flow

1. Click "+ Add Curves" → modal opens
2. Two input options:
   - **Upload IBDB export** — drag-drop or file picker, accepts `.html`
   - **Paste IBDB URL** — text input, labeled "API integration coming soon" (non-functional in v1)
3. After file upload, system parses Plotly JSON from the HTML and shows a checklist of found series:
   ```
   ☑ H200  · SGLang · FP8 · 4096/4096 · 8 points · Mar 13
   ☑ B200  · SGLang · FP8 · 4096/4096 · 8 points · Mar 13
   ☑ GB300 · SGLang · FP8 · 4096/4096 · 8 points · Mar 13
   ```
   All checked by default.
4. If any selected series match an existing curve in the scene (same hardware+framework+precision), a warning banner appears: "GB300 FP8 already in this scene — will be added as a second curve with date label."
5. Confirm → checked curves added, chart re-renders immediately

---

## UI: Compare View (`/devzone/compare`)

Accessed via "Compare" button on any scene card. Opens a scene-picker modal to select a second scene, then navigates to `/devzone/compare?a=<id>&b=<id>`.

- Two charts rendered at 50% width, side by side
- Scene names editable inline (anyone)
- Both charts read-only — no add/remove curves from this view
- URL is shareable — stable, persistent
- Each chart has its own "Export JSON" button

---

## Navigation

Add to `base.html` after the Overview link:
```html
<a href="/devzone" class="nav-link {% if request.url.path.startswith('/devzone') %}active{% endif %}">Devzone</a>
```

---

## Deferred: Curve Comparison / X-Factor Analysis

Choosing two curves and seeing the x-factor ratio along the full Pareto is a separate analytical use case ("arm yourself with exact hardware differences") distinct from the staging/publish workflow. It will be designed and added in a future iteration. The UI reserves space for it with a "Coming soon" placeholder.

---

## Files Touched

### New
- `alembic/versions/<rev>_add_devzone_tables.py`
- `app/routers/devzone.py`
- `app/templates/devzone.html`
- `app/templates/devzone_compare.html`

### Modified
- `app/models.py` — `DevzoneScene`, `DevzoneCurve` models
- `app/schemas.py` — `DevzoneSceneCreate`, `DevzoneSceneRow`, `DevzoneCurveRow`, `DevzoneExport`
- `app/main.py` — register devzone router, add `/devzone` and `/devzone/compare` routes
- `app/templates/base.html` — add Devzone nav link

---

## Success Criteria

- Engineer can upload an IBDB export, build a named scene in under 2 minutes
- Scene URL shared in Slack opens the same chart for any colleague
- Team can open two scenes side by side and decide which to publish
- "What data was published on March 26?" is answerable from the scenes list
