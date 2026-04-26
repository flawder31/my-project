from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f4e6 Мои подписки", callback_data="my_subs")],
        [InlineKeyboardButton(text="\U0001f6d2 Купить VPN", callback_data="buy_vpn")],
        [InlineKeyboardButton(text="\U0001f381 Пробный период", callback_data="trial")],
        [InlineKeyboardButton(text="\U0001f517 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="\U0001f3ab Промокод", callback_data="promo_enter")],
        [InlineKeyboardButton(text="\u2139\ufe0f О сервисе", callback_data="about")],
    ])


def tariffs_kb(tariffs: list[dict[str, Any]], promo_id: int | None = None) -> InlineKeyboardMarkup:
    rows = []
    for t in tariffs:
        suffix = f" (promo:{promo_id})" if promo_id else ""
        cb = f"tariff:{t['id']}" + (f":promo:{promo_id}" if promo_id else "")
        rows.append([
            InlineKeyboardButton(
                text=f"{t['name']} — {t['price_stars']}\u2b50",
                callback_data=cb,
            )
        ])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_payment_kb(tariff_id: int, amount: int, promo_id: int | None = None) -> InlineKeyboardMarkup:
    promo_part = f":promo:{promo_id}" if promo_id else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"\u2b50 Оплатить {amount} Stars",
            callback_data=f"pay:{tariff_id}:{amount}{promo_part}",
        )],
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="buy_vpn")],
    ])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u2b05\ufe0f Главное меню", callback_data="main_menu")],
    ])


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f4ca Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="\U0001f465 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="\U0001f4b0 Платежи", callback_data="admin_payments")],
        [InlineKeyboardButton(text="\U0001f4e2 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="\U0001f3ab Промокоды", callback_data="admin_promos")],
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="main_menu")],
    ])


def admin_promo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u2795 Создать промокод", callback_data="admin_promo_create")],
        [InlineKeyboardButton(text="\U0001f4cb Список промокодов", callback_data="admin_promo_list")],
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="admin_menu")],
    ])
