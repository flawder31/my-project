from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot

from bot.config import settings
from bot.db import queries
from bot.keyboards.inline import back_to_menu_kb
from bot.marzban.client import marzban_client

logger = logging.getLogger(__name__)

# IMPROVED: concurrency limit for parallel notifications
_NOTIFY_CONCURRENCY = 20


async def _send_expiry_notification(bot: Bot, sub: dict, days: int) -> None:
    """Send a single expiry notification."""
    try:
        text = (
            f"\u26a0\ufe0f <b>Подписка истекает через {days} дн.!</b>\n\n"
            f"\U0001f517 <code>{sub.get('subscription_url', '')}</code>\n\n"
            "Продлите подписку, чтобы не потерять доступ."
        )
        await bot.send_message(
            sub["tg_user_id"],
            text,
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await queries.mark_notified(sub["id"], days)
        logger.info(
            "Notified user %s about sub %s expiring in %d days",
            sub["tg_user_id"], sub["id"], days,
        )
    except Exception as exc:
        logger.warning("Failed to notify user %s: %s", sub.get("tg_user_id"), exc)


# IMPROVED: parallel notifications with semaphore
async def check_expiring_subscriptions(bot: Bot) -> None:
    """Send notifications for subscriptions expiring in configured days."""
    for days in settings.subscription.notify_before_days:
        try:
            subs = await queries.get_expiring_subscriptions(days)
            if not subs:
                continue

            semaphore = asyncio.Semaphore(_NOTIFY_CONCURRENCY)

            async def _limited_notify(sub: dict) -> None:
                async with semaphore:
                    await _send_expiry_notification(bot, sub, days)

            await asyncio.gather(
                *[_limited_notify(sub) for sub in subs],
                return_exceptions=True,
            )
            logger.info("Processed %d expiry notifications (%d days)", len(subs), days)

        except Exception as exc:
            logger.error("Error checking expiring subs (%d days): %s", days, exc)


async def disable_expired_subscriptions(bot: Bot) -> None:
    """Disable expired subscriptions in Marzban and DB."""
    try:
        expired = await queries.get_expired_active_subscriptions()
        for sub in expired:
            try:
                await marzban_client.disable_user(sub["marzban_username"])
                logger.info("Disabled Marzban user %s", sub["marzban_username"])
            except Exception as exc:
                logger.warning(
                    "Failed to disable Marzban user %s: %s",
                    sub["marzban_username"], exc,
                )

            await queries.deactivate_subscription(sub["id"])

            try:
                await bot.send_message(
                    sub["tg_user_id"],
                    "\u274c <b>Ваша подписка истекла.</b>\n\n"
                    "Приобретите новую подписку для восстановления доступа.",
                    reply_markup=back_to_menu_kb(),
                    parse_mode="HTML",
                )
            except Exception:
                pass

            logger.info("Deactivated sub %s for user %s", sub["id"], sub["tg_user_id"])
    except Exception as exc:
        logger.error("Error disabling expired subs: %s", exc)


async def scheduler_loop(bot: Bot) -> None:
    """Main scheduler loop — runs every 10 minutes."""
    logger.info("Scheduler started")
    while True:
        try:
            await check_expiring_subscriptions(bot)
            await disable_expired_subscriptions(bot)
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled, shutting down")
            break
        except Exception as exc:
            logger.error("Scheduler iteration error: %s", exc)
        await asyncio.sleep(600)  # 10 minutes
