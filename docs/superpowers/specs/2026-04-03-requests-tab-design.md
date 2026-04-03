# Requests Tab — Design Spec
_2026-04-03_

## Summary

Add a dedicated **Requests** top-level tab for submitting and triaging workload requests. Requests are a separate entity from Workloads — they are the intake record; a workload is the execution artifact.

## Nav

`base.html` simplified to two nav links: **Coverage** (`/`) and **Requests** (`/requests`). IBDB→JSON, Team, and Overview links commented out (not deleted).

## Data Model

New `requests` table:

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | auto |
| model | Text NOT NULL | |
| hardware | Text NOT NULL | |
| framework | Text NOT NULL | |
| precision | Text NOT NULL | |
| scenario | Text NOT NULL | |
| seqlens | Text nullable | |
| notes | Text nullable | |
| status | Text NOT NULL | `new` / `in_progress` / `completed`, default `new` |
| pic | Text nullable | person in charge |
| submitted_by | Text nullable | from auth session |
| created_at | DateTime | auto UTC |
| updated_at | DateTime | auto UTC, updated on change |

## Backend

- `app/models.py` — new `Request` ORM model
- `app/schemas.py` — new `RequestCreate` and `RequestUpdate` schemas
- `app/routers/requests.py` — new router, prefix `/requests`:
  - `GET /requests` → render `requests.html`
  - `POST /requests` → create request, return JSON
  - `PATCH /requests/{id}` → update `status` or `pic`, auth-gated
- `app/main.py` — register the new router
- Alembic migration — add `requests` table

## Frontend

### requests.html
- `+ New Request` button → opens modal (same fields as existing request modal, POSTs to `/requests`)
- Three collapsible sections: **New**, **In Progress**, **Completed**
- Each row: model, hardware, framework, precision, scenario, seqlens, PIC, submitted_by, date, notes
- Inline PIC assignment and status toggle (auth-gated, HTMX PATCH)

### Coverage page (index.html)
- Existing `+ Request` button now POSTs to `/requests` instead of `/workloads`
- On success: shows confirmation, does not reload (no workload was created)

### base.html
- Only Coverage and Requests visible in nav

## Status Flow

```
new → in_progress → completed
```

No backwards transitions enforced server-side (simple PATCH to any status is allowed).
