from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from bot.db.database import get_cursor, get_transactional_cursor

logger = logging.getLogger(__name__)


# ──────────────── Users ────────────────

async def get_or_create_user(
    user_id: int,
    username: str | None,
    full_name: str,
    referral_code: str,
    referrer_id: int | None = None,
) -> dict[str, Any]:
    async with get_cursor() as cur:
        await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = await cur.fetchone()
        if row:
            if username != row.get("username"):
                await cur.execute(
                    "UPDATE users SET username = %s WHERE id = %s",
                    (username, user_id),
                )
            return row

        await cur.execute(
            """INSERT INTO users (id, username, full_name, referral_code, referrer_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (user_id, username, full_name, referral_code, referrer_id),
        )
        await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return await cur.fetchone()


async def get_user(user_id: int) -> dict[str, Any] | None:
    async with get_cursor() as cur:
        await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return await cur.fetchone()


async def set_trial_used(user_id: int) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            "UPDATE users SET trial_used = 1 WHERE id = %s", (user_id,)
        )


async def add_bonus_days(user_id: int, days: int) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            "UPDATE users SET bonus_days = bonus_days + %s WHERE id = %s",
            (days, user_id),
        )


async def get_user_by_referral_code(code: str) -> dict[str, Any] | None:
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT * FROM users WHERE referral_code = %s", (code,)
        )
        return await cur.fetchone()


async def count_users() -> int:
    async with get_cursor(dict_cursor=False) as cur:
        await cur.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_all_user_ids() -> list[int]:
    async with get_cursor(dict_cursor=False) as cur:
        await cur.execute("SELECT id FROM users WHERE is_blocked = 0")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def set_user_admin(user_id: int, is_admin: bool) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            "UPDATE users SET is_admin = %s WHERE id = %s",
            (int(is_admin), user_id),
        )


# ──────────────── Tariffs ────────────────

async def get_active_tariffs() -> list[dict[str, Any]]:
    # IMPROVED: use TTL cache to avoid hitting DB on every menu open
    from bot.utils.cache import tariff_cache
    cached = tariff_cache.get()
    if cached is not None:
        return cached

    async with get_cursor() as cur:
        await cur.execute(
            "SELECT * FROM tariffs WHERE is_active = 1 ORDER BY price_stars ASC"
        )
        result = await cur.fetchall()

    tariff_cache.set(result)
    return result


async def get_tariff(tariff_id: int) -> dict[str, Any] | None:
    async with get_cursor() as cur:
        await cur.execute("SELECT * FROM tariffs WHERE id = %s", (tariff_id,))
        return await cur.fetchone()


# ──────────────── Subscriptions ────────────────

async def create_subscription(
    user_id: int,
    tariff_id: int | None,
    marzban_username: str,
    subscription_url: str | None,
    device_limit: int,
    duration_days: int,
    is_trial: bool = False,
) -> dict[str, Any]:
    now = datetime.utcnow()
    expires = now + timedelta(days=duration_days)
    async with get_cursor() as cur:
        await cur.execute(
            """INSERT INTO subscriptions
               (user_id, tariff_id, marzban_username, subscription_url,
                device_limit, is_trial, starts_at, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, tariff_id, marzban_username, subscription_url,
             device_limit, int(is_trial), now, expires),
        )
        sub_id = cur.lastrowid
        await cur.execute(
            "SELECT * FROM subscriptions WHERE id = %s", (sub_id,)
        )
        return await cur.fetchone()


async def get_user_active_subscriptions(user_id: int) -> list[dict[str, Any]]:
    async with get_cursor() as cur:
        await cur.execute(
            """SELECT s.*, t.name as tariff_name
               FROM subscriptions s
               LEFT JOIN tariffs t ON s.tariff_id = t.id
               WHERE s.user_id = %s AND s.is_active = 1
               ORDER BY s.expires_at ASC""",
            (user_id,),
        )
        return await cur.fetchall()


# FIXED: notification queries using subscription_notifications table
async def get_expiring_subscriptions(days: int) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    target = now + timedelta(days=days)

    async with get_cursor() as cur:
        await cur.execute(
            """SELECT s.*, u.id AS tg_user_id
               FROM subscriptions s
               JOIN users u ON s.user_id = u.id
               LEFT JOIN subscription_notifications sn
                   ON sn.subscription_id = s.id AND sn.days_before = %s
               WHERE s.is_active = 1
                 AND s.expires_at <= %s
                 AND s.expires_at > %s
                 AND sn.id IS NULL""",
            (days, target, now),
        )
        return await cur.fetchall()


# FIXED: use notification table instead of hardcoded columns
async def mark_notified(sub_id: int, days: int) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            """INSERT IGNORE INTO subscription_notifications
               (subscription_id, days_before) VALUES (%s, %s)""",
            (sub_id, days),
        )


