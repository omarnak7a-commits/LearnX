from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

import sys
sys.path.insert(0, '.')

from app.core.db import Base
from app.core.config import get_settings

# Import model modules so their tables register on Base.metadata
import app.models.auth_tokens
import app.models.calendar
import app.models.course
import app.models.file_vault
import app.models.planner
import app.models.profile
import app.models.video

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata from SQLAlchemy Base
target_metadata = Base.metadata

# Database URL comes straight from the app settings (backend/.env or env
# vars). We intentionally do NOT route it through alembic.ini's
# configparser, because `%` characters in passwords (e.g. `%23` in
# Supabase URLs) break configparser's interpolation.
settings = get_settings()
database_url = settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL, no DB connection)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the configured database."""
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
