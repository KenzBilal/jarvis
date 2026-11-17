"""Alembic environment (async). The database URL comes only from Pydantic Settings / the environment."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from jarvis.config.settings import get_settings
from jarvis.core.errors import retry_async
from jarvis.core.logging import configure_logging
from jarvis.db.base import Base

config = context.config
settings = get_settings()
configure_logging(settings.log_level, environment=settings.jarvis_env)

# Import ALL model modules so autogenerate can see every table.
import jarvis.market.models  # noqa: F401, E402
import jarvis.agents.models  # noqa: F401, E402
import jarvis.news.models    # noqa: F401, E402
import jarvis.execution.models  # noqa: F401, E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connect_args: dict[str, object] = {"timeout": 15}
    if settings.database_ssl:
        connect_args["ssl"] = "require"
    engine = create_async_engine(settings.database_url, poolclass=NullPool, connect_args=connect_args)

    async def _migrate() -> None:
        async with engine.connect() as connection:
            await connection.run_sync(_do_run_migrations)

    try:
        await retry_async(_migrate, attempts=3, base_delay=1.0, operation="alembic.migrate")
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
