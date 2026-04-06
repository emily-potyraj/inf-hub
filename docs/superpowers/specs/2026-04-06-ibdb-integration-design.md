# IBDB Integration Design

**Date:** 2026-04-06  
**Status:** Approved

## Overview

Integrate the Inference Benchmark Database (IBDB) GraphQL API into inf-hub to show whether live performance data exists for each workload, and when it was last run. No perf values are stored — only existence and latest run timestamp.

## Goals

- Per workload: query IBDB to check if data exists and retrieve the latest run date/time
- Sync every 5 minutes via background scheduler
- Display latest IBDB run date/time in the Coverage table (IBDB column)
- "Sync Now" button + last synced timestamp in the top-right of the Coverage page
- Placeholder link column (non-functional, "Coming soon")

## Non-Goals

- Storing or displaying TPS / throughput values from IBDB
- Functional deep-links to IBDB UI (deferred)
- Per-user token management (service account NVAuth token works headlessly)

## Architecture

### Sync Job

APScheduler (already running for Sentinel) gains a second job on a 5-minute interval. The job:

1. Fetches all workloads from the DB
2. For each workload, queries IBDB GraphQL `getData` with filters: `s_model_name`, `s_framework_name`, `s_max_isl_osl` (seqlen), `s_accelerator_name`
3. If results exist, records the latest run date from the response (field TBD — confirm with IBDB team, likely `s_run_date` or similar)
4. Writes `ibdb_latest_run_at` and `ibdb_synced_at` back to the workload row

If IBDB is unreachable, the job logs the error and skips — existing values are not cleared.

**Batching note:** Confirm with IBDB team whether a single `getData` query can filter by multiple models/hardware to reduce request count. If not, one query per workload is the fallback.

### Auth

NVAuth token passed as a Bearer token in the `Authorization` header. Token configured via environment variable `IBDB_AUTH_TOKEN`. Works for both user and service accounts.

### New DB Columns (workloads table)

| Column | Type | Description |
|--------|------|-------------|
| `ibdb_latest_run_at` | DateTime, nullable | Latest run date/time returned by IBDB; null = no data |
| `ibdb_synced_at` | DateTime, nullable | When this workload was last checked against IBDB |

### API Endpoints

- `POST /ibdb/sync` — triggers an immediate sync, returns `{ synced_at, total, with_data }`
- `GET /ibdb/status` — returns `{ last_synced_at, total, with_data }` for the header UI

### Name Mapping

IBDB field names (model, hardware, framework) may not match inf-hub values. A JSON mapping file (`app/ibdb_name_map.json`) translates inf-hub values to IBDB filter values, following the same pattern as the Sentinel name map.

## UI Changes

### Coverage page top-right

```
Last IBDB sync: 2 min ago   [Sync Now]
```

Updated via polling `GET /ibdb/status` every 60 seconds (or on page load).

### Table tab — IBDB column

| Condition | Display |
|-----------|---------|
| `ibdb_latest_run_at` is set | `2025-03-14 09:32` (grey "Coming soon" link) |
| null | `—` |

### ibdb_link column

Existing `ibdb_link` field remains. Until deep-links are implemented, the column shows "Coming soon" if `ibdb_latest_run_at` is set, empty otherwise.

## Files Changed

| File | Change |
|------|--------|
| `app/models.py` | Add `ibdb_latest_run_at`, `ibdb_synced_at` columns to `Workload` |
| `app/schemas.py` | Add fields to `WorkloadRow` |
| `app/routers/ibdb.py` | New router: `POST /ibdb/sync`, `GET /ibdb/status` |
| `app/ibdb_client.py` | New module: GraphQL query logic, auth, name mapping lookup |
| `app/ibdb_name_map.json` | New: inf-hub → IBDB field value mappings |
| `app/main.py` | Register ibdb router; add 5-min APScheduler job |
| `app/routers/workloads.py` | Include new fields in `_to_row()` |
| `app/templates/index.html` | Add IBDB column to table; add sync status + button to top-right |
| `alembic/versions/` | Migration: add `ibdb_latest_run_at`, `ibdb_synced_at` |

## Open Question

- Confirm IBDB response field name for run date/time (e.g., `s_run_date`) before implementation
- Confirm whether `getData` supports multi-model batch filtering to reduce request volume at 5-min sync frequency
