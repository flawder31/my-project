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
async def get_cursor(
    dict_cursor: bool = True,
) -> AsyncGenerator[aiomysql.DictCursor | aiomysql.Cursor, None]:
    async with get_connection() as conn:
        cursor_class = aiomysql.DictCursor if dict_cursor else aiomysql.Cursor
        async with conn.cursor(cursor_class) as cur:
            yield cur


# FIXED: transactional cursor for SELECT ... FOR UPDATE and atomic operations
@asynccontextmanager
async def get_transactional_cursor(
    dict_cursor: bool = True,
) -> AsyncGenerator[aiomysql.DictCursor | aiomysql.Cursor, None]:
    """Cursor with autocommit=False for transactional operations.

    Usage::

        async with get_transactional_cursor() as cur:
            await cur.execute("SELECT ... FOR UPDATE")
            await cur.execute("UPDATE ...")
        # auto-committed on clean exit, rolled back on exception
    """
    pool = get_pool()
    conn: aiomysql.Connection = await pool.acquire()
    try:
        await conn.autocommit(False)
        cursor_class = aiomysql.DictCursor if dict_cursor else aiomysql.Cursor
        cur = await conn.cursor(cursor_class)
        try:
            yield cur
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await cur.close()
    finally:
        await conn.autocommit(True)
        pool.release(conn)


async def init_tables() -> None:
    """Run the schema migration on first start."""
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

    # IMPROVED: apply incremental migrations
    updates_dir = Path(__file__).resolve().parent.parent.parent / "migrations" / "updates"
    if updates_dir.is_dir():
        for sql_file in sorted(updates_dir.glob("*.sql")):
            sql = sql_file.read_text(encoding="utf-8")
            async with get_connection() as conn:
                async with conn.cursor() as cur:
                    for statement in sql.split(";"):
                        stmt = statement.strip()
                        if stmt:
                            try:
                                await cur.execute(stmt)
                            except Exception as exc:
                                if "already exists" in str(exc).lower() or "duplicate" in str(exc).lower():
                                    continue
                                logger.warning("Migration %s skipped: %s", sql_file.name, exc)
                await conn.commit()
            logger.info("Applied migration: %s", sql_file.name)

    logger.info("Database tables initialised")
