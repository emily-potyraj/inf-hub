# Sentinel Integration Design Spec
*2026-03-26*

---

## Purpose

Integrate InferenceX Sentinel (`https://inferencex-sentinel-427b63.gitlab-master-pages.nvidia.com/`) with inf-hub to:

1. **Auto-populate `amd_tps`** from Sentinel's LLM-extracted competitive data, with full provenance tracking
2. **Surface Sentinel threat levels** on workload rows and detail pages, linking out to Sentinel rather than duplicating it
3. **Import AMD curves into devzone scenes** from Sentinel, with one-click linkage to the matched inf-hub workload

Sentinel runs hourly CI on the SemiAnalysis InferenceX leaderboard and publishes structured `data.json` to GitLab Pages. inf-hub polls that file — no changes to Sentinel required.

---

## What This Is (and Isn't)

**Is:**
- A daily + on-demand poll of Sentinel's `data.json`
- A name-mapping config file translating Sentinel model/hardware names to inf-hub names
- Provenance tracking on every `amd_tps` value (manual vs. Sentinel-sourced)
- A lightweight Sentinel badge on workload matrix rows, linking out to Sentinel chart images
- A richer Sentinel section on the workload detail page
- An "Import from Sentinel" path in the devzone Add Curves modal, with workload linkage

