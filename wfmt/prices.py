"""Prices for watched items: best online orders + 48h trade statistics."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from . import config
from .db import Db
from .http import HttpClient, MarketError
from .models import PriceSnapshot

log = logging.getLogger(__name__)
ONLINE = {"ingame", "online"}
HEADERS = {"Platform": "pc", "Language": "en", "Crossplay": "true"}


def weighted_median(rows: list[dict]) -> float | None:
    """Median of the hourly 'median' prices, each counted 'volume' times."""
    values: list[float] = []
    for r in rows:
        if r.get("median") is None:
            continue
        values.extend([float(r["median"])] * max(int(r.get("volume") or 0), 1))
    if not values:
        return None
    values.sort()
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def effective_price(snap: PriceSnapshot | None) -> int | None:
    if snap is None:
        return None
    if snap.median_48h is not None:
        median = int(round(snap.median_48h))
        # Nobody pays the median when someone sells cheaper right now.
        return min(median, snap.sell_min) if snap.sell_min is not None else median
    return snap.sell_min


def unit_price(order: dict) -> float:
    """Price of one item: bulk lots quote the price of a whole trade ("60 per trade, 6 per trade")."""
    per_trade = int(order.get("perTrade") or 1)
    return float(order["platinum"]) / max(per_trade, 1)


def _mine(o: dict, me: str | None) -> bool:
    return bool(me) and ((o.get("user") or {}).get("ingameName") or "").lower() == me.lower()


def _best(
    orders: list[dict], rank: int | None, pick, subtype: str | None = None, exclude_user: str | None = None
) -> int | None:
    prices = [
        unit_price(o)
        for o in orders
        if (o.get("user") or {}).get("status") in ONLINE
        and (rank is None or o.get("rank") in (None, rank))
        and (subtype is None or o.get("subtype") in (None, subtype))
        and not _mine(o, exclude_user)
    ]
    return int(math.floor(pick(prices) + 0.5)) if prices else None


def _stats_rows(rows: list[dict], rank: int | None, subtype: str | None = None) -> list[dict]:
    if subtype is not None and any("subtype" in r for r in rows):
        rows = [r for r in rows if r.get("subtype") == subtype]
    if not any("mod_rank" in r for r in rows):
        return rows
    want = 0 if rank is None else rank
    return [r for r in rows if r.get("mod_rank") == want]


async def fetch_top(
    http: HttpClient, slug: str, rank: int | None, subtype: str | None = None, exclude_user: str | None = None
) -> tuple[int | None, int | None]:
    """Best online sell and buy price per unit (one request)."""
    params: dict = {}
    if rank is not None:
        params["rank"] = rank
    if subtype is not None:
        params["subtype"] = subtype
    top = await http.get_json(
        f"{config.MARKET_API}/v2/orders/item/{slug}/top", headers=HEADERS, params=params or None
    )
    data = top.get("data") or {}
    return (_best(data.get("sell") or [], rank, min, subtype, exclude_user),
            _best(data.get("buy") or [], rank, max, subtype, exclude_user))


async def fetch_stats(
    http: HttpClient, slug: str, rank: int | None, subtype: str | None = None
) -> tuple[float | None, int]:
    """Median and volume of trades in the last 48 h (one request)."""
    stats = await http.get_json(f"{config.MARKET_API}/v1/items/{slug}/statistics", headers=HEADERS)
    closed = (stats.get("payload") or {}).get("statistics_closed") or {}
    rows = _stats_rows(closed.get("48hours") or [], rank, subtype)
    if not rows:
        # No trades in 48 h: use the last week of the 90-day history instead of nothing.
        rows = [r for r in _stats_rows(closed.get("90days") or [], rank, subtype) if _recent(r, RECENT_DAYS)]
    return weighted_median(rows), sum(int(r.get("volume") or 0) for r in rows)


RECENT_DAYS = 7


def _recent(row: dict, days: int) -> bool:
    try:
        t = datetime.fromisoformat(str(row.get("datetime")).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - t).days < days


def _order_view(o: dict) -> dict:
    u = o.get("user") or {}
    return {
        "name": u.get("ingameName") or "",
        "status": u.get("status") or "offline",
        "unit": int(math.floor(unit_price(o) + 0.5)),
        "per_trade": int(o.get("perTrade") or 1),
        "quantity": int(o.get("quantity") or 0),
        "reputation": u.get("reputation"),
    }


def _series(rows: list[dict]) -> list[dict]:
    return [
        {"t": r.get("datetime"), "median": r.get("median"), "min": r.get("min_price"),
         "max": r.get("max_price"), "volume": int(r.get("volume") or 0)}
        for r in rows
    ]


async def fetch_details(http: HttpClient, slug: str, rank: int | None, subtype: str | None = None) -> dict:
    """Everything the item panel shows: online sellers/buyers and 48 h / 90 day trade history."""
    params: dict = {}
    if rank is not None:
        params["rank"] = rank
    if subtype is not None:
        params["subtype"] = subtype
    top = await http.get_json(f"{config.MARKET_API}/v2/orders/item/{slug}/top", headers=HEADERS, params=params or None)
    data = top.get("data") or {}

    def keep(o):
        return ((o.get("user") or {}).get("status") in ONLINE and (rank is None or o.get("rank") in (None, rank))
                and (subtype is None or o.get("subtype") in (None, subtype)))

    sellers = sorted((_order_view(o) for o in data.get("sell") or [] if keep(o)), key=lambda x: x["unit"])
    buyers = sorted((_order_view(o) for o in data.get("buy") or [] if keep(o)), key=lambda x: -x["unit"])
    stats = await http.get_json(f"{config.MARKET_API}/v1/items/{slug}/statistics", headers=HEADERS)
    closed = (stats.get("payload") or {}).get("statistics_closed") or {}
    return {
        "sellers": sellers,
        "buyers": buyers,
        "h48": _series(_stats_rows(closed.get("48hours") or [], rank, subtype)),
        "d90": _series(_stats_rows(closed.get("90days") or [], rank, subtype)),
    }


async def fetch_price(
    http: HttpClient, slug: str, rank: int | None, *, now: datetime | None = None, subtype: str | None = None
) -> PriceSnapshot:
    sell_min, buy_max = await fetch_top(http, slug, rank, subtype)
    median, volume = await fetch_stats(http, slug, rank, subtype)
    return PriceSnapshot(slug, rank, sell_min, buy_max, median, volume, now or datetime.now(timezone.utc))


def default_subtype(catalog, slug: str) -> str | None:
    """Items with variants (relic refinement, fish size…) are priced for their first, basic variant."""
    item = catalog.by_slug(slug) if catalog is not None else None
    return item.subtypes[0] if item is not None and item.subtypes else None


async def refresh_all(
    http: HttpClient, db: Db, *, now: datetime | None = None, catalog=None
) -> list[PriceSnapshot]:
    out = []
    for w in db.watch_list():
        try:
            snap = await fetch_price(http, w.slug, w.rank, now=now, subtype=default_subtype(catalog, w.slug))
        except Exception as e:  # one bad item must not stop the others
            log.warning("price refresh failed for %s: %s", w.slug, type(e).__name__)
            continue
        db.price_save(snap)
        out.append(snap)
    return out
