from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime


def generate_referral_code(user_id: int) -> str:
    raw = f"{user_id}-{secrets.token_hex(4)}"
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def generate_marzban_username(user_id: int) -> str:
    ts = int(datetime.utcnow().timestamp())
    return f"tg_{user_id}_{ts}"


def format_datetime(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


def format_days_left(expires_at: datetime) -> str:
    delta = expires_at - datetime.utcnow()
    days = delta.days
    if days < 0:
        return "Истекла"
    if days == 0:
        hours = delta.seconds // 3600
        return f"{hours} ч."
    return f"{days} дн."


def generate_promo_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))