async def get_expired_active_subscriptions() -> list[dict[str, Any]]:
    now = datetime.utcnow()
    async with get_cursor() as cur:
        await cur.execute(
            """SELECT s.*, u.id as tg_user_id
               FROM subscriptions s
               JOIN users u ON s.user_id = u.id
               WHERE s.is_active = 1 AND s.expires_at <= %s""",
            (now,),
        )
        return await cur.fetchall()


async def deactivate_subscription(sub_id: int) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            "UPDATE subscriptions SET is_active = 0 WHERE id = %s", (sub_id,)
        )


# FIXED: deactivate all active subscriptions for a user (for #2 — prevent duplicates)
async def deactivate_user_subscriptions(user_id: int) -> list[dict[str, Any]]:
    """Deactivate all active subscriptions for a user, return them for Marzban cleanup."""
    async with get_cursor() as cur:
        await cur.execute(
            """SELECT marzban_username FROM subscriptions
               WHERE user_id = %s AND is_active = 1""",
            (user_id,),
        )
        old_subs = await cur.fetchall()
        await cur.execute(
            "UPDATE subscriptions SET is_active = 0 WHERE user_id = %s AND is_active = 1",
            (user_id,),
        )
        return old_subs


async def count_active_subscriptions() -> int:
    async with get_cursor(dict_cursor=False) as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE is_active = 1"
        )
        row = await cur.fetchone()
        return row[0] if row else 0


# ──────────────── Payments ────────────────

async def create_payment(
    user_id: int,
    tariff_id: int,
    amount_stars: int,
    discount_stars: int = 0,
    promo_code_id: int | None = None,
) -> dict[str, Any]:
    async with get_cursor() as cur:
        await cur.execute(
            """INSERT INTO payments
               (user_id, tariff_id, amount_stars, discount_stars, promo_code_id, status)
               VALUES (%s, %s, %s, %s, %s, 'pending')""",
            (user_id, tariff_id, amount_stars, discount_stars, promo_code_id),
        )
        pay_id = cur.lastrowid
        await cur.execute("SELECT * FROM payments WHERE id = %s", (pay_id,))
        return await cur.fetchone()


async def complete_payment(
    payment_id: int,
    telegram_payment_id: str,
    subscription_id: int,
) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            """UPDATE payments
               SET status = 'completed',
                   telegram_payment_id = %s,
                   subscription_id = %s
               WHERE id = %s""",
            (telegram_payment_id, subscription_id, payment_id),
        )


async def fail_payment(payment_id: int) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            "UPDATE payments SET status = 'failed' WHERE id = %s",
            (payment_id,),
        )


async def get_payment(payment_id: int) -> dict[str, Any] | None:
    async with get_cursor() as cur:
        await cur.execute("SELECT * FROM payments WHERE id = %s", (payment_id,))
        return await cur.fetchone()


async def count_payments(status: str = "completed") -> int:
    async with get_cursor(dict_cursor=False) as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM payments WHERE status = %s", (status,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def sum_revenue() -> int:
    async with get_cursor(dict_cursor=False) as cur:
        await cur.execute(
            "SELECT COALESCE(SUM(amount_stars), 0) FROM payments WHERE status = 'completed'"
        )
        row = await cur.fetchone()
        return row[0] if row else 0


