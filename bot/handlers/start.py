from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.db import queries
from bot.keyboards.inline import main_menu_kb
from bot.utils.helpers import generate_referral_code

router = Router(name="start")
logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "\U0001f525 <b>Добро пожаловать в VPN-бот!</b>\n\n"
    "Здесь вы можете приобрести быстрый и надёжный VPN.\n"
    "Выберите действие в меню ниже:"
)

ABOUT_TEXT = (
    "\u2139\ufe0f <b>О сервисе</b>\n\n"
    "\u2022 Высокоскоростной VPN на базе VLESS/VMess\n"
    "\u2022 Оплата через Telegram Stars\n"
    "\u2022 Мгновенная выдача конфигурации\n"
    "\u2022 Пробный период — {trial_days} дней бесплатно\n"
    "\u2022 Реферальная программа — {ref_days} бонусных дней за друга\n\n"
    "По всем вопросам — /support"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if not user:
        return

    ref_code = generate_referral_code(user.id)
    referrer_id: int | None = None

    # deep-link referral
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        ref_param = args[1].strip()
        referrer = await queries.get_user_by_referral_code(ref_param)
        if referrer and referrer["id"] != user.id:
            referrer_id = referrer["id"]

    db_user = await queries.get_or_create_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        referral_code=ref_code,
        referrer_id=referrer_id,
    )

    # register referral if new
    if referrer_id and not db_user.get("referrer_id"):
        await queries.create_referral(
            referrer_id=referrer_id,
            referred_id=user.id,
            bonus_days=settings.subscription.referral_bonus_days,
        )

    is_admin = user.id in settings.bot.admin_ids
    if is_admin and not db_user.get("is_admin"):
        await queries.set_user_admin(user.id, True)

    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        WELCOME_TEXT, reply_markup=main_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery) -> None:
    text = ABOUT_TEXT.format(
        trial_days=settings.subscription.trial_days,
        ref_days=settings.subscription.referral_bonus_days,
    )
    from bot.keyboards.inline import back_to_menu_kb
    await callback.message.edit_text(
        text, reply_markup=back_to_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()
