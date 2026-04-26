from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.db import queries
from bot.keyboards.inline import back_to_menu_kb
from bot.utils.helpers import format_datetime, format_days_left

router = Router(name="subscription")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "my_subs")
async def cb_my_subs(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    subs = await queries.get_user_active_subscriptions(user_id)

    if not subs:
        await callback.message.edit_text(
            "\U0001f4e6 <b>У вас нет активных подписок.</b>\n\n"
            "Вы можете приобрести VPN в разделе «Купить VPN».",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    lines = ["\U0001f4e6 <b>Ваши активные подписки:</b>\n"]
    for i, s in enumerate(subs, 1):
        tariff_name = s.get("tariff_name") or ("Пробный" if s["is_trial"] else "—")
        lines.append(
            f"{i}. <b>{tariff_name}</b>\n"
            f"   \U0001f4f1 Устройств: {s['device_limit']}\n"
            f"   \u23f3 До: {format_datetime(s['expires_at'])} "
            f"({format_days_left(s['expires_at'])})\n"
            f"   \U0001f517 <code>{s.get('subscription_url', '—')}</code>\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
