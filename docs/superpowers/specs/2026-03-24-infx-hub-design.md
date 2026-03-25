# inf-hub Design Spec
*2026-03-24*

---

## Purpose

inf-hub is NVIDIA's single nerve center for inference performance: what results we have, what stories they tell, who owns each workload, and where results have been published. It replaces a stale Google Sheet as the system of record and gives engineers, PMs, and eventually marketing one authoritative place to answer "where do we stand?"

The organizing principle is NVIDIA's own performance narrative — not SemiAnalysis's benchmark schedule. SA's InferenceMax is one publishing destination tracked in the tool, not the reason the tool exists.

---

## Problem

The InferenceX team operates in permanent reaction mode:

- Configs are scattered across srt-slurm branches, personal forks, Slack threads, and IBDB
- AMD competitive gaps are discovered after SA publishes, not before
- No one knows who owns what without asking in Slack
- Accuracy problems are found post-submission, not pre
- Infrastructure decisions are re-litigated every two weeks because nothing is written down
- Marketing is not armed: NVIDIA's best results don't flow cleanly to the people who tell the story publicly (see Project Nebula)

The meta-problem: "SA said Blackwell is 50x Hopper — NVIDIA should have been saying that." The engineering work is excellent. The visibility infrastructure around it is broken.

---

## What This Is (and Isn't)

**Is:**
- A workload tracker: every (model × hardware × framework × precision × seqlens) NVIDIA cares about, with engineering status, competitive status, and publishing status in one place
- A config registry with version history and Slack-shareable deeplinks
- An ownership map: who owns each workload and each team function
- A marketing roadmap layer: priority, story label, DLPerf/InfMax/NVMax publishing status

