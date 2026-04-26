from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.db import queries
from bot.keyboards.inline import confirm_payment_kb, tariffs_kb

router = Router(name="tariffs")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "buy_vpn")
async def cb_buy_vpn(callback: CallbackQuery) -> None:
    tariffs = await queries.get_active_tariffs()
    if not tariffs:
        await callback.answer("Тарифы временно недоступны", show_alert=True)
        return
    await callback.message.edit_text(
        "\U0001f6d2 <b>Выберите тариф:</b>",
        reply_markup=tariffs_kb(tariffs),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tariff:"))
async def cb_select_tariff(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    tariff_id = int(parts[1])

    promo_id: int | None = None
    if "promo" in parts:
        promo_idx = parts.index("promo")
        promo_id = int(parts[promo_idx + 1])

    tariff = await queries.get_tariff(tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    price = tariff["price_stars"]
    discount_info = ""

    if promo_id:
        promo = await queries.get_promo_code_by_id(promo_id)
        if promo:
            price = queries.calc_discount(tariff["price_stars"], promo)
            discount_info = f"\n\U0001f3ab Промокод: скидка {tariff['price_stars'] - price}\u2b50"

    text = (
        f"\U0001f4cb <b>Тариф: {tariff['name']}</b>\n\n"
        f"\u23f3 Срок: {tariff['duration_days']} дней\n"
        f"\U0001f4f1 Устройств: {tariff['device_limit']}\n"
        f"\U0001f4b0 Стоимость: {price}\u2b50"
        f"{discount_info}\n\n"
        f"Нажмите кнопку ниже для оплаты:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=confirm_payment_kb(tariff_id, price, promo_id),
        parse_mode="HTML",
    )
    await callback.answer()



