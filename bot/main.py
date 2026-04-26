from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.db.database import close_pool, create_pool, init_tables
from bot.handlers import admin, history, payment, promo, referral, start, subscription, tariffs, trial
from bot.marzban.client import marzban_client
from bot.middlewares.db import DatabaseMiddleware
from bot.scheduler.tasks import scheduler_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# IMPROVED: startup healthcheck config
_DB_RETRY_ATTEMPTS = 10
_DB_RETRY_DELAY = 3.0
_MARZBAN_RETRY_ATTEMPTS = 5
_MARZBAN_RETRY_DELAY = 5.0


# IMPROVED: healthcheck with retry at startup
async def on_startup(bot: Bot) -> None:
    logger.info("Starting up...")

    # DB connection with retry
    for attempt in range(1, _DB_RETRY_ATTEMPTS + 1):
        try:
            await create_pool()
            await init_tables()
            logger.info("MySQL connection OK")
            break
        except Exception as exc:
            if attempt == _DB_RETRY_ATTEMPTS:
                logger.critical("MySQL connection FAILED after %d attempts: %s", _DB_RETRY_ATTEMPTS, exc)
                raise SystemExit(1)
            logger.warning("MySQL connection attempt %d/%d failed: %s. Retrying in %.0fs...",
                           attempt, _DB_RETRY_ATTEMPTS, exc, _DB_RETRY_DELAY)
            await asyncio.sleep(_DB_RETRY_DELAY)

    # Marzban connection with retry
    for attempt in range(1, _MARZBAN_RETRY_ATTEMPTS + 1):
        try:
            ok = await marzban_client.healthcheck()
            if ok:
                logger.info("Marzban connection OK")
                break
            raise ConnectionError("healthcheck returned False")
        except Exception as exc:
            if attempt == _MARZBAN_RETRY_ATTEMPTS:
                logger.error("Marzban connection FAILED after %d attempts: %s. "
                             "Bot will start but VPN operations may fail.",
                             _MARZBAN_RETRY_ATTEMPTS, exc)
                break
            logger.warning("Marzban connection attempt %d/%d failed: %s. Retrying in %.0fs...",
                           attempt, _MARZBAN_RETRY_ATTEMPTS, exc, _MARZBAN_RETRY_DELAY)
            await asyncio.sleep(_MARZBAN_RETRY_DELAY)

    me = await bot.get_me()
    logger.info("Bot @%s started", me.username)


async def on_shutdown(bot: Bot) -> None:
    logger.info("Shutting down...")
    await marzban_client.close()
    await close_pool()


async def main() -> None:
    bot = Bot(
        token=settings.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    dp.include_routers(
        start.router,
        tariffs.router,
        payment.router,
        subscription.router,
        trial.router,
        referral.router,
        promo.router,
        history.router,
        admin.router,
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # FIXED: proper scheduler lifecycle with graceful shutdown
    scheduler_task = asyncio.create_task(scheduler_loop(bot))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler_task.cancel()
        with asyncio.CancelledError:
            try:
                await scheduler_task
            except asyncio.CancelledError:
                logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
