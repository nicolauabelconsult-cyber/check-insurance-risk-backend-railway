from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

from app.db import Base
from app import models  # noqa: F401

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    return os.environ["DATABASE_URL"]

def run_migrations_online():
    connectable = engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
