from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.db import queries
from bot.keyboards.inline import back_to_menu_kb
from bot.marzban.client import marzban_client
from bot.utils.helpers import generate_marzban_username

router = Router(name="trial")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "trial")
async def cb_trial(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    db_user = await queries.get_user(user_id)

    if not db_user:
        await callback.answer("Ошибка. Нажмите /start", show_alert=True)
        return

    if db_user["trial_used"]:
        await callback.message.edit_text(
            "\u274c <b>Пробный период уже использован.</b>\n\n"
            "Вы можете приобрести подписку в разделе «Купить VPN».",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    trial_days = settings.subscription.trial_days
    trial_devices = settings.subscription.trial_device_limit
    marzban_username = generate_marzban_username(user_id)

    # FIXED: deactivate existing subscriptions before creating trial
    old_subs = await queries.deactivate_user_subscriptions(user_id)
    for old_sub in old_subs:
        try:
            await marzban_client.disable_user(old_sub["marzban_username"])
            logger.info("Disabled old Marzban user %s before trial", old_sub["marzban_username"])
        except Exception as exc:
            logger.warning("Failed to disable old Marzban user %s: %s", old_sub["marzban_username"], exc)

    try:
        await marzban_client.create_user(
            username=marzban_username,
            days=trial_days,
            device_limit=trial_devices,
            note=f"Trial for TG user {user_id}",
        )
        sub_url = await marzban_client.get_user_subscription_url(marzban_username)
    except Exception as exc:
        logger.error("Failed to create trial for %s: %s", user_id, exc)
        await callback.message.edit_text(
            "\u274c Ошибка при активации пробного периода. Попробуйте позже.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await queries.create_subscription(
        user_id=user_id,
        tariff_id=None,
        marzban_username=marzban_username,
        subscription_url=sub_url,
        device_limit=trial_devices,
        duration_days=trial_days,
        is_trial=True,
    )
    await queries.set_trial_used(user_id)

    text = (
        "\u2705 <b>Пробный период активирован!</b>\n\n"
        f"\u23f3 Срок: {trial_days} дней\n"
        f"\U0001f4f1 Устройств: {trial_devices}\n\n"
        f"\U0001f517 <b>Ваша ссылка подписки:</b>\n"
        f"<code>{sub_url}</code>\n\n"
        "Скопируйте ссылку и вставьте в VPN-приложение."
    )
    await callback.message.edit_text(
        text, reply_markup=back_to_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()
    logger.info("Trial activated for user %s", user_id)
