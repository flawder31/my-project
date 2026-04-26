from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.db import queries
from bot.keyboards.inline import back_to_menu_kb

router = Router(name="referral")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    db_user = await queries.get_user(user_id)
    if not db_user:
        await callback.answer("Ошибка. Нажмите /start", show_alert=True)
        return

    ref_code = db_user["referral_code"]
    ref_count = await queries.count_referrals(user_id)
    bonus_days = db_user["bonus_days"]
    bot_info = await callback.bot.get_me()

    ref_link = f"https://t.me/{bot_info.username}?start={ref_code}"

    text = (
        "\U0001f517 <b>Реферальная программа</b>\n\n"
        f"Ваша реферальная ссылка:\n<code>{ref_link}</code>\n\n"
        f"\U0001f465 Приглашено друзей: <b>{ref_count}</b>\n"
        f"\U0001f381 Бонусных дней: <b>{bonus_days}</b>\n\n"
        f"За каждого друга, который оплатит подписку, "
        f"вы получите <b>{settings.subscription.referral_bonus_days}</b> бонусных дней!"
    )

    await callback.message.edit_text(
        text, reply_markup=back_to_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()