# IMPROVED: pagination support for admin panel
async def get_recent_payments(limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
    async with get_cursor() as cur:
        await cur.execute(
            """SELECT p.*, u.username, u.full_name, t.name as tariff_name
               FROM payments p
               JOIN users u ON p.user_id = u.id
               LEFT JOIN tariffs t ON p.tariff_id = t.id
               ORDER BY p.created_at DESC LIMIT %s OFFSET %s""",
            (limit, offset),
        )
        return await cur.fetchall()


# IMPROVED: user payment history
async def get_user_payments(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    async with get_cursor() as cur:
        await cur.execute(
            """SELECT p.*, t.name as tariff_name
               FROM payments p
               LEFT JOIN tariffs t ON p.tariff_id = t.id
               WHERE p.user_id = %s
               ORDER BY p.created_at DESC LIMIT %s""",
            (user_id, limit),
        )
        return await cur.fetchall()


# ──────────────── Promo Codes ────────────────

async def get_promo_code_by_id(promo_id: int) -> dict[str, Any] | None:
    async with get_cursor() as cur:
        await cur.execute("SELECT * FROM promo_codes WHERE id = %s", (promo_id,))
        return await cur.fetchone()


async def get_promo_code(code: str) -> dict[str, Any] | None:
    now = datetime.utcnow()
    async with get_cursor() as cur:
        await cur.execute(
            """SELECT * FROM promo_codes
               WHERE code = %s AND is_active = 1
                 AND valid_from <= %s
                 AND (valid_until IS NULL OR valid_until >= %s)
                 AND (max_uses IS NULL OR used_count < max_uses)""",
            (code, now, now),
        )
        return await cur.fetchone()


# FIXED: race condition — use SELECT ... FOR UPDATE in a transaction
async def use_promo_code(promo_id: int, user_id: int) -> None:
    async with get_transactional_cursor() as cur:
        # Lock the promo code row
        await cur.execute(
            "SELECT * FROM promo_codes WHERE id = %s FOR UPDATE",
            (promo_id,),
        )
        promo = await cur.fetchone()
        if not promo:
            raise ValueError("Promo code not found")

        # Check if max uses exceeded
        if promo["max_uses"] is not None and promo["used_count"] >= promo["max_uses"]:
            raise ValueError("Promo code usage limit exceeded")

        # Check if user already used this promo
        await cur.execute(
            "SELECT id FROM promo_usage WHERE promo_code_id = %s AND user_id = %s",
            (promo_id, user_id),
        )
        if await cur.fetchone():
            raise ValueError("Promo code already used by this user")

        await cur.execute(
            "INSERT INTO promo_usage (promo_code_id, user_id) VALUES (%s, %s)",
            (promo_id, user_id),
        )
        await cur.execute(
            "UPDATE promo_codes SET used_count = used_count + 1 WHERE id = %s",
            (promo_id,),
        )


async def create_promo_code(
    code: str,
    discount_type: str,
    discount_value: int,
    max_uses: int | None = None,
    valid_until: datetime | None = None,
) -> dict[str, Any]:
    async with get_cursor() as cur:
        await cur.execute(
            """INSERT INTO promo_codes
               (code, discount_type, discount_value, max_uses, valid_until)
               VALUES (%s, %s, %s, %s, %s)""",
            (code, discount_type, discount_value, max_uses, valid_until),
        )
        pid = cur.lastrowid
        await cur.execute("SELECT * FROM promo_codes WHERE id = %s", (pid,))
        return await cur.fetchone()


async def get_all_promo_codes() -> list[dict[str, Any]]:
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT * FROM promo_codes ORDER BY created_at DESC"
        )
        return await cur.fetchall()


async def deactivate_promo_code(promo_id: int) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            "UPDATE promo_codes SET is_active = 0 WHERE id = %s", (promo_id,)
        )


def calc_discount(price: int, promo: dict[str, Any]) -> int:
    if promo["discount_type"] == "percent":
        return max(0, price - int(price * promo["discount_value"] / 100))
    return max(0, price - promo["discount_value"])


# ──────────────── Referrals ────────────────

async def create_referral(referrer_id: int, referred_id: int, bonus_days: int) -> None:
    async with get_cursor() as cur:
        try:
            await cur.execute(
                """INSERT INTO referrals (referrer_id, referred_id, bonus_days)
                   VALUES (%s, %s, %s)""",
                (referrer_id, referred_id, bonus_days),
            )
        except Exception:
            logger.debug("Referral already exists for %s -> %s", referrer_id, referred_id)


async def reward_referral(referrer_id: int, referred_id: int) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            """UPDATE referrals SET is_rewarded = 1
               WHERE referrer_id = %s AND referred_id = %s""",
            (referrer_id, referred_id),
        )


async def count_referrals(user_id: int) -> int:
    async with get_cursor(dict_cursor=False) as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = %s", (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_unrewarded_referral(referrer_id: int, referred_id: int) -> dict[str, Any] | None:
    async with get_cursor() as cur:
        await cur.execute(
            """SELECT * FROM referrals
               WHERE referrer_id = %s AND referred_id = %s AND is_rewarded = 0""",
            (referrer_id, referred_id),
        )
        return await cur.fetchone()


# FIXED: circular referral detection
async def is_referred_by(user_id: int, potential_referrer_id: int) -> bool:
    """Check if user_id has already referred potential_referrer_id (circular check)."""
    async with get_cursor(dict_cursor=False) as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = %s AND referred_id = %s",
            (user_id, potential_referrer_id),
        )
        row = await cur.fetchone()
        return (row[0] if row else 0) > 0


# ──────────────── Broadcasts ────────────────

async def create_broadcast(admin_id: int, message_text: str, total_users: int) -> dict[str, Any]:
    async with get_cursor() as cur:
        await cur.execute(
            """INSERT INTO broadcasts (admin_id, message_text, total_users, status)
               VALUES (%s, %s, %s, 'pending')""",
            (admin_id, message_text, total_users),
        )
        bid = cur.lastrowid
        await cur.execute("SELECT * FROM broadcasts WHERE id = %s", (bid,))
        return await cur.fetchone()


async def update_broadcast_progress(
    broadcast_id: int, sent: int, failed: int, status: str = "in_progress"
) -> None:
    async with get_cursor() as cur:
        await cur.execute(
            """UPDATE broadcasts
               SET sent_count = %s, failed_count = %s, status = %s,
                   completed_at = IF(%s = 'completed', NOW(), completed_at)
               WHERE id = %s""",
            (sent, failed, status, status, broadcast_id),
        )
