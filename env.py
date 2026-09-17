import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
load_dotenv()  # alembic runs standalone -- must load .env itself, doesn't go through main.py

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make `app` importable when alembic is run from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import Base  # noqa: E402  — imports every model via app/models/__init__.py

config = context.config

db_url = os.getenv("DATABASE_URL")
if db_url:
    # ConfigParser treats "%" as interpolation syntax even when just SETTING a value,
    # so a URL-encoded password like "%40" (an escaped "@") crashes set_main_option
    # unless we escape it as "%%" first. This is a ConfigParser quirk, not an Alembic one.
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


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


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,       # catch column type drift, e.g. accidental Float instead of DECIMAL
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
