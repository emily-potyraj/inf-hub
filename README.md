# inf-hub

NVIDIA's internal inference performance workload tracker.

## Prerequisites

1. **Entra ID app registration** — file IT request for OAuth2 app registration:
   - App name: `inf-hub`
   - Redirect URI: `https://inf-hub.nvidia.com/auth/callback`
   - Required permissions: `openid`, `email`, `profile`, `User.Read`
   - You will receive `CLIENT_ID` and `CLIENT_SECRET`

2. Python 3.11+, nginx on the target server

## Local Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in real values
alembic upgrade head
uvicorn app.main:app --reload
```

Visit http://localhost:8000

## Running Tests

```bash
pytest tests/ -v
```

## Deploy

```bash
# On inf-hub.nvidia.com
git pull
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart inf-hub   # systemd unit pointing to uvicorn
sudo nginx -s reload
```

## Environment Variables

See `.env.example` for required variables.

## Architecture

FastAPI + SQLite + HTMX + Tailwind. Reads are open; writes require NVIDIA SSO login.
See `docs/superpowers/specs/2026-03-24-infx-hub-design.md` for full design spec.
