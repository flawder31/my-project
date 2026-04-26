from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.db import queries
from bot.keyboards.inline import back_to_menu_kb, tariffs_kb

router = Router(name="promo")
logger = logging.getLogger(__name__)


class PromoStates(StatesGroup):
    waiting_code = State()


@router.callback_query(F.data == "promo_enter")
async def cb_promo_enter(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "\U0001f3ab <b>Введите промокод:</b>",
        parse_mode="HTML",
    )
    await state.set_state(PromoStates.waiting_code)
    await callback.answer()


@router.message(PromoStates.waiting_code)
async def msg_promo_code(message: Message, state: FSMContext) -> None:
    code = message.text.strip().upper()
    promo = await queries.get_promo_code(code)

    if not promo:
        await message.answer(
            "\u274c Промокод не найден или уже недействителен.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await state.clear()
        return

    # Check if user already used this promo
    from bot.db.database import get_cursor
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT id FROM promo_usage WHERE promo_code_id = %s AND user_id = %s",
            (promo["id"], message.from_user.id),
        )
        if await cur.fetchone():
            await message.answer(
                "\u274c Вы уже использовали этот промокод.",
                reply_markup=back_to_menu_kb(),
                parse_mode="HTML",
            )
            await state.clear()
            return

    discount_text = (
        f"{promo['discount_value']}%"
        if promo["discount_type"] == "percent"
        else f"{promo['discount_value']}\u2b50"
    )

    tariffs = await queries.get_active_tariffs()
    await message.answer(
        f"\u2705 Промокод <b>{code}</b> применён!\n"
        f"Скидка: <b>{discount_text}</b>\n\n"
        "Выберите тариф:",
        reply_markup=tariffs_kb(tariffs, promo_id=promo["id"]),
        parse_mode="HTML",
    )
    await state.clear()
