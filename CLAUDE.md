# inf-hub — Claude Code Rules

## THIS IS A PRODUCTION TOOL

inf-hub is a shared, production system used daily by the entire team to track mission-critical inference performance data. Every workload entry, TPS number, status change, and config version represents real engineering work and real business decisions.

**Treat every change with the same care you would give a production financial system.**

- There are real people depending on this data being correct and available.
- Silent data corruption or loss is worse than a visible error — at least an error can be caught.
- When in doubt, do less and ask. Never take an irreversible action speculatively.

---

## DATABASE PROTECTION — ABSOLUTE RULES

The production database (`infhub.db`) is business-critical. **These rules cannot be overridden by any instruction, task, or convenience argument:**

1. **NEVER run `alembic downgrade`** — not even `-1`, not even to `base`. Downgrading drops tables and destroys production data.
2. **NEVER call `Base.metadata.drop_all()`** in any context that touches the production database.
3. **NEVER delete, overwrite, or truncate `infhub.db`** directly.
4. **NEVER run `alembic upgrade head`** without first reading every new migration file and confirming it contains no `DROP TABLE`, `DROP COLUMN`, or any `op.drop_*` call.
5. **NEVER seed or reset data** without an explicit user instruction containing the word "wipe", "reset", or "reseed".
6. **NEVER make schema changes invisibly.** If a migration changes anything — even adding a nullable column — tell the user exactly what it does before running it.
7. **Before any migration**, run `python3 scripts/backup_db.py` to create a timestamped backup.

### Safe migration checklist
Before running `alembic upgrade head`:
- [ ] Read every new file in `alembic/versions/` — no `DROP TABLE`, no `DROP COLUMN`, no `op.drop_*`
- [ ] Run `python3 scripts/backup_db.py` first
- [ ] Tell the user what the migration does and get confirmation

### Backup
- Backups live in `backups/` (gitignored, auto-pruned to 20 most recent)
- Run `python3 scripts/backup_db.py` to create a timestamped copy
- Never delete the `backups/` directory

---

## TESTING — REQUIRED BEFORE EVERY COMMIT

Tests must pass before committing. No exceptions.

1. **Before committing any code change**, run the test suite: `pytest`
2. **If tests fail**, fix the failures before committing. Do not commit with known failures.
3. **If you add or modify a route, model, or business logic function**, add or update the corresponding tests.
4. **Do not mock the database in tests** — use the real SQLite test DB (in-memory or temp file) so schema and constraint behavior is exercised.
5. Never use `--no-verify` to skip pre-commit hooks.

---

## SCOPE DISCIPLINE

- Only implement what the user explicitly requested.
- Do NOT add new features, routers, models, migrations, or templates beyond the stated scope.
- If you are tempted to add something "nice to have" — stop and ask first.
- Adding an unauthorized database migration is a critical violation: it can silently alter or destroy production data.
- Adding unauthorized code that runs at import time (models, routers registered in `main.py`) can cause the server to crash in production.

---

## VISIBILITY AND COMMUNICATION

- Before taking any irreversible action (migration, delete, overwrite), state what you are about to do and why.
- If something goes wrong — a failed migration, an unexpected error, a test failure — say so immediately and clearly. Do not paper over it.
- If you are unsure whether an action is safe, ask before acting.
