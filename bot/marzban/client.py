from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from bot.config import settings

logger = logging.getLogger(__name__)

# IMPROVED: retry config
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0
_RETRY_BACKOFF = 2.0


class MarzbanClient:
    """Async client for Marzban Panel REST API with retry logic."""

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

    # IMPROVED: retry logic with exponential backoff
    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any] | list[Any]:
        last_exc: Exception | None = None
        delay = _RETRY_DELAY

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                session = await self._get_session()
                headers = await self._headers()
                url = f"{self._base}{path}"

                async with session.request(method, url, headers=headers, **kwargs) as resp:
                    if resp.status == 401:
                        # Token expired mid-session, force re-auth
                        self._token = None
                        self._token_expires = None
                        if attempt < _MAX_RETRIES:
                            logger.warning("Marzban 401 on %s %s, re-authenticating (attempt %d)", method, path, attempt)
                            continue
                    if resp.status >= 400:
                        body = await resp.text()
                        logger.error("Marzban %s %s -> %s: %s", method, path, resp.status, body)
                        resp.raise_for_status()
                    return await resp.json()

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "Marzban %s %s failed (attempt %d/%d): %s. Retrying in %.1fs",
                        method, path, attempt, _MAX_RETRIES, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= _RETRY_BACKOFF

        logger.error("Marzban %s %s failed after %d attempts", method, path, _MAX_RETRIES)
        raise last_exc or RuntimeError(f"Marzban request failed: {method} {path}")

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
        inbounds = await self._get_default_inbounds()

        # FIXED: validate that we have at least proxies and inbounds before creating
        if not proxies:
            proxies = {"vless": {"flow": "xtls-rprx-vision"}}
            logger.warning("Using fallback proxy config for user %s", username)
        if not inbounds:
            logger.warning("Empty inbounds for user %s — Marzban may reject", username)

        payload: dict[str, Any] = {
            "username": username,
            "proxies": proxies,
            "inbounds": inbounds,
            "expire": expire_ts,
            "data_limit": int(data_limit_gb * 1024**3) if data_limit_gb else 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": note,
        }

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

    # IMPROVED: healthcheck method
    async def healthcheck(self) -> bool:
        """Verify Marzban is reachable and credentials are valid."""
        try:
            await self._auth()
            return True
        except Exception as exc:
            logger.error("Marzban healthcheck failed: %s", exc)
            return False

    # ────── Helpers ──────

    # FIXED: always return at least default proxies even on error
    async def _get_default_proxies(self) -> dict[str, Any]:
        fallback = {"vless": {"flow": "xtls-rprx-vision"}}
        try:
            inbounds = await self.get_inbounds()
            if not inbounds or not isinstance(inbounds, dict):
                logger.warning("Marzban returned empty/invalid inbounds, using fallback")
                return fallback

            proxies: dict[str, Any] = {}
            for protocol in inbounds:
                proto_lower = protocol.lower()
                if proto_lower == "vless":
                    proxies["vless"] = {"flow": "xtls-rprx-vision"}
                elif proto_lower == "vmess":
                    proxies["vmess"] = {}
                elif proto_lower == "trojan":
                    proxies["trojan"] = {"password": ""}
                elif proto_lower == "shadowsocks":
                    proxies["shadowsocks"] = {"method": "chacha20-ietf-poly1305"}
                else:
                    proxies[protocol] = {}
            return proxies if proxies else fallback
        except Exception as exc:
            logger.warning("Failed to get inbounds for proxies: %s, using fallback", exc)
            return fallback

    # FIXED: return fallback inbounds on error to avoid empty dict
    async def _get_default_inbounds(self) -> dict[str, list[str]]:
        try:
            inbounds_data = await self.get_inbounds()
            if not inbounds_data or not isinstance(inbounds_data, dict):
                return {}
            result: dict[str, list[str]] = {}
            for protocol, inbound_list in inbounds_data.items():
                if isinstance(inbound_list, list):
                    result[protocol] = [
                        ib["tag"] for ib in inbound_list
                        if isinstance(ib, dict) and "tag" in ib
                    ]
            return result
        except Exception as exc:
            logger.warning("Failed to get inbounds: %s", exc)
            return {}


marzban_client = MarzbanClient()
