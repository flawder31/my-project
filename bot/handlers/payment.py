from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from bot.config import settings
from bot.db import queries
from bot.keyboards.inline import back_to_menu_kb
from bot.marzban.client import marzban_client
from bot.utils.helpers import generate_marzban_username

router = Router(name="payment")
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    tariff_id = int(parts[1])
    amount = int(parts[2])

    promo_id: int | None = None
    if "promo" in parts:
        promo_idx = parts.index("promo")
        promo_id = int(parts[promo_idx + 1])

    tariff = await queries.get_tariff(tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    user_id = callback.from_user.id
    discount = tariff["price_stars"] - amount

    payment = await queries.create_payment(
        user_id=user_id,
        tariff_id=tariff_id,
        amount_stars=amount,
        discount_stars=discount,
        promo_code_id=promo_id,
    )

    if promo_id:
        try:
            await queries.use_promo_code(promo_id, user_id)
        except ValueError:
            pass

    prices = [LabeledPrice(label=tariff["name"], amount=amount)]

    await callback.message.answer_invoice(
        title=f"VPN — {tariff['name']}",
        description=(
            f"Срок: {tariff['duration_days']} дней\n"
            f"Устройств: {tariff['device_limit']}"
        ),
        payload=f"{payment['id']}:{tariff_id}",
        currency="XTR",
        prices=prices,
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    user = message.from_user
    if not user:
        return

    sp = message.successful_payment
    payload_parts = sp.invoice_payload.split(":")
    payment_id = int(payload_parts[0])
    tariff_id = int(payload_parts[1])

    tariff = await queries.get_tariff(tariff_id)
    if not tariff:
        await message.answer(
            "\u274c Ошибка: тариф не найден. Свяжитесь с поддержкой.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        return

    # FIXED: validate payment amount matches expected price
    payment_record = await queries.get_payment(payment_id)
    if payment_record:
        expected_amount = payment_record["amount_stars"]
        actual_amount = sp.total_amount
        if actual_amount != expected_amount:
            logger.error(
                "Payment amount mismatch! payment_id=%s expected=%s actual=%s user=%s",
                payment_id, expected_amount, actual_amount, user.id,
            )
            await queries.fail_payment(payment_id)
            await message.answer(
                "\u274c Ошибка: сумма платежа не совпадает с ожидаемой. "
                "Свяжитесь с поддержкой.\n"
                f"ID платежа: {payment_id}",
                reply_markup=back_to_menu_kb(),
                parse_mode="HTML",
            )
            return

    # FIXED: deactivate existing subscriptions to prevent duplicates
    old_subs = await queries.deactivate_user_subscriptions(user.id)
    for old_sub in old_subs:
        try:
            await marzban_client.disable_user(old_sub["marzban_username"])
            logger.info("Disabled old Marzban user %s before new purchase", old_sub["marzban_username"])
        except Exception as exc:
            logger.warning("Failed to disable old Marzban user %s: %s", old_sub["marzban_username"], exc)

    marzban_username = generate_marzban_username(user.id)

    try:
        marzban_user = await marzban_client.create_user(
            username=marzban_username,
            days=tariff["duration_days"],
            device_limit=tariff["device_limit"],
        )
        sub_url = await marzban_client.get_user_subscription_url(marzban_username)
    except Exception as exc:
        logger.error("Failed to create Marzban user: %s", exc)
        await message.answer(
            "\u274c Ошибка при создании подписки. "
            "Ваш платёж зарегистрирован — мы свяжемся с вами.\n"
            f"ID платежа: {payment_id}",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        return

    sub = await queries.create_subscription(
        user_id=user.id,
        tariff_id=tariff_id,
        marzban_username=marzban_username,
        subscription_url=sub_url,
        device_limit=tariff["device_limit"],
        duration_days=tariff["duration_days"],
    )

    await queries.complete_payment(
        payment_id=payment_id,
        telegram_payment_id=sp.telegram_payment_charge_id,
        subscription_id=sub["id"],
    )

    # FIXED: safe referral reward — use .get() for all dict access
    db_user = await queries.get_user(user.id)
    referrer_id = db_user.get("referrer_id") if db_user else None
    if referrer_id:
        ref = await queries.get_unrewarded_referral(referrer_id, user.id)
        if ref:
            bonus = ref.get("bonus_days", settings.subscription.referral_bonus_days)
            await queries.add_bonus_days(referrer_id, bonus)
            await queries.reward_referral(referrer_id, user.id)
            logger.info("Rewarded referrer %s with %d bonus days", referrer_id, bonus)

    text = (
        "\u2705 <b>Подписка активирована!</b>\n\n"
        f"\U0001f4cb Тариф: {tariff['name']}\n"
        f"\U0001f4f1 Устройств: {tariff['device_limit']}\n"
        f"\u23f3 Действует: {tariff['duration_days']} дней\n\n"
        f"\U0001f517 <b>Ваша ссылка подписки:</b>\n"
        f"<code>{sub_url}</code>\n\n"
        "Скопируйте ссылку и вставьте в приложение:\n"
        "\u2022 <b>iOS</b>: Streisand, V2Box\n"
        "\u2022 <b>Android</b>: V2rayNG, NekoBox\n"
        "\u2022 <b>Windows</b>: Nekoray, V2rayN\n"
        "\u2022 <b>macOS</b>: V2Box, Streisand"
    )

    await message.answer(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    logger.info("Payment %s completed for user %s, sub %s", payment_id, user.id, sub["id"])
