import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.database import Base, DATABASE_URL
from app import models  # noqa: F401 — registers all models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# DOWNGRADE GUARD — protect production data
# ---------------------------------------------------------------------------
_migration_command = os.environ.get("ALEMBIC_CMD", "")
if "downgrade" in " ".join(
    __import__("sys").argv
) and not os.environ.get("ALLOW_DESTRUCTIVE_MIGRATION"):
    raise SystemExit(
        "\n\n"
        "  *** BLOCKED: alembic downgrade is disabled to protect production data ***\n"
        "  infhub.db contains business-critical data.\n"
        "  To override (only in dev with throwaway data), set:\n"
        "    ALLOW_DESTRUCTIVE_MIGRATION=1 alembic downgrade ...\n"
    )
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = DATABASE_URL
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
