"""Sets you can build from parts in your inventory, and whether a set sells better than its parts."""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from . import config
from .catalog import Catalog
from .db import Db
from .http import HttpClient
from .prices import default_subtype, effective_price, fetch_price
from .visual import set_slug_for

log = logging.getLogger(__name__)


def _owned(catalog: Catalog, db: Db) -> dict[str, int]:
    from .sell import normalize_ref  # local import: sell imports this module's neighbours

    items, _, _ = db.inventory_load()
    owned: dict[str, int] = defaultdict(int)
    for inv in items:
        cat = catalog.by_game_ref(inv.game_ref) or catalog.by_game_ref(normalize_ref(inv.game_ref))
        if cat:
            owned[cat.slug] += inv.count
    return owned


def catalog_parts(catalog: Catalog, set_slug: str) -> list[str]:
    """Parts of a set as the catalog names them (without quantities)."""
    base = set_slug[: -len("_set")]
    return [i.slug for i in catalog.items
            if i.slug != set_slug and i.slug.startswith(base + "_") and set_slug_for(i.slug) == set_slug]


def candidate_sets(catalog: Catalog, db: Db) -> list[str]:
    """Sets for which you own at least one of every part."""
    owned = _owned(catalog, db)
    sets = {set_slug_for(slug) for slug in owned}
    out = []
    for s in sorted(x for x in sets if x and catalog.by_slug(x)):
        parts = catalog_parts(catalog, s)
        if len(parts) >= 2 and all(owned.get(p, 0) > 0 for p in parts):
            out.append(s)
    return out


async def fetch_set_parts(http: HttpClient, catalog: Catalog, db: Db, set_slug: str) -> list[tuple[str, int]]:
    """Exact composition of a set (part, quantity), fetched once and cached for good."""
    cached = db.set_parts_get(set_slug)
    if cached is not None:
        return cached
    data = (await http.get_json(f"{config.MARKET_API}/v2/item/{set_slug}")).get("data") or {}
    set_item = catalog.by_slug(set_slug)
    parts = []
    for pid in data.get("setParts") or []:
        part = catalog.by_id(pid)
        if part is None or (set_item and part.id == set_item.id):
            continue
        detail = (await http.get_json(f"{config.MARKET_API}/v2/item/{part.slug}")).get("data") or {}
        parts.append((part.slug, int(detail.get("quantityInSet") or 1)))
    if parts:
        db.set_parts_save(set_slug, parts)
    return parts


async def fill_sets(catalog: Catalog, http: HttpClient, db: Db, *, now: datetime | None = None) -> None:
    """Background step: learn set compositions and make sure set prices are known."""
    now = now or datetime.now(timezone.utc)
    for s in candidate_sets(catalog, db):
        try:
            await fetch_set_parts(http, catalog, db, s)
            snap = db.price_latest(s, None)
            if snap is None or now - snap.at > timedelta(seconds=config.INVENTORY_PRICE_FRESH_S):
                db.price_save(await fetch_price(http, s, None, now=now, subtype=default_subtype(catalog, s)))
        except Exception as e:
            log.warning("set %s skipped: %s", s, type(e).__name__)


def buildable_sets(catalog: Catalog, db: Db) -> list[dict]:
    owned = _owned(catalog, db)
    out = []
    for s in candidate_sets(catalog, db):
        parts = db.set_parts_get(s)
        if not parts:
            continue
        count = min(owned.get(p, 0) // q for p, q in parts)
        if count < 1:
            continue
        set_price = effective_price(db.price_latest(s, None))
        part_prices = [effective_price(db.price_latest(p, None)) for p, _ in parts]
        parts_price = (sum(q * pp for (_, q), pp in zip(parts, part_prices))
                       if all(pp is not None for pp in part_prices) else None)
        gain = set_price - parts_price if set_price is not None and parts_price is not None else None
        item = catalog.by_slug(s)
        out.append({
            "slug": s, "item_id": item.id, "name": item.name_ru, "thumb": item.thumb, "count": count,
            "set_price": set_price, "parts_price": parts_price, "gain": gain,
            "better": None if gain is None else ("set" if gain > 0 else "parts"),
            "ducats": getattr(item, "ducats", None),
            "parts": [{"slug": p, "name": catalog.by_slug(p).name_ru, "qty": q, "owned": owned.get(p, 0)} for p, q in parts],
        })
    out.sort(key=lambda x: -(x["count"] * max(x["set_price"] or 0, x["parts_price"] or 0)))
    return out
