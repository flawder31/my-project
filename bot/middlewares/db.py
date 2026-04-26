from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)

# IMPROVED: throttle + DB availability check
_THROTTLE_SECONDS = 0.5
_user_last_request: dict[int, float] = defaultdict(float)


class DatabaseMiddleware(BaseMiddleware):
    """Throttle rapid requests and verify DB availability."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Extract user_id for throttling
        user_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = time.monotonic()
            last = _user_last_request.get(user_id, 0.0)
            if now - last < _THROTTLE_SECONDS:
                if isinstance(event, CallbackQuery):
                    await event.answer()
                return None
            _user_last_request[user_id] = now

        # Check DB pool availability
        from bot.db.database import _pool
        if _pool is None:
            logger.error("DB pool is not available — dropping request from user %s", user_id)
            if isinstance(event, Message):
                await event.answer("Сервис временно недоступен. Попробуйте позже.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Сервис временно недоступен", show_alert=True)
            return None

        return await handler(event, data)
