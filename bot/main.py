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
from bot.handlers import admin, payment, promo, referral, start, subscription, tariffs, trial
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


async def on_startup(bot: Bot) -> None:
    logger.info("Starting up...")
    await create_pool()
    await init_tables()

    # verify Marzban connection
    try:
        await marzban_client._auth()
        logger.info("Marzban connection OK")
    except Exception as exc:
        logger.error("Marzban connection FAILED: %s", exc)

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
        admin.router,
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # start scheduler in background
    scheduler_task = asyncio.create_task(scheduler_loop(bot))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
