"""Riven mod auctions on warframe.market.

Search endpoint (verified 2026-11-25):
  GET https://api.warframe.market/v1/auctions/search
      ?type=riven&weapon_url_name=<slug>&buyout_policy=direct&sort_by=price_asc
      [&positive_stats=a,b,c][&negative_stats=x]
  -> {"payload": {"auctions": [...]}}  (up to 100 auctions)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

from . import config
from .db import Db
from .http import HttpClient
from .models import RivenAttr, RivenLot, RivenWatch

SEARCH_URL = f"{config.MARKET_API}/v1/auctions/search"
HEADERS = {"Platform": "pc", "Crossplay": "true", "Language": "en"}
ONLINE = {"ingame", "online"}
MAX_LOTS = 30


def riven_interval(n_weapons: int) -> float:
    """Seconds between polls of one weapon so total stays <= RIVEN_MAX_RPS."""
    if n_weapons <= 0:
        return float(config.RIVEN_INTERVAL_S)
    return float(max(config.RIVEN_INTERVAL_S, math.ceil(n_weapons / config.RIVEN_MAX_RPS)))


def _parse(a: dict) -> RivenLot | None:
    item = a.get("item") or {}
    price = a.get("buyout_price")
    if price is None or item.get("type") != "riven":
        return None
    owner = a.get("owner") or {}
    return RivenLot(
        id=a["id"],
        weapon_slug=item.get("weapon_url_name", ""),
        name=item.get("name", ""),
        price=int(price),
        attributes=[
            RivenAttr(x["url_name"], float(x["value"]), bool(x["positive"])) for x in item.get("attributes", [])
        ],
        mastery=item.get("mastery_level"),
        rerolls=item.get("re_rolls"),
        polarity=item.get("polarity"),
        seller=owner.get("ingame_name", ""),
        seller_status=owner.get("status", "offline"),
        url=f"{config.MARKET_SITE}/auction/{a['id']}",
    )


def matches(lot: RivenLot, watch: RivenWatch) -> bool:
    pos = {a.url_name for a in lot.attributes if a.positive}
    neg = {a.url_name for a in lot.attributes if not a.positive}
    if not set(watch.positive) <= pos:
        return False
    if watch.negative and watch.negative not in neg:
        return False
    if watch.max_price is not None and lot.price > watch.max_price:
        return False
    return True


async def _search(http: HttpClient, weapon_slug: str, watch: RivenWatch | None) -> list[RivenLot]:
    params = {
        "type": "riven",
        "weapon_url_name": weapon_slug,
        "buyout_policy": "direct",
        "sort_by": "price_asc",
    }
    if watch and watch.positive:
        params["positive_stats"] = ",".join(watch.positive)
    if watch and watch.negative:
        params["negative_stats"] = watch.negative
    data = await http.get_json(SEARCH_URL, headers=HEADERS, params=params)
    auctions = (data.get("payload") or {}).get("auctions") or []
    lots = []
    for a in auctions:
        if a.get("closed") or a.get("visible") is False:
            continue
        lot = _parse(a)
        if lot:
            lots.append(lot)
    return lots


async def search_lots(http: HttpClient, watch: RivenWatch) -> list[RivenLot]:
    lots = [
        l for l in await _search(http, watch.weapon_slug, watch) if l.seller_status in ONLINE and matches(l, watch)
    ]
    lots.sort(key=lambda l: l.price)
    return lots[:MAX_LOTS]


def new_lots(db: Db, watch: RivenWatch, lots: list[RivenLot]) -> list[RivenLot]:
    """Lots not seen before for this watch; marks all given lots as seen."""
    seen = db.riven_seen_ids(watch.id)
    fresh = [l for l in lots if l.id not in seen]
    db.riven_mark_seen(watch.id, [l.id for l in lots])
    return fresh


async def weapon_median(http: HttpClient, weapon_slug: str) -> int | None:
    """Rough price reference: median buyout of current direct-sell lots."""
    prices = [l.price for l in await _search(http, weapon_slug, None)]
    return int(round(median(prices))) if prices else None


# Negative stats that barely hurt a weapon; rivens with them sell for more.
HARMLESS_CURSES = {
    "zoom", "recoil", "ammo_maximum", "projectile_speed", "finisher_damage", "status_duration",
    "punch_through", "impact_damage", "puncture_damage",
}
MIN_SIMILAR = 3


def is_harmless(curse: str | None) -> bool:
    if curse is None:
        return True
    return curse in HARMLESS_CURSES or curse.startswith(("damage_vs_", "damage_to_"))


def _lot_harmless(lot: RivenLot) -> bool:
    return all(is_harmless(a.url_name) for a in lot.attributes if not a.positive)


@dataclass
class RivenValue:
    price: int | None
    count: int
    basis: str  # "similar" (lots with the same positive stats) or "weapon" (any riven of the weapon)


async def riven_value(http: HttpClient, weapon_slug: str, positives: list[str], curse: str | None) -> RivenValue:
    """Price reference for one riven: median buyout of lots with the same positive stats and
    the same kind of negative (harmless/none vs harmful). Falls back to fewer stats, then to the weapon."""
    harmless = is_harmless(curse)
    stats = list(positives[:3])
    while stats:
        lots = await _search(http, weapon_slug, RivenWatch(None, weapon_slug, stats))
        same = [l for l in lots if _lot_harmless(l) == harmless]
        pool = same if len(same) >= MIN_SIMILAR else lots
        if len(pool) >= MIN_SIMILAR:
            return RivenValue(int(round(median(l.price for l in pool))), len(pool), "similar")
        if len(stats) <= 2:
            break
        stats = stats[:2]
    return RivenValue(await weapon_median(http, weapon_slug), 0, "weapon")
