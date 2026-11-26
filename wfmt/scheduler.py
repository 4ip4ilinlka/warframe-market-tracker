"""Background loops: watched prices every 5 min, riven watches every ~10 s."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

from . import config
from .alerts import check_price_alerts, riven_notices
from .catalog import Catalog
from .db import Db
from .http import HttpClient
from .models import Notice
from .prices import refresh_all
from .rivens import new_lots, riven_interval, search_lots

log = logging.getLogger(__name__)
# Marker stored among "seen" auction ids once a watch has been polled at least once.
INIT_MARK = "__polled__"
# Without an open page for this long, only riven watches with notifications keep polling.
UI_IDLE_S = 600
NEW_HIGHLIGHT_S = 60  # how long a new riven lot stays highlighted
SEEN_PRUNE_EVERY_S = 3600


class Scheduler:
    def __init__(
        self,
        http: HttpClient,
        db: Db,
        catalog: Catalog,
        *,
        notifier: Callable[[Notice], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        if notifier is None:
            from .notify import notify as notifier
        self.http = http
        self.db = db
        self.catalog = catalog
        self.notifier = notifier
        self.riven_lots: dict[int, dict] = {}
        self.last_price_refresh: datetime | None = None
        self.last_error: str | None = None
        self.last_error_at: datetime | None = None
        self._fired: set[int] = set()
        self._riven_pos = 0
        self._tasks: list[asyncio.Task] = []
        self._price_now = asyncio.Event()
        self.clock = clock
        self._last_ui = clock()
        self._first_seen: dict[tuple[int, str], float] = {}

    def ui_seen(self) -> None:
        self._last_ui = self.clock()

    def active_watches(self):
        watches = self.db.riven_watch_list()
        if self.clock() - self._last_ui <= UI_IDLE_S:
            return watches
        alerted = {a.riven_watch_id for a in self.db.alert_list() if a.kind == "riven"}
        return [w for w in watches if w.id in alerted]

    async def catalog_tick(self) -> None:
        if not self.catalog.items or self.catalog.needs_refresh():
            await self.catalog.load(force=bool(self.catalog.items))

    # --- one step of each loop (tested directly) ---
    async def price_tick(self) -> None:
        snaps = await refresh_all(self.http, self.db, catalog=self.catalog)
        self.last_price_refresh = datetime.now(timezone.utc)
        names = {}
        for s in snaps:
            item = self.catalog.by_slug(s.slug)
            if item:
                names[s.slug] = item.name_ru
        for n in check_price_alerts(self.db.alert_list(), snaps, self._fired, names):
            self.notifier(n)

    async def riven_tick(self) -> None:
        watches = self.active_watches()
        if not watches:
            return
        w = watches[self._riven_pos % len(watches)]
        self._riven_pos += 1
        first = INIT_MARK not in self.db.riven_seen_ids(w.id)
        lots = await search_lots(self.http, w)
        fresh = new_lots(self.db, w, lots)
        if first:
            self.db.riven_mark_seen(w.id, [INIT_MARK])
        now = self.clock()
        if not first:
            for l in fresh:
                self._first_seen[(w.id, l.id)] = now
        current = {l.id for l in lots}
        self.riven_lots[w.id] = {
            "lots": lots,
            "new": {
                lid for lid in current
                if now - self._first_seen.get((w.id, lid), -NEW_HIGHLIGHT_S - 1) <= NEW_HIGHLIGHT_S
            },
            "at": datetime.now(timezone.utc),
        }
        for key in [k for k in self._first_seen if k[0] == w.id and k[1] not in current]:
            del self._first_seen[key]
        if first or not fresh:
            return
        if any(a.kind == "riven" and a.riven_watch_id == w.id for a in self.db.alert_list()):
            weapon = self.catalog.riven_weapon(w.weapon_slug)
            for n in riven_notices(w, fresh, weapon.name_ru if weapon else w.weapon_slug):
                self.notifier(n)

    # --- loop plumbing ---
    async def _safe(self, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        try:
            await fn()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.last_error = f"{name}: {type(e).__name__}: {e}"
            self.last_error_at = datetime.now(timezone.utc)
            log.warning("%s loop error: %s", name, e)

    def riven_interval_s(self) -> float:
        return riven_interval(len(self.db.riven_watch_list()))

    async def _price_once(self) -> None:
        self._price_now.clear()  # requests arriving during the tick trigger another one
        await self._safe("prices", self.price_tick)

    async def _prune_seen(self) -> None:
        self.db.riven_prune_seen(datetime.now(timezone.utc), keep={INIT_MARK})

    async def _catalog_loop(self) -> None:
        while True:
            await self._safe("catalog", self.catalog_tick)
            await self._safe("prune", self._prune_seen)
            await asyncio.sleep(3600 if self.catalog.items else 60)

    async def _price_loop(self) -> None:
        while True:
            await self._price_once()
            try:
                await asyncio.wait_for(self._price_now.wait(), timeout=config.PRICE_INTERVAL_S)
            except asyncio.TimeoutError:
                pass

    async def _riven_loop(self) -> None:
        while True:
            n = len(self.active_watches())
            if n:
                await self._safe("rivens", self.riven_tick)
                await asyncio.sleep(riven_interval(n) / n)
            else:
                await asyncio.sleep(1.0)

    def refresh_prices_now(self) -> None:
        self._price_now.set()

    def start(self) -> None:
        if not self._tasks:
            self._tasks = [
                asyncio.create_task(self._catalog_loop()),
                asyncio.create_task(self._price_loop()),
                asyncio.create_task(self._riven_loop()),
            ]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks = []

    def status(self) -> dict:
        return {
            "last_price_refresh": self.last_price_refresh.isoformat() if self.last_price_refresh else None,
            "riven_interval_s": self.riven_interval_s(),
            "last_error": self.last_error,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
        }
