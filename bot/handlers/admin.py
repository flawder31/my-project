from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.db import queries
from bot.keyboards.inline import admin_menu_kb, admin_promo_kb, back_to_menu_kb
from bot.utils.helpers import format_datetime, generate_promo_code

router = Router(name="admin")
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in settings.bot.admin_ids


class AdminStates(StatesGroup):
    broadcast_text = State()
    promo_code = State()
    promo_type = State()
    promo_value = State()
    promo_max_uses = State()
    promo_valid_until = State()


# ──────────────── Admin entry ────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "\U0001f6e0 <b>Админ-панель</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(
        "\U0001f6e0 <b>Админ-панель</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────── Statistics ────────────────

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    total_users = await queries.count_users()
    active_subs = await queries.count_active_subscriptions()
    total_payments = await queries.count_payments()
    revenue = await queries.sum_revenue()

    text = (
        "\U0001f4ca <b>Статистика</b>\n\n"
        f"\U0001f465 Пользователей: <b>{total_users}</b>\n"
        f"\U0001f4e6 Активных подписок: <b>{active_subs}</b>\n"
        f"\U0001f4b0 Платежей: <b>{total_payments}</b>\n"
        f"\u2b50 Доход: <b>{revenue} Stars</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────── Users list ────────────────

@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    total = await queries.count_users()
    text = (
        f"\U0001f465 <b>Пользователи</b>\n\n"
        f"Всего: <b>{total}</b>\n\n"
        "Используйте /user_info &lt;telegram_id&gt; для просмотра информации."
    )
    await callback.message.edit_text(
        text, reply_markup=admin_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("user_info"))
async def cmd_user_info(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /user_info <telegram_id>")
        return

    try:
        target_id = int(args[1].strip())
    except ValueError:
        await message.answer("ID должен быть числом")
        return

    user = await queries.get_user(target_id)
    if not user:
        await message.answer("Пользователь не найден")
        return

    subs = await queries.get_user_active_subscriptions(target_id)
    ref_count = await queries.count_referrals(target_id)

    sub_lines = []
    for s in subs:
        sub_lines.append(
            f"  \u2022 {s.get('tariff_name', 'Trial')} — до {format_datetime(s['expires_at'])}"
        )

    text = (
        f"\U0001f464 <b>Пользователь</b>\n\n"
        f"ID: <code>{user['id']}</code>\n"
        f"Username: @{user['username'] or '—'}\n"
        f"Имя: {user['full_name']}\n"
        f"Рег.: {format_datetime(user['created_at'])}\n"
        f"Trial: {'Да' if user['trial_used'] else 'Нет'}\n"
        f"Бонус дней: {user['bonus_days']}\n"
        f"Рефералов: {ref_count}\n\n"
        f"<b>Подписки ({len(subs)}):</b>\n"
        + ("\n".join(sub_lines) if sub_lines else "  Нет активных")
    )
    await message.answer(text, parse_mode="HTML")


# ──────────────── Payments ────────────────

@router.callback_query(F.data == "admin_payments")
async def cb_admin_payments(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    payments = await queries.get_recent_payments(10)
    if not payments:
        await callback.message.edit_text(
            "\U0001f4b0 <b>Платежей пока нет.</b>",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    lines = ["\U0001f4b0 <b>Последние платежи:</b>\n"]
    for p in payments:
        name = p.get("username") or p.get("full_name", "—")
        lines.append(
            f"\u2022 {format_datetime(p['created_at'])} | "
            f"@{name} | {p['amount_stars']}\u2b50 | "
            f"{p.get('tariff_name', '—')} | {p['status']}"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────── Broadcast ────────────────

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "\U0001f4e2 <b>Рассылка</b>\n\n"
        "Отправьте текст сообщения для рассылки всем пользователям.\n"
        "Отмена: /cancel",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.broadcast_text)
    await callback.answer()


@router.message(AdminStates.broadcast_text)
async def msg_broadcast_text(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer(
            "Рассылка отменена.", reply_markup=admin_menu_kb()
        )
        return

    text = message.text or ""
    user_ids = await queries.get_all_user_ids()
    total = len(user_ids)

    if total == 0:
        await message.answer("Нет пользователей для рассылки.")
        await state.clear()
        return

    broadcast = await queries.create_broadcast(message.from_user.id, text, total)
    await message.answer(f"\U0001f4e2 Начинаю рассылку ({total} пользователей)...")

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # rate limit

    await queries.update_broadcast_progress(
        broadcast["id"], sent, failed, "completed"
    )

    await message.answer(
        f"\u2705 Рассылка завершена!\n"
        f"Отправлено: {sent}\nОшибок: {failed}",
        reply_markup=admin_menu_kb(),
    )
    await state.clear()


# ──────────────── Promo Management ────────────────

@router.callback_query(F.data == "admin_promos")
async def cb_admin_promos(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "\U0001f3ab <b>Управление промокодами</b>",
        reply_markup=admin_promo_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_promo_list")
async def cb_admin_promo_list(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    promos = await queries.get_all_promo_codes()
    if not promos:
        await callback.message.edit_text(
            "\U0001f3ab Промокодов нет.",
            reply_markup=admin_promo_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    lines = ["\U0001f3ab <b>Промокоды:</b>\n"]
    for p in promos:
        status = "\u2705" if p["is_active"] else "\u274c"
        dtype = f"{p['discount_value']}%" if p["discount_type"] == "percent" else f"{p['discount_value']}\u2b50"
        uses = f"{p['used_count']}/{p['max_uses'] or '\u221e'}"
        lines.append(
            f"{status} <code>{p['code']}</code> — {dtype} | "
            f"Исп: {uses} | До: {format_datetime(p.get('valid_until'))}"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_promo_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_promo_create")
async def cb_admin_promo_create(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    auto_code = generate_promo_code()
    await callback.message.edit_text(
        "\U0001f3ab <b>Создание промокода</b>\n\n"
        f"Введите код или нажмите /auto для автоматического (<code>{auto_code}</code>).\n"
        "Отмена: /cancel",
        parse_mode="HTML",
    )
    await state.update_data(auto_code=auto_code)
    await state.set_state(AdminStates.promo_code)
    await callback.answer()


@router.message(AdminStates.promo_code)
async def msg_promo_code(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_kb())
        return

    data = await state.get_data()
    code = data["auto_code"] if text == "/auto" else text.upper()

    await state.update_data(code=code)
    await message.answer(
        "Тип скидки:\n"
        "1 — Процент\n"
        "2 — Фиксированная (в Stars)\n\n"
        "Введите 1 или 2:"
    )
    await state.set_state(AdminStates.promo_type)


@router.message(AdminStates.promo_type)
async def msg_promo_type(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if text not in ("1", "2"):
        await message.answer("Введите 1 или 2")
        return

    dtype = "percent" if text == "1" else "fixed"
    await state.update_data(discount_type=dtype)
    label = "процент (1-100)" if dtype == "percent" else "сумма в Stars"
    await message.answer(f"Введите значение скидки ({label}):")
    await state.set_state(AdminStates.promo_value)


@router.message(AdminStates.promo_value)
async def msg_promo_value(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        value = int(message.text.strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число.")
        return

    await state.update_data(discount_value=value)
    await message.answer(
        "Максимальное количество использований (или 0 для безлимита):"
    )
    await state.set_state(AdminStates.promo_max_uses)


@router.message(AdminStates.promo_max_uses)
async def msg_promo_max_uses(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        max_uses = int(message.text.strip())
        if max_uses < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите неотрицательное число.")
        return

    data = await state.get_data()

    promo = await queries.create_promo_code(
        code=data["code"],
        discount_type=data["discount_type"],
        discount_value=data["discount_value"],
        max_uses=max_uses if max_uses > 0 else None,
    )

    dtype = (
        f"{promo['discount_value']}%"
        if promo["discount_type"] == "percent"
        else f"{promo['discount_value']}\u2b50"
    )

    await message.answer(
        f"\u2705 Промокод создан!\n\n"
        f"Код: <code>{promo['code']}</code>\n"
        f"Скидка: {dtype}\n"
        f"Лимит: {max_uses if max_uses > 0 else 'безлимит'}",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await state.clear()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=back_to_menu_kb())
