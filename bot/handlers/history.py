from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.db import queries
from bot.keyboards.inline import back_to_menu_kb
from bot.utils.helpers import format_datetime

router = Router(name="history")
logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "completed": "\u2705",
    "pending": "\u23f3",
    "failed": "\u274c",
    "refunded": "\U0001f504",
}


@router.callback_query(F.data == "payment_history")
async def cb_payment_history(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    payments = await queries.get_user_payments(user_id, limit=10)

    if not payments:
        await callback.message.edit_text(
            "\U0001f4b0 <b>У вас пока нет платежей.</b>\n\n"
            "Приобретите VPN в разделе «Купить VPN».",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    lines = ["\U0001f4b0 <b>Ваши последние платежи:</b>\n"]
    for p in payments:
        status_icon = _STATUS_MAP.get(p["status"], "\u2753")
        tariff_name = p.get("tariff_name") or "—"
        lines.append(
            f"{status_icon} {format_datetime(p['created_at'])} | "
            f"{tariff_name} | {p['amount_stars']}\u2b50"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