**Is not:**
- A replacement for or duplication of the Sentinel dashboard — always link out
- A real-time mirror (daily poll, not live)
- An embedder of Sentinel charts (link to the image URL, don't embed)

---

## Architecture

Three new pieces bolt onto the existing inf-hub server:

### `data/sentinel_mappings.json`
Committed to the repo, edited by hand. Two sub-maps:

```json
{
  "models": {
    "DeepSeek-R1": "DSR1",
    "Llama 3.1 70B": "Llama3-70B"
  },
  "hardware": {
    "GB300 NVL": "GB300",
    "Instinct MI300X": "MI300X"
  }
}
```

Seqlens are normalized automatically (`"8K / 1K"` → `"8k/1k"`) — no mapping entry needed.

Unmatched names are recorded in `data/sentinel_sync_log.json` on each sync so engineers know what to add.

### `app/routers/sentinel.py`
- `POST /sentinel/sync` — manual trigger, auth-required
- `GET /sentinel/status` — last sync time, match stats, open

### APScheduler (new dep)
Registered at app startup in `main.py`. Fires `sync_sentinel()` daily at `SENTINEL_SYNC_HOUR` UTC (default: 06:00).

### Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `SENTINEL_DATA_URL` | (required) | Base URL of Sentinel GitLab Pages, e.g. `https://inferencex-sentinel-427b63.gitlab-master-pages.nvidia.com` |
| `SENTINEL_SYNC_HOUR` | `6` | UTC hour for daily sync |

---

## DB Schema Changes

Single Alembic migration — new columns on `workloads`:

| Column | Type | Notes |
|---|---|---|
| `amd_tps_source` | TEXT | `"manual"` or `"sentinel"` — set on every write to `amd_tps` |
| `amd_tps_sentinel_value` | REAL | Raw value Sentinel extracted — preserved even if engineer manually overrides `amd_tps` |
| `amd_tps_synced_at` | DATETIME | When Sentinel last wrote this value |
| `sentinel_threat_level` | TEXT | `"GREEN"` / `"YELLOW"` / `"RED"` |
| `sentinel_summary` | TEXT | One-line LLM summary from Sentinel |
| `sentinel_image_url` | TEXT | Full URL to chart JPEG on Sentinel dashboard |
| `sentinel_synced_at` | DATETIME | When this workload's Sentinel fields were last updated |

One new column on `devzone_curves`:

| Column | Type | Notes |
|---|---|---|
| `inf_hub_workload_id` | TEXT | Nullable FK to workloads.id — set for Sentinel-sourced curves |

Existing `audit_log` captures every `amd_tps` change. Sentinel sync writes entries with `user_name = "sentinel-sync"` so they are distinguishable from human edits.

New file (not a DB table): `data/sentinel_sync_log.json` — written on each sync:

```json
{
  "timestamp": "2026-03-26T06:00:00Z",
  "analyses_total": 84,
  "matched": 31,
  "unmatched_models": ["Kimi K2.5"],
  "unmatched_hardware": ["Instinct MI325X"],
  "manual_divergences": [
    {"workload_id": 42, "sentinel_value": 1840, "manual_value": 2100}
  ]
}
```

---

## Sync Logic

`sync_sentinel()` in `app/routers/sentinel.py`:

### Step 1 — Fetch
HTTP GET `{SENTINEL_DATA_URL}/data/data.json`. If unreachable or invalid JSON, abort and record the error. No workload data is touched on a failed fetch.

### Step 2 — Load mappings
Read `data/sentinel_mappings.json`. Normalize seqlens by stripping spaces and lowercasing.

### Step 3 — Match
For each analysis in Sentinel's `analyses` array:
- Apply model and hardware mappings
- Match to workload rows by `(model, hardware)`. Seqlen from `isl` is a tiebreaker if multiple rows match.
- Match requires model + hardware minimum.

### Step 4 — Write
For each matched workload:
- **Always write:** `sentinel_threat_level`, `sentinel_summary`, `sentinel_image_url`, `sentinel_synced_at`
- **Always write:** `amd_tps_sentinel_value`, `amd_tps_synced_at` from `amd_value` in the best matching comparison — defined as the comparison whose `amd_gpu` maps to the workload's `hardware` field. If no comparison matches hardware exactly, use the first comparison with a non-null `amd_value`.
- **Conditionally write `amd_tps`:** only if `amd_tps_source` is `null` or `"sentinel"`. Never overwrite a manually-set value. Set `amd_tps_source = "sentinel"`. Write an `audit_log` entry with `user_name = "sentinel-sync"`.
- **Divergence flag:** if `amd_tps_source = "manual"` and Sentinel's value differs by >5%, record in `sentinel_sync_log.json`.

### Step 5 — Log
Write `data/sentinel_sync_log.json` with full sync results.

---

## UI Changes

### Workload Matrix

Add a `Sentinel` column to the workload matrix. Each cell:
- If `sentinel_threat_level` is set: colored pill `🟢 SA` / `🟡 SA` / `🔴 SA`, linked to `sentinel_image_url` (opens new tab)
- If `sentinel_synced_at` > 48 hours old: subtle gray clock icon on the pill
- If no Sentinel data: `—`

### Workload Detail Page

New collapsible "Sentinel" section in the right panel, below config history:

- Threat level badge + `sentinel_summary` text
- `amd_tps_sentinel_value` labeled "SA-extracted AMD TPS" with `amd_tps_synced_at` timestamp
- If `amd_tps_source = "manual"` and `amd_tps_sentinel_value` differs from `amd_tps`: amber note "Sentinel value differs from manually-entered AMD TPS — review"
- "View on Sentinel dashboard →" link to `sentinel_image_url`
- Last synced timestamp (`sentinel_synced_at`)

### Sentinel Status (base.html footer)

A small status block in the `base.html` footer, rendered server-side, showing:
- Last sync time (from `data/sentinel_sync_log.json`)
- Matched workload count
- Link to download `sentinel_sync_log.json`
- "Sync Now" button (auth-required, `hx-post="/sentinel/sync"`, visible only when `user` is in session)

`GET /sentinel/status` returns JSON consumed by this footer block via HTMX polling or page render — it is not a dedicated user-facing page.

---

## Devzone: Import from Sentinel

### Add Curves Modal — Third Option

A third input option in the devzone "Add Curves" modal: **"Import from Sentinel"**.

Populated by `GET /devzone/sentinel-analyses?model=X&seqlen=Y` — reads Sentinel columns from matched workload rows for the current scene's model + seqlen. No re-fetch; uses cached workload data.

Dropdown options show: `[hardware] · [framework] · [precision] · SA: RED/YELLOW/GREEN · owner: [pic]`

### On Import

- AMD comparison points added as a curve. Single `amd_value` scalar plotted as a dot connected by a dashed line.
- Curve labeled `"AMD (SA — approximate)"`.
- Footnote below chart: *"AMD curves imported from SemiAnalysis via Sentinel are single-point approximations."*
- `inf_hub_workload_id` set on the `devzone_curves` row to the matched workload.
- Curve label in the scene's curve table links to `/workloads/{inf_hub_workload_id}` — one-click to see owner, status, configs, and what's being done.

### New Endpoint

`GET /devzone/sentinel-analyses?model=X&seqlen=Y` — returns workloads matching the scene parameters that have Sentinel data, shaped for the modal dropdown.

---

## Dependencies

This spec depends on the devzone tables (`devzone_scenes`, `devzone_curves`) existing in the database, as defined in `docs/superpowers/specs/2026-03-26-devzone-tab-design.md`. The devzone tab feature must be implemented before or alongside the "Import from Sentinel" devzone feature (Section: Devzone: Import from Sentinel). The Sentinel workload matrix and detail page changes have no devzone dependency and can be implemented independently.

---

## Files Touched

### New
- `data/sentinel_mappings.json`
- `app/routers/sentinel.py`
- `alembic/versions/<rev>_add_sentinel_columns.py`

### Modified
- `app/main.py` — register sentinel router, register APScheduler job
- `app/models.py` — new columns on `Workload`, new column on `DevzoneCurve`
- `app/schemas.py` — extend `WorkloadRow` with Sentinel fields
- `app/routers/workloads.py` — `amd_tps` PATCH sets `amd_tps_source = "manual"`
- `app/routers/devzone.py` — new `GET /devzone/sentinel-analyses` endpoint; `POST /devzone/scenes/{id}/curves` handles `sentinel_source` curves
- `app/templates/base.html` — Sentinel status block in footer
- `app/templates/index.html` — Sentinel column header
- `app/templates/partials/workload_row.html` — Sentinel badge cell
- `app/templates/workload_detail.html` — Sentinel section in right panel
- `app/templates/devzone.html` — Import from Sentinel option in Add Curves modal; workload link in curve table
- `requirements.txt` — add `apscheduler`

---

## Success Criteria

- Daily sync runs automatically; `sentinel_sync_log.json` shows matched count growing as mapping file is updated
- `amd_tps` on workload rows shows `sentinel-sync` in audit log when Sentinel-populated; manual entries are never silently overwritten
- Engineers can see on the workload detail page: what Sentinel thinks vs. what's manually recorded, with timestamps
- From a devzone scene with an AMD Sentinel curve, one click reaches the inf-hub workload owner and status
- "What does SA say about DSR1 on GB300?" is answerable in under 10 seconds from inf-hub
