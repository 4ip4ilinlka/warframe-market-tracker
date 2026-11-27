"""Ephemera tracking: Kuva Lich and Sister of Parvos lots on warframe.market that carry an ephemera.

On the market an ephemera is part of a lich/sister auction: the item has `having_ephemera` and an
`element`, and every element maps to one ephemera (Heat lich -> Vengeful Flame, Heat sister -> Zarina).

Sources:
* /v1/auctions - the newest auctions; polled every ~20 s, lots found there are kept for two days.
* /v1/auctions/search?type=lich|sister&has_ephemera=true&element=... - per watch, every few minutes.
  (At the time of writing the market's search returns nothing for liches, also on its own site,
  so the recent feed is the main source; search results are merged when it works.)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import config
from .db import Db
from .http import HttpClient
from .models import EphLot, EphWatch, Notice  # noqa: F401 (re-exported)

log = logging.getLogger(__name__)

RECENT_URL = f"{config.MARKET_API}/v1/auctions"
SEARCH_URL = f"{config.MARKET_API}/v1/auctions/search"
KINDS = ("lich", "sister")
ELEMENTS = ("electricity", "impact", "radiation", "magnetic", "cold", "toxin", "heat")
CACHE_FILE = "ephemeras.json"
CATALOG_TTL_S = 7 * 24 * 3600
LOT_MAX_AGE_S = 48 * 3600
NOTIFY_FRESH_S = 1800  # lots created longer ago than this are not "new" (e.g. after a restart)
MAX_NOTICES = 3
POLL_S = 20
SEARCH_EVERY_S = 300
KIND_RU = {"lich": "Лич Кувы", "sister": "Сестра Парвос"}


@dataclass
class Ephemera:
    kind: str
    element: str
    slug: str
    name: str
    name_en: str
    thumb: str | None
    animation: str | None = None


def _strip_prefix(name: str) -> str:
    for p in ("Эфемера: ", "Эфемера "):
        if name.startswith(p):
            return name[len(p):]
    return name


def parse_ephemeras(kind: str, data: dict) -> list[Ephemera]:
    out = []
    for e in data.get("data") or []:
        i18n = e.get("i18n") or {}
        en, ru = i18n.get("en") or {}, i18n.get("ru") or {}
        thumb = en.get("thumb") or ru.get("thumb")
        out.append(Ephemera(kind, e.get("element", ""), e.get("slug", ""),
                            _strip_prefix(ru.get("name") or en.get("name") or e.get("slug", "")),
                            en.get("name", ""), thumb or None, e.get("animation") or None))
    return out


def _is_open(a: dict) -> bool:
    return not a.get("closed") and a.get("visible", True) is not False


def lots_from_auctions(auctions: list[dict], seen_at: float = 0.0) -> list[EphLot]:
    """Direct-sale, open lich/sister lots that have an ephemera."""
    out = []
    for a in auctions or []:
        item = a.get("item") or {}
        if item.get("type") not in KINDS or not item.get("having_ephemera"):
            continue
        if not a.get("is_direct_sell") or not _is_open(a) or a.get("buyout_price") is None:
            continue
        owner = a.get("owner") or {}
        out.append(EphLot(
            str(a["id"]), item["type"], item.get("element", ""), item.get("weapon_url_name", ""),
            item.get("damage"), int(a["buyout_price"]), owner.get("ingame_name", ""),
            owner.get("status", "offline"), a.get("created"), seen_at))
    return out


def watch_matches(w: EphWatch, lot: EphLot) -> bool:
    return (w.kind == lot.kind and w.element == lot.element and (not w.weapon or w.weapon == lot.weapon)
            and (w.max_price is None or lot.price <= w.max_price))


def _created_ts(lot: EphLot) -> float | None:
    try:
        return datetime.fromisoformat(lot.created).timestamp() if lot.created else None
    except ValueError:
        return None


class EphemeraTracker:
    def __init__(self, http: HttpClient, db: Db, cache_dir: Path, *,
                 notifier: Callable[[Notice], None] | None = None, clock: Callable[[], float] = time.time):
        if notifier is None:
            from .notify import notify as notifier
        self.http = http
        self.db = db
        self.cache_path = Path(cache_dir) / CACHE_FILE
        self.notifier = notifier
        self.clock = clock
        self.ephemeras: list[Ephemera] = []
        self.weapons: dict[str, dict[str, str]] = {k: {} for k in KINDS}
        self.updated_at: float | None = None
        self.error: str | None = None
        self._last_search = 0.0

    # --- static data ---
    def _load_cache(self) -> dict | None:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _apply(self, raw: dict) -> None:
        self.ephemeras = [Ephemera(**e) for e in raw.get("ephemeras", [])]
        self.weapons = {k: dict(raw.get("weapons", {}).get(k, {})) for k in KINDS}

    async def load_catalog(self, force: bool = False) -> None:
        raw = self._load_cache()
        if raw and not force and self.clock() - raw.get("fetched_at", 0) < CATALOG_TTL_S:
            self._apply(raw)
            return
        try:
            eph: list[Ephemera] = []
            weapons: dict[str, dict[str, str]] = {}
            for kind in KINDS:
                eph += parse_ephemeras(kind, await self.http.get_json(
                    f"{config.MARKET_API}/v2/{kind}/ephemeras", headers={"Language": "ru"}))
                data = await self.http.get_json(f"{config.MARKET_API}/v2/{kind}/weapons", headers={"Language": "ru"})
                weapons[kind] = {
                    w["slug"]: ((w.get("i18n") or {}).get("ru") or (w.get("i18n") or {}).get("en") or {}).get("name", w["slug"])
                    for w in data.get("data") or [] if w.get("slug")}
            raw = {"fetched_at": self.clock(), "ephemeras": [e.__dict__ for e in eph], "weapons": weapons}
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.cache_path)
            self._apply(raw)
        except Exception as e:
            log.warning("ephemera catalog failed: %s", type(e).__name__)
            old = self._load_cache()
            if old:
                self._apply(old)

    def weapon_name(self, kind: str, slug: str) -> str:
        return self.weapons.get(kind, {}).get(slug) or slug.replace("_", " ").title()

    def ephemera(self, kind: str, element: str) -> Ephemera | None:
        return next((e for e in self.ephemeras if e.kind == kind and e.element == element), None)

    # --- watches ---
    def add_watch(self, kind: str, element: str, weapon: str | None, max_price: int | None, *, notify: bool) -> int:
        if kind not in KINDS or element not in ELEMENTS:
            raise ValueError("unknown ephemera")
        return self.db.eph_watch_add(EphWatch(None, kind, element, weapon or None, max_price, notify))

    def remove_watch(self, watch_id: int) -> None:
        self.db.eph_watch_remove(watch_id)

    def watches(self) -> list[EphWatch]:
        return self.db.eph_watch_list()

    # --- lots ---
    def lots(self, kind: str | None = None, element: str | None = None) -> list[EphLot]:
        lots = [l for l in self.db.eph_lot_list() if (not kind or l.kind == kind) and (not element or l.element == element)]
        lots.sort(key=lambda l: (l.price, l.id))
        return lots

    def _store(self, lots: list[EphLot]) -> list[EphLot]:
        """Save lots; returns those not stored before."""
        known = self.db.eph_lot_ids()
        self.db.eph_lot_save(lots)
        return [l for l in lots if l.id not in known]

    def _notify(self, fresh: list[EphLot]) -> None:
        now = self.clock()
        fresh = [l for l in fresh if (ts := _created_ts(l)) is not None and now - ts <= NOTIFY_FRESH_S]
        if not fresh:
            return
        watches = [w for w in self.watches() if w.notify]
        hits = sorted((l for l in fresh if any(watch_matches(w, l) for w in watches)), key=lambda l: l.price)
        for l in hits[:MAX_NOTICES]:
            e = self.ephemera(l.kind, l.element)
            self.notifier(Notice(
                title=f"Эфемера: {e.name if e else l.element}",
                body=f"{self.weapon_name(l.kind, l.weapon)} — {l.price} пл. ({l.seller})",
                url=l.url))

    async def tick(self) -> None:
        """Read the newest auctions once."""
        now = self.clock()
        data = await self.http.get_json(RECENT_URL)
        auctions = (data.get("payload") or {}).get("auctions") or []
        gone = [str(a.get("id")) for a in auctions if not _is_open(a)]
        if gone:
            self.db.eph_lot_delete(gone)
        fresh = self._store(lots_from_auctions(auctions, now))
        self.db.eph_lot_prune(now - LOT_MAX_AGE_S)
        self.updated_at = now
        self.error = None
        self._notify(fresh)

    async def search_tick(self) -> None:
        now = self.clock()
        self._last_search = now
        for w in self.watches():
            params = {"type": w.kind, "has_ephemera": "true", "element": w.element}
            if w.weapon:
                params["weapon_url_name"] = w.weapon
            params.update({"buyout_policy": "direct", "sort_by": "price_asc"})
            try:
                data = await self.http.get_json(SEARCH_URL, params=params)
            except Exception as e:
                log.info("ephemera search failed: %s", type(e).__name__)
                continue
            self._notify(self._store(lots_from_auctions((data.get("payload") or {}).get("auctions") or [], now)))

    def summary(self) -> list[dict]:
        lots = self.lots()
        watched = {(w.kind, w.element) for w in self.watches()}
        out = []
        for e in self.ephemeras:
            mine = [l for l in lots if l.kind == e.kind and l.element == e.element]
            out.append({**e.__dict__, "count": len(mine), "min_price": min((l.price for l in mine), default=None),
                        "watched": (e.kind, e.element) in watched})
        return out

    # --- loop ---
    async def run(self, active: Callable[[], bool]) -> None:
        """Poll while the page is open, or while a watch with notifications exists."""
        if not self.ephemeras:
            await self.load_catalog()
        while True:
            if active() or any(w.notify for w in self.watches()):
                try:
                    await self.tick()
                    if self.watches() and self.clock() - self._last_search >= SEARCH_EVERY_S:
                        await self.search_tick()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.error = type(e).__name__
                    log.warning("ephemera poll failed: %s", self.error)
            await asyncio.sleep(POLL_S)
