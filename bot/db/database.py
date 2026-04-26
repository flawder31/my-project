from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiomysql

from bot.config import settings

logger = logging.getLogger(__name__)

_pool: aiomysql.Pool | None = None


async def create_pool() -> aiomysql.Pool:
    global _pool
    if _pool is not None:
        return _pool

    _pool = await aiomysql.create_pool(
        host=settings.db.host,
        port=settings.db.port,
        user=settings.db.user,
        password=settings.db.password,
        db=settings.db.database,
        minsize=1,
        maxsize=settings.db.pool_size,
        autocommit=True,
        charset="utf8mb4",
    )
    logger.info("MySQL connection pool created")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        logger.info("MySQL connection pool closed")


def get_pool() -> aiomysql.Pool:
    if _pool is None:
        raise RuntimeError("DB pool is not initialised. Call create_pool() first.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[aiomysql.Connection, None]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_cursor(dict_cursor: bool = True) -> AsyncGenerator[aiomysql.DictCursor | aiomysql.Cursor, None]:
    async with get_connection() as conn:
        cursor_class = aiomysql.DictCursor if dict_cursor else aiomysql.Cursor
        async with conn.cursor(cursor_class) as cur:
            yield cur


async def init_tables() -> None:
    """Run the schema migration on first start."""
    import importlib.resources as pkg_resources
    from pathlib import Path

    schema_path = Path(__file__).resolve().parent.parent.parent / "migrations" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            for statement in schema_sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    try:
                        await cur.execute(stmt)
                    except Exception as exc:
                        if "already exists" in str(exc).lower() or "duplicate" in str(exc).lower():
                            continue
                        logger.warning("Schema statement skipped: %s — %s", stmt[:80], exc)
        await conn.commit()
    logger.info("Database tables initialised")
