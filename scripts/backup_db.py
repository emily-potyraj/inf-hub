"""
Backup the inf-hub SQLite database to backups/ with a UTC timestamp.
Run before any alembic migration or destructive operation.
"""
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "infhub.db"
BACKUP_DIR = REPO_ROOT / "backups"


def backup():
    if not DB_PATH.exists():
        print(f"[backup] No database found at {DB_PATH} — nothing to back up.")
        return

    BACKUP_DIR.mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = BACKUP_DIR / f"infhub_{ts}.db"
    shutil.copy2(DB_PATH, dest)
    size_kb = dest.stat().st_size // 1024
    print(f"[backup] {dest.name}  ({size_kb} KB)")

    # Keep the 20 most recent backups, remove older ones
    backups = sorted(BACKUP_DIR.glob("infhub_*.db"))
    to_remove = backups[:-20]
    for old in to_remove:
        old.unlink()
        print(f"[backup] Removed old backup: {old.name}")


if __name__ == "__main__":
    backup()
