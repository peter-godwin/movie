from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ------------------------------------------------------------------
# Ensure project root is on PYTHONPATH
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

# ------------------------------------------------------------------
# Alembic Config
# ------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url with DATABASE_URL env var if present.
# This allows Docker to inject the correct host (db) while
# alembic.ini keeps the local dev URL (localhost) as a fallback.
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # Alembic uses psycopg2 (sync) — swap asyncpg driver if present
    database_url = database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )
    config.set_main_option("sqlalchemy.url", database_url)

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ------------------------------------------------------------------
# Import models BEFORE setting target_metadata
# ------------------------------------------------------------------
from app.db.base import Base
import app.models  # triggers app/models/__init__.py

target_metadata = Base.metadata


# ------------------------------------------------------------------
# Offline migrations
# ------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ------------------------------------------------------------------
# Online migrations
# ------------------------------------------------------------------
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()