# inf-hub

Internal inference performance workload tracker for the NVIDIA InferenceX team.

Tracks tuning workloads across models, hardware platforms, frameworks, precisions, and scenarios. Provides inline editing, config versioning, full audit trails, and competitive gap analysis against AMD.

---

## Features

- **Workload matrix** — grouped by (model × hardware × framework × precision × scenario), with seqlen variants as sub-rows. Multi-column filtering, text search, collapse/expand all.
- **Inline editing** — every cell is editable in place (status, PIC, priority, TPS numbers, notes, etc.). Changes are saved instantly and logged.
- **Audit trail** — every field edit records who changed what, from what value, to what value, and when.
- **Config versioning** — upload and version inference configs per workload. Config history visible in the workload detail page.
- **Breadth studies** — bulk-create workload matrices from a crossproduct of models × hardware × frameworks × precisions × scenarios × seqlens.
- **Devzone** — staging area for Pareto curve comparison. Upload IBDB exports, compare NV vs AMD curves side-by-side.
- **Sentinel** — daily sync of AMD competitive TPS data; flags workloads where AMD is ahead.
- **Team tab** — PIC assignments and workload ownership overview.
- **SSO** — Microsoft Entra ID (Azure AD) OAuth2. Pending app registration; edits are open for local dev in the meantime.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Database | SQLite + SQLAlchemy ORM |
| Migrations | Alembic |
| Frontend | Jinja2 templates + HTMX + Tailwind CSS |
| Auth | Microsoft Entra ID OAuth2 (itsdangerous sessions) |
| Scheduling | APScheduler (sentinel daily sync) |

---

## Local Setup

```bash
git clone https://github.com/emily-potyraj/inf-hub.git
cd inf-hub

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # fill in ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, SESSION_SECRET
alembic upgrade head
uvicorn app.main:app --reload --port 9000
```

Visit http://localhost:9000

> **Auth note:** SSO requires an Entra app registration (in progress — working with BTK team). Until configured, all edits work without login. Flip `editable` in `app/main.py` and restore `require_auth` in `app/auth.py` once the registration is in place.

### Seed data

```bash
python3 scripts/seed_data.py   # loads workloads from InferenceX Configs.xlsx + SemiAnalysis notes
```

---

## Environment Variables

See `.env.example`. Required:

| Variable | Description |
|---|---|
| `SESSION_SECRET` | Random string for signing session cookies |
| `ENTRA_CLIENT_ID` | Entra app client ID |
| `ENTRA_CLIENT_SECRET` | Entra app client secret |
| `ENTRA_TENANT_ID` | Azure tenant (default: `nvidia.onmicrosoft.com`) |
| `REDIRECT_URI` | OAuth callback URL (default: `http://localhost:9000/auth/callback`) |
| `SENTINEL_SYNC_HOUR` | Hour (UTC) to run daily sentinel sync (default: `6`) |

---

## Running Tests

```bash
pytest tests/ -v
```

Tests must pass before every commit. See `CLAUDE.md` for full contribution rules.

---

## Database

- SQLite at `infhub.db` (gitignored — never committed)
- Backup before any migration: `python3 scripts/backup_db.py`
- Backups saved to `backups/` (gitignored, auto-pruned to 20 most recent)
- **Never run `alembic downgrade`** — see `CLAUDE.md`

### Adding a migration

```bash
python3 scripts/backup_db.py          # backup first
alembic revision --autogenerate -m "describe change"
# read the generated file — confirm no DROP TABLE / DROP COLUMN
alembic upgrade head
```

---

## Project Structure

```
app/
  main.py              # FastAPI app, page routes
  models.py            # SQLAlchemy models
  schemas.py           # Pydantic schemas
  auth.py              # Session + Entra OAuth helpers
  audit.py             # Audit log writes
  database.py          # DB session factory
  devzone_parser.py    # IBDB export parser (xlsx + html)
  routers/
    workloads.py       # Workload CRUD + inline field edit
    configs.py         # Config version upload/download
    breadth_studies.py # Bulk workload creation
    devzone.py         # Devzone scenes + curves
    sentinel.py        # AMD competitive data sync
    team.py            # Team function management
    auth_router.py     # OAuth login/callback/logout
  templates/           # Jinja2 HTML templates
scripts/
  seed_data.py         # Seed workloads from source files
  backup_db.py         # Timestamped DB backup utility
alembic/               # DB migrations
tests/                 # pytest test suite
static/                # CSS + vendor JS
```

---

## Deploy

```bash
git pull origin main
pip install -r requirements.txt
python3 scripts/backup_db.py   # always backup before migrating
alembic upgrade head
sudo systemctl restart inf-hub
```

Production systemd unit should run:
```
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 9000
```
