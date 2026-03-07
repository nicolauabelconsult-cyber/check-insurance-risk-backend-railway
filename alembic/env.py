from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
import os
import sys

# garante que a raiz do projeto entra no PYTHONPATH
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.db import Base  # noqa: E402
from app import models  # noqa: F401,E402  (importa models para registrar metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_UNPOOLED")
    if not url:
        raise RuntimeError("DATABASE_URL não está definido nas Environment Variables do Render.")
    return url


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool, pool_pre_ping=True)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
