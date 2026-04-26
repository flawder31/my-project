from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from bot.config import settings

logger = logging.getLogger(__name__)


class MarzbanClient:
    """Async client for Marzban Panel REST API."""

    def __init__(self) -> None:
        self._base = settings.marzban.base_url.rstrip("/")
        self._username = settings.marzban.username
        self._password = settings.marzban.password
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _auth(self) -> str:
        if self._token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._token

        session = await self._get_session()
        async with session.post(
            f"{self._base}/api/admin/token",
            data={
                "username": self._username,
                "password": self._password,
                "grant_type": "password",
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            self._token = data["access_token"]
            self._token_expires = datetime.utcnow() + timedelta(hours=11)
            logger.info("Marzban: obtained access token")
            return self._token

    async def _headers(self) -> dict[str, str]:
        token = await self._auth()
        return {"Authorization": f"Bearer {token}"}

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any] | list[Any]:
        session = await self._get_session()
        headers = await self._headers()
        url = f"{self._base}{path}"

        async with session.request(method, url, headers=headers, **kwargs) as resp:
            if resp.status >= 400:
                body = await resp.text()
                logger.error("Marzban %s %s -> %s: %s", method, path, resp.status, body)
                resp.raise_for_status()
            return await resp.json()

    # ────── User Management ──────

    async def create_user(
        self,
        username: str,
        days: int,
        device_limit: int = 1,
        data_limit_gb: float = 0,
        note: str = "",
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        expire_ts = int((now + timedelta(days=days)).timestamp())

        proxies = await self._get_default_proxies()

        payload: dict[str, Any] = {
            "username": username,
            "proxies": proxies,
            "inbounds": await self._get_default_inbounds(),
            "expire": expire_ts,
            "data_limit": int(data_limit_gb * 1024**3) if data_limit_gb else 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": note,
        }

        if device_limit > 0:
            payload["on_hold_timeout"] = None
            payload["on_hold_expire_duration"] = None

        result = await self._request("POST", "/api/user", json=payload)
        logger.info("Marzban: user %s created (expire in %d days)", username, days)
        return result

    async def get_user(self, username: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/user/{username}")

    async def modify_user(self, username: str, **fields: Any) -> dict[str, Any]:
        return await self._request("PUT", f"/api/user/{username}", json=fields)

    async def disable_user(self, username: str) -> dict[str, Any]:
        return await self.modify_user(username, status="disabled")

    async def enable_user(self, username: str) -> dict[str, Any]:
        return await self.modify_user(username, status="active")

    async def delete_user(self, username: str) -> None:
        await self._request("DELETE", f"/api/user/{username}")
        logger.info("Marzban: user %s deleted", username)

    async def get_user_subscription_url(self, username: str) -> str:
        user = await self.get_user(username)
        sub_url = user.get("subscription_url", "")
        if settings.marzban.subscription_base_url:
            return f"{settings.marzban.subscription_base_url}{sub_url}"
        return f"{self._base}{sub_url}"

    async def extend_user(
        self, username: str, extra_days: int
    ) -> dict[str, Any]:
        user = await self.get_user(username)
        current_expire = user.get("expire", 0)
        now_ts = int(datetime.utcnow().timestamp())
        base_ts = max(current_expire, now_ts)
        new_expire = base_ts + extra_days * 86400
        return await self.modify_user(username, expire=new_expire, status="active")

    # ────── System Info ──────

    async def get_system_stats(self) -> dict[str, Any]:
        return await self._request("GET", "/api/system")

    async def get_inbounds(self) -> dict[str, Any]:
        return await self._request("GET", "/api/inbounds")

    # ────── Helpers ──────

    async def _get_default_proxies(self) -> dict[str, Any]:
        try:
            inbounds = await self.get_inbounds()
            proxies: dict[str, Any] = {}
            for protocol in inbounds:
                if protocol.lower() == "vless":
                    proxies["vless"] = {"flow": "xtls-rprx-vision"}
                elif protocol.lower() == "vmess":
                    proxies["vmess"] = {}
                elif protocol.lower() == "trojan":
                    proxies["trojan"] = {"password": ""}
                elif protocol.lower() == "shadowsocks":
                    proxies["shadowsocks"] = {"method": "chacha20-ietf-poly1305"}
                else:
                    proxies[protocol] = {}
            return proxies if proxies else {"vless": {"flow": "xtls-rprx-vision"}}
        except Exception:
            return {"vless": {"flow": "xtls-rprx-vision"}}

    async def _get_default_inbounds(self) -> dict[str, list[str]]:
        try:
            inbounds_data = await self.get_inbounds()
            result: dict[str, list[str]] = {}
            for protocol, inbound_list in inbounds_data.items():
                result[protocol] = [ib["tag"] for ib in inbound_list]
            return result
        except Exception:
            return {}


marzban_client = MarzbanClient()
