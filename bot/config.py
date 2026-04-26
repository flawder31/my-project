from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _env(key: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required env variable: {key}")
    return val or ""


@dataclass(frozen=True)
class BotConfig:
    token: str = field(default_factory=lambda: _env("BOT_TOKEN", required=True))
    admin_ids: list[int] = field(
        default_factory=lambda: [
            int(x.strip())
            for x in _env("ADMIN_IDS", "").split(",")
            if x.strip()
        ]
    )


@dataclass(frozen=True)
class DBConfig:
    host: str = field(default_factory=lambda: _env("MYSQL_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("MYSQL_PORT", "3306")))
    user: str = field(default_factory=lambda: _env("MYSQL_USER", "marzban_bot"))
    password: str = field(default_factory=lambda: _env("MYSQL_PASSWORD", required=True))
    database: str = field(default_factory=lambda: _env("MYSQL_DATABASE", "marzban_bot"))
    pool_size: int = field(default_factory=lambda: int(_env("MYSQL_POOL_SIZE", "10")))


@dataclass(frozen=True)
class MarzbanConfig:
    base_url: str = field(default_factory=lambda: _env("MARZBAN_BASE_URL", required=True))
    username: str = field(default_factory=lambda: _env("MARZBAN_USERNAME", required=True))
    password: str = field(default_factory=lambda: _env("MARZBAN_PASSWORD", required=True))
    subscription_base_url: str = field(
        default_factory=lambda: _env("MARZBAN_SUBSCRIPTION_URL", "")
    )


@dataclass(frozen=True)
class SubscriptionConfig:
    trial_days: int = field(default_factory=lambda: int(_env("TRIAL_DAYS", "3")))
    trial_device_limit: int = field(
        default_factory=lambda: int(_env("TRIAL_DEVICE_LIMIT", "1"))
    )
    referral_bonus_days: int = field(
        default_factory=lambda: int(_env("REFERRAL_BONUS_DAYS", "3"))
    )
    notify_before_days: list[int] = field(
        default_factory=lambda: [3, 1]
    )


@dataclass(frozen=True)
class Settings:
    bot: BotConfig = field(default_factory=BotConfig)
    db: DBConfig = field(default_factory=DBConfig)
    marzban: MarzbanConfig = field(default_factory=MarzbanConfig)
    subscription: SubscriptionConfig = field(default_factory=SubscriptionConfig)


settings = Settings()