**Is not:**
- A perf results viewer (link to IBDB/IBPlatform, don't duplicate)
- A config store (link to srt-slurm, don't store YAMLs)
- A CI orchestration tool
- A Slack bot (v2)
- A replacement for Project Nebula's golden data pipeline (complementary, not overlapping)

---

## Users

**v1 audience (~30 people):**
- InferenceX engineers — primary daily users; update workload status, upload configs, claim ownership
- PMs (Emily, Nick, others) — read workloads, update priority and story labels, track publishing status

**Later:**
- Broader NVIDIA inference stakeholders (product, AR/PR, DevTech, marketing) via `inf-hub.nvidia.com`

---

## Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | FastAPI + Python | Consistent with pm-hub; team already knows it |
| Database | SQLite + Alembic | No infra to manage; Alembic handles schema migrations; Postgres swap is one config change if needed |
| Frontend | HTMX + Tailwind CSS | Server-rendered, inline-editable, no build step; visual polish comes from CSS not framework complexity |
| Auth | NVIDIA Entra ID SSO via `authlib` | Reads open, writes require login; user identity flows into audit log automatically |
| Hosting | nginx reverse proxy → uvicorn on `inf-hub.nvidia.com` | Single process, behind NVIDIA VPN |

**Auth prerequisite:** App registration in NVIDIA's Entra ID tenant with redirect URI `https://inf-hub.nvidia.com/auth/callback`. This is an IT/admin step — flag early so it doesn't block deploy.

---

## Visual Design

- **Background:** Soft charcoal `#1C1E22` (not harsh black)
- **Body text:** `#e2e8f0` — readable, not glaring
- **NVIDIA wins (AMD gap positive):** `#76b900` green
- **Warnings / attention needed:** amber `#fbbf24`
- **AMD ahead:** red `#f87171`
- **Typography:** Inter for prose and UI labels; Rajdhani for numbers, metrics, and headings
- **Row alternation:** subtle — `#23262d` / `#1f2229`
- **Status badges:** color-coded pill labels, not raw text

Principle: readable first, polished second. No harsh contrast ratios. The tool should feel like a dashboard people want to open, not a spreadsheet they tolerate.

---

## Core Data Model

### `workloads`
The atomic unit. One row per (model × hardware × framework × precision × scenario × seqlens). A `UNIQUE` constraint on these six columns must be enforced at the database level to prevent duplicate rows.

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| model | text | Kimi K2.5, Qwen3.5 397B, DSR1, GLM-5, GPT-OSS, ... |
| hardware | text | H100, H200, B200, B300, GB200, GB300, VR200, R200 |
| framework | text | TRT-LLM, vLLM, SGLang, Dynamo+TRT-LLM |
| precision | text | FP8, NVFP4, INT4, BF16 |
| scenario | text | agg, disagg, disagg+WideEP, agg+MTP, disagg+MTP |
| seqlens | text | 1k/1k, 8k/1k, 128k/8k, etc. |
| status | text | not_started → config_search → accuracy_gate → internal_review → infmax_submitted → published |
| pic | text | owner (NVIDIA username) |
| priority | integer | 0 = highest; matches PM priority ranking |
| story_label | text | e.g. "Blackwell leadership", "SOTA new models", "Long context", "Internal" |
| accuracy_status | text | not_run, pass, fail, unknown |
| nv_tps | real | NVIDIA best TPS/GPU (manually updated) |
| amd_tps | real | AMD best TPS/GPU (manually updated) |
| gap_pct | virtual | Not a stored column. Computed at query time: `(nv_tps - amd_tps) / amd_tps`. Negative = AMD ahead. Omit from CREATE TABLE; add as a computed expression in SELECT. |
| dl_perf_published | text | ISO date if published, null if not |
| infmax_submitted | text | ISO date if submitted, null if not |
| nvmax_recipe_url | text | URL to public recipe, null if not ready |
| ibdb_link | text | URL to IBDB result set |
| notes | text | Freetext, most recent update |
| created_at | timestamp | |
| last_updated | timestamp | Updated on any field change |

### `config_versions`
Immutable config history per workload. Never deleted — only appended.

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| workload_id | integer FK | |
| version_num | integer | Auto-incrementing per workload |
| source_type | text | "file" or "url" |
| file_path | text | Server-side path if source_type = file; original filename preserved for download |
| original_filename | text | Preserved for display and download; any file type accepted; 50 MB per-file cap enforced at upload (nginx `client_max_body_size`) |
| url | text | srt-slurm URL or PR link if source_type = url |
| uploaded_by | text | Authenticated user display name |
| uploaded_by_email | text | From SSO token |
| timestamp | timestamp | |
| notes | text | What changed, why |

Each config version gets a deeplink: `inf-hub.nvidia.com/workloads/{id}/config/{version_num}` — paste directly into Slack. This URL renders the full workload detail page (`/workloads/{id}`) with the config history panel scrolled to and highlighting the specified version. If the source was a file upload, the page shows a download link; if a URL, it shows the link. It does not trigger an automatic download.

### `audit_log`
Every field change on every workload, forever.

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| workload_id | integer FK | |
| user_name | text | From SSO session |
| user_email | text | From SSO token |
| field_name | text | Which field changed |
| old_value | text | Serialized previous value |
| new_value | text | Serialized new value |
| timestamp | timestamp | |

### `team_functions`
Who owns each team function (not per workload — per role).

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| function | text | e.g. "srt-slurm PR approvals", "AMD competitive monitoring" |
| owner | text | NVIDIA username |
| backup | text | NVIDIA username |
| notes | text | |

---

## Pages and Routes

### `/` — Workload Matrix

The main view. Every workload NVIDIA is tracking, filterable and inline-editable.

**Filters (combinable):**
- Story label
- Hardware
- Framework
- Status
- AMD ahead only (gap_pct < 0)
- Unassigned PIC
- Publication status (not on DLPerf, not in InfMax, etc.)
- Priority

**Columns visible in matrix:**
Model, Hardware, Framework, Precision, Scenario/Seqlens, Status (badge), PIC, Priority, NV TPS, AMD TPS, Gap % (colored), Accuracy (badge), DLPerf (✓/date), InfMax (✓/date), Config (link to latest version)

**Inline editing (authenticated):** Status, PIC (with "claim" shortcut), accuracy_status, nv_tps, amd_tps, notes, priority, story_label, dl_perf_published, infmax_submitted, nvmax_recipe_url

**Add workload:** Form at top or modal — required fields are model, hardware, framework, precision, scenario, and seqlens. All six fields together form the unique identity of a workload row; duplicate combinations are rejected with a validation error.

### `/workloads/{id}` — Workload Detail

Full detail for one workload. Two panels:

**Left: All fields** — editable inline for authenticated users. Every field from the data model, with a visible "last updated by X at Y" line.

**Right: History**
- Config versions: ordered newest-first. Each shows version number, source (file download or URL), uploaded by, timestamp, notes. Deeplink button copies `inf-hub.nvidia.com/workloads/{id}/config/{version_num}` to clipboard.
- Field audit trail: chronological log of all changes to this workload. "weiliang changed status from config_search → accuracy_gate on Mar 21 at 14:32"

**Add config:** Button to upload a file or paste a URL. Creates a new config version.

### `/team` — Ownership View

Two sections:

**Team Functions** (top): Simple editable table — function, owner, backup. Who approves srt-slurm PRs, who monitors AMD repos, who owns the SA relationship. Editable by authenticated users.

**Workloads by PIC** (below): All workloads grouped by assigned PIC. Each person's section shows their submission count, status breakdown, and any unresolved accuracy failures. Unassigned workloads surfaced prominently at top.

### `/auth/callback` — SSO redirect handler (not user-facing)

---

## Auth Flow

1. Unauthenticated user visits any page — reads freely, no redirect
2. User clicks any edit control → if no active session, a small inline prompt appears ("Sign in to edit") rather than a full-page redirect. Clicking it opens the Microsoft login in a popup or redirect; the edit state is not preserved across the OAuth round-trip. After successful auth the user lands back on the page they came from and can re-apply their edit.
3. After SSO, session cookie set (signed, server-side); user lands on the original page
4. Session carries: display name, email, expiry
5. All writes log the authenticated user to `audit_log`

Session duration: 8 hours. If a session expires while a user has the page open and they attempt a write, the server returns a 401 and the frontend shows a toast: "Session expired — please sign in again." The write is dropped; the user re-authenticates and reapplies it.

---

## Update Mechanics

**Inline editing:** HTMX `hx-patch` on each editable field. Click to edit, blur or Enter to save. Last-write-wins — the server applies the update unconditionally and returns the saved value, which replaces the field in place. A subtle toast confirms the save. No conflict rejection; if two people edit the same field simultaneously, the second write wins and both are recorded in the audit log.

**Config upload:** File upload or URL paste via form. Server stores file under `data/configs/{workload_id}/{version_num}/` or records the URL. Creates a new `config_versions` row with an auto-incremented `version_num`. The current config is always derived as the row with the highest `version_num` for a given workload — no stored boolean needed.

**Audit:** Every PATCH to a workload field writes an `audit_log` row before updating. Atomic — if the log write fails, the update is rolled back.

**Staleness indicator:** Each workload row shows `last_updated` timestamp. Rows not updated in >7 days get a subtle amber dot — visible signal that the data may be stale.

---

## Deeplinks for Slack

Every workload has a stable URL: `inf-hub.nvidia.com/workloads/{id}`
Every config version has a stable URL: `inf-hub.nvidia.com/workloads/{id}/config/{version_num}`

These are designed to be pasted into Slack. When someone asks "does anyone have the Kimi K2.5 B200 FP8 disagg config?" the answer is a deeplink, not a file attachment.

---

## Out of Scope (v1)

| Feature | Why deferred |
|---------|-------------|
| Automated AMD TPS ingestion | Manual updates with staleness timestamps are sufficient for v1; automation is v2 |
| IBDB / PBR data ingestion | Engineering effort; link out to IBDB instead |
| Nightly regression CI integration | v2 |
| Slack bot / notifications | v2 |
| Decisions log | Dropped from MVP; not blocking |
| Role-based access control | All authenticated users have write access; no permissioning complexity for now |
| Public-facing marketing UI | inf-hub is internal; Project Nebula owns the marketing-grade golden data layer |

---

## Success Criteria (3 months post-launch)

- "Does anyone have the X config?" stops appearing in #inferencemax Slack
- "We didn't know AMD submitted for [model]" stops happening
- Weekly eng meeting opens with inf-hub on screen, not a Google Sheet
- New engineers can find who owns what and where the config is without asking
- PMs can answer "what stories do we have data for right now?" in under 60 seconds
