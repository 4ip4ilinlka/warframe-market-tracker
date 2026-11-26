"""Single HTTP client for every outbound request.

* Refuses any host outside config.ALLOWED_HOSTS.
* Sends a neutral User-Agent and nothing about the machine.
* Rate-limits requests to warframe.market (config.MARKET_MAX_RPS) and
  backs off on HTTP 429.
"""
from __future__ import annotations

import asyncio
import http.cookiejar
import time
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit

import httpx

from . import config

import logging

# httpx/httpcore log full request URLs (which may carry game session
# parameters) at INFO/DEBUG. Keep them quiet.
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)

log = logging.getLogger(__name__)
MAX_429_RETRIES = 3
DEFAULT_429_WAIT_S = 5.0
MAX_429_WAIT_S = 60.0


class ForbiddenHost(Exception):
    pass


class MarketError(Exception):
    def __init__(self, message: str, status: int | None = None, detail: str = ""):
        super().__init__(message)
        self.status = status
        self.detail = detail  # response body excerpt (never contains request URL)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def check_host(url: str) -> str:
    host = _host(url)
    if urlsplit(url).scheme != "https" or host not in config.ALLOWED_HOSTS:
        raise ForbiddenHost(host or url)
    return host


class _Queue:
    """Request spacing and 429 back-off for one class of market requests."""

    def __init__(self, min_gap: float):
        self.min_gap = min_gap
        self.last: float | None = None
        self.blocked_until = 0.0
        self.lock = asyncio.Lock()


class HttpClient:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        transport: httpx.AsyncBaseTransport | None = None,
        max_rps: float = config.MARKET_MAX_RPS,
    ):
        self._clock = clock
        self._sleep = sleep
        # Riven auction search has a stricter limit on the market side: its own, slower queue.
        scale = config.MARKET_MAX_RPS / max_rps
        self._queues = {
            "market": _Queue(1.0 / max_rps),
            "auctions": _Queue(scale / config.AUCTION_MAX_RPS),
        }
        self._client = httpx.AsyncClient(
            headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"},
            timeout=httpx.Timeout(20.0),
            transport=transport,
            follow_redirects=False,
        )
        # Never keep or send cookies: anonymous polling must not carry a market session.
        self._client.cookies.jar.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))

    async def _throttle(self, q: _Queue) -> None:
        async with q.lock:
            now = self._clock()
            if q.blocked_until > now:
                await self._sleep(q.blocked_until - now)
                now = self._clock()
            if q.last is not None:
                wait = q.last + q.min_gap - now
                if wait > 0:
                    await self._sleep(wait)
            q.last = self._clock()

    async def request(self, method: str, url: str, **kw: Any) -> httpx.Response:
        host = check_host(url)
        limited = host.endswith("warframe.market")
        q = self._queues["auctions" if "/auctions" in url else "market"]
        # Only idempotent market reads are retried; never game servers or sign-in/order writes.
        retries = MAX_429_RETRIES if (limited and method == "GET") else 0
        for attempt in range(retries + 1):
            if limited:
                await self._throttle(q)
            try:
                resp = await self._client.request(method, url, **kw)
            except httpx.HTTPError as e:
                raise MarketError(f"network error: {type(e).__name__}") from None
            if resp.status_code == 429:
                try:
                    wait = float(resp.headers.get("Retry-After", DEFAULT_429_WAIT_S))
                except ValueError:
                    wait = DEFAULT_429_WAIT_S
                wait = max(0.0, min(wait, MAX_429_WAIT_S))
                if limited:
                    q.blocked_until = max(q.blocked_until, self._clock() + wait)
                    log.warning("market asked to slow down (%s queue, %.0f s)", "auctions" if q is self._queues["auctions"] else "market", wait)
                if attempt < retries:
                    continue  # _throttle waits out the shared block
            if resp.status_code >= 400:
                raise MarketError(
                    f"HTTP {resp.status_code} from {host}", resp.status_code, resp.text[:500]
                )
            return resp
        raise MarketError("unreachable", None)  # pragma: no cover

    @staticmethod
    def _json(resp: httpx.Response) -> dict:
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            raise MarketError("invalid JSON", resp.status_code) from None

    async def get_json(self, url: str, *, headers=None, params=None) -> dict:
        return self._json(await self.request("GET", url, headers=headers, params=params))

    async def post_json(self, url: str, json: Any, *, headers=None) -> tuple[dict, httpx.Headers]:
        resp = await self.request("POST", url, headers=headers, json=json)
        return self._json(resp), resp.headers

    async def patch_json(self, url: str, json: Any, *, headers=None) -> dict:
        return self._json(await self.request("PATCH", url, headers=headers, json=json))

    async def delete(self, url: str, *, headers=None) -> None:
        await self.request("DELETE", url, headers=headers)

    async def aclose(self) -> None:
        await self._client.aclose()
