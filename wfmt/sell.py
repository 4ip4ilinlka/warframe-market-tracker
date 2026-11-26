"""'What to sell': match the saved inventory against market prices."""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import config
from .catalog import Catalog
from .db import Db
from .http import HttpClient, MarketError
from .models import PriceSnapshot
from .prices import default_subtype, effective_price, fetch_stats, fetch_top
from .rivens import RivenValue, is_harmless, riven_value
from .visual import SUBCAT_LABELS, category_of, part_of, rarity_of, relic_tier, set_slug_for, subcategory_of, unmatched_group

log = logging.getLogger(__name__)


@dataclass
class SellRow:
    slug: str
    item_id: str
    name: str
    tags: list[str]
    count: int
    rank: int | None
    unit_price: int | None
    total: int | None
    price_at: datetime | None
    thumb: str | None
    price_rank: int | None = None
    market_min: int | None = None
    category: str = "other"
    part: str | None = None
    max_rank: int | None = None
    rarity: str | None = None
    tier: str | None = None
    sub: str = "other:other"
    sub_label: str = ""


@dataclass
class SellRiven:
    weapon_slug: str | None
    weapon_name: str
    buffs: list[tuple[str, float]]
    curses: list[tuple[str, float]]
    rerolls: int | None
    mastery: int | None
    reference_price: int | None
    reference_count: int = 0
    reference_basis: str | None = None  # "similar" or "weapon"
    curse_harmless: bool = True
    weapon_thumb: str | None = None


@dataclass
class SellList:
    rows: list[SellRow]
    rivens: list[SellRiven]
    unmatched: int
    inventory_at: datetime | None
    unmatched_groups: dict[str, int] | None = None


RELIC_PREFIX = "/Lotus/Types/Game/Projections/"
# Inventory relic refs carry the refinement: Bronze=intact, Silver=exceptional,
# Gold=flawless, Platinum=radiant. The market ref has no suffix.
REFINEMENTS = ("Bronze", "Silver", "Gold", "Platinum")


def normalize_ref(ref: str) -> str:
    if ref.startswith(RELIC_PREFIX):
        for suffix in REFINEMENTS:
            if ref.endswith(suffix):
                return ref[: -len(suffix)]
    return ref


def price_rank(inv_rank: int | None, max_rank: int | None) -> int | None:
    """Rank whose price applies: max rank if fully ranked, else rank 0; None for unranked items."""
    if max_rank is None:
        return None
    return max_rank if inv_rank == max_rank else 0


def _grouped(catalog: Catalog, db: Db):
    """Inventory grouped by (slug, real rank); unmatched entries counted by group."""
    items, rivens, at = db.inventory_load()
    groups: dict[tuple[str, int | None], int] = defaultdict(int)
    unmatched: dict[str, int] = defaultdict(int)
    for inv in items:
        cat = catalog.by_game_ref(inv.game_ref) or catalog.by_game_ref(normalize_ref(inv.game_ref))
        if cat is None:
            unmatched[unmatched_group(inv.game_ref)] += 1
            continue
        rank = inv.rank if cat.max_rank is not None else None
        groups[(cat.slug, rank)] += inv.count
    return groups, rivens, at, dict(unmatched)


def _price_keys(catalog: Catalog, groups) -> list[tuple[str, int | None]]:
    keys = []
    for slug, rank in groups:
        cat = catalog.by_slug(slug)
        key = (slug, price_rank(rank, cat.max_rank))
        if key not in keys:
            keys.append(key)
    return keys


def item_subcategory(catalog: Catalog, cat) -> str:
    set_item = catalog.by_slug(set_slug_for(cat.slug) or "")
    return subcategory_of(cat.tags, cat.slug, set_item.tags if set_item else None)


def select_targets(
    catalog: Catalog, db: Db, *, subs: set[str] | None, max_age_s: float, now: datetime | None = None
) -> list[tuple[str, int | None]]:
    """Inventory price keys in the chosen subcategories (None = all) older than max_age_s."""
    now = now or datetime.now(timezone.utc)
    fresh_after = now - timedelta(seconds=max_age_s)
    groups, _, _, _ = _grouped(catalog, db)
    out = []
    for slug, rank in _price_keys(catalog, groups):
        cat = catalog.by_slug(slug)
        if subs is not None and item_subcategory(catalog, cat) not in subs:
            continue
        snap = db.price_latest(slug, rank)
        if max_age_s <= 0 or snap is None or snap.at < fresh_after:
            out.append((slug, rank))
    out.sort(key=lambda k: _PRIORITY[category_of(catalog.by_slug(k[0]).tags)])
    return out


def auto_targets(
    catalog: Catalog,
    db: Db,
    *,
    listed_ids: set[str],
    top_n: int = config.HOT_TOP_N,
    now: datetime | None = None,
) -> list[tuple[str, int | None]]:
    """What the background job refreshes: everything older than an hour, plus items on sale
    and the most valuable ones once they are older than 10 minutes."""
    now = now or datetime.now(timezone.utc)
    groups, _, _, _ = _grouped(catalog, db)
    keys = _price_keys(catalog, groups)
    value = {}
    for slug, rank in keys:
        unit = effective_price(db.price_latest(slug, rank)) or 0
        count = sum(n for (s, _r), n in groups.items() if s == slug)
        value[(slug, rank)] = unit * count
    hot = {k for k in sorted(keys, key=lambda k: -value[k])[:top_n]}
    hot |= {k for k in keys if catalog.by_slug(k[0]).id in listed_ids}
    out = []
    for key in keys:
        snap = db.price_latest(*key)
        limit = config.HOT_PRICE_FRESH_S if key in hot else config.INVENTORY_PRICE_FRESH_S
        if snap is None or (now - snap.at).total_seconds() > limit:
            out.append(key)
    out.sort(key=lambda k: (k not in hot, _PRIORITY[category_of(catalog.by_slug(k[0]).tags)]))
    return out


# Most valuable categories get their prices first.
_PRIORITY = {"mod": 0, "arcane": 1, "prime": 2, "relic": 3, "other": 4}


def price_targets(
    catalog: Catalog, db: Db, *, now: datetime | None = None, max_age_s: float = config.INVENTORY_PRICE_FRESH_S
) -> list[tuple[str, int | None]]:
    """(slug, rank) pairs from the inventory whose cached price is missing or older than max_age_s."""
    now = now or datetime.now(timezone.utc)
    fresh_after = now - timedelta(seconds=max_age_s)
    groups, _, _, _ = _grouped(catalog, db)
    out = []
    for slug, rank in _price_keys(catalog, groups):
        snap = db.price_latest(slug, rank)
        if snap is None or snap.at < fresh_after:
            out.append((slug, rank))
    out.sort(key=lambda k: _PRIORITY[category_of(catalog.by_slug(k[0]).tags)])
    return out


async def fill_prices(
    catalog: Catalog,
    http: HttpClient,
    db: Db,
    *,
    now: datetime | None = None,
    progress=None,
    medians: dict | None = None,
    max_age_s: float = config.INVENTORY_PRICE_FRESH_S,
    targets: list[tuple[str, int | None]] | None = None,
    exclude_user: str | None = None,
) -> int:
    """Fetch prices for inventory items that need them, fastest-useful first:
    riven references, then current listings (1 request per item, valuable categories first),
    then 48 h trade statistics. Returns how many items got a price."""
    if medians is not None:
        if progress:
            progress(0, 0)  # stage 1: riven references
        await fill_riven_values(catalog, http, db, medians)
    if targets is None:
        targets = price_targets(catalog, db, now=now, max_age_s=max_age_s)
    total = len(targets) * 2
    step = 0
    tops: dict[tuple[str, int | None], tuple[int | None, int | None]] = {}
    for slug, rank in targets:
        if progress:
            progress(step, total)
        step += 1
        try:
            sell, buy = await fetch_top(http, slug, rank, default_subtype(catalog, slug), exclude_user)
        except Exception as e:
            log.warning("listings for %s failed: %s", slug, type(e).__name__)
            continue
        tops[(slug, rank)] = (sell, buy)
        db.price_save(PriceSnapshot(slug, rank, sell, buy, None, 0, now or datetime.now(timezone.utc)))
    for slug, rank in targets:
        if progress:
            progress(step, total)
        step += 1
        if (slug, rank) not in tops:
            continue
        sell, buy = tops[(slug, rank)]
        if sell is not None and sell < config.STATS_MIN_PLAT:
            continue  # the price is the cheapest listing anyway; stats would not change it
        try:
            median, volume = await fetch_stats(http, slug, rank, default_subtype(catalog, slug))
        except Exception as e:
            log.warning("stats for %s failed: %s", slug, type(e).__name__)
            continue
        sell, buy = tops[(slug, rank)]
        db.price_save(PriceSnapshot(slug, rank, sell, buy, median, volume, now or datetime.now(timezone.utc)))
    if progress:
        progress(total, total)
    return len(tops)


def riven_key(catalog: Catalog, r) -> tuple[str, tuple[str, ...], bool] | None:
    """What a riven's price depends on: weapon, positive stats, harmless (or no) negative."""
    w = catalog.riven_weapon_by_game_ref(r.weapon_game_ref)
    if not w:
        return None
    positives = tuple(a["slug"] for a in (_riven_attr(catalog, t) for t, _ in r.buffs) if a)
    curse = next((a["slug"] for a in (_riven_attr(catalog, t) for t, _ in r.curses) if a), None)
    return w.slug, positives, is_harmless(curse)


async def fill_riven_values(catalog: Catalog, http: HttpClient, db: Db, cache: dict) -> None:
    """Price reference for each kind of riven in the inventory, from similar lots on the market."""
    _, rivens, _ = db.inventory_load()
    for r in rivens:
        key = riven_key(catalog, r)
        if key is None or key in cache:
            continue
        weapon, positives, harmless = key
        try:
            cache[key] = await riven_value(http, weapon, list(positives), None if harmless else "harmful")
        except Exception as e:
            log.warning("riven value for %s failed: %s", weapon, type(e).__name__)


# Melee rivens use their own tags for stats the market lists under the generic name.
TAG_ALIASES = {"WeaponMeleeDamageMod": "WeaponDamageAmountMod"}


def _riven_attr(catalog: Catalog, tag: str) -> dict | None:
    a = catalog.riven_attr_by_game_ref(tag)
    if a is None:
        alias = TAG_ALIASES.get(tag) or tag.replace("WeaponMeleeFactionDamage", "WeaponFactionDamage")
        a = catalog.riven_attr_by_game_ref(alias)
    return a


def _attr_names(catalog: Catalog, pairs: list[tuple[str, float]]) -> list[tuple[str, float]]:
    out = []
    for tag, value in pairs:
        a = _riven_attr(catalog, tag)
        out.append((a["name_ru"] if a else tag, value))
    return out


async def build_sell_list(
    catalog: Catalog,
    http: HttpClient,
    db: Db,
    *,
    now: datetime | None = None,
    riven_prices: bool = True,
    median_cache: dict | None = None,
    fetch_medians: bool = True,
) -> SellList:
    groups, rivens, inv_at, unmatched_groups = _grouped(catalog, db)
    rows = []
    for (slug, rank), count in groups.items():
        cat = catalog.by_slug(slug)
        prank = price_rank(rank, cat.max_rank)
        snap = db.price_latest(slug, prank)
        unit = effective_price(snap)
        rows.append(
            SellRow(
                slug=slug,
                item_id=cat.id,
                name=cat.name_ru,
                tags=cat.tags,
                count=count,
                rank=rank,
                unit_price=unit,
                total=unit * count if unit is not None else None,
                price_at=snap.at if snap else None,
                thumb=cat.thumb,
                price_rank=prank,
                market_min=snap.sell_min if snap else None,
                category=category_of(cat.tags),
                part=part_of(slug),
                max_rank=cat.max_rank,
                rarity=rarity_of(cat.tags),
                tier=relic_tier(slug),
                sub=(sub := item_subcategory(catalog, cat)),
                sub_label=SUBCAT_LABELS.get(sub, ""),
            )
        )
    rows.sort(key=lambda r: (r.total is None, -(r.total or 0), r.name))

    values: dict = median_cache if median_cache is not None else {}
    out_rivens = []
    for r in rivens:
        w = catalog.riven_weapon_by_game_ref(r.weapon_game_ref)
        key = riven_key(catalog, r)
        value: RivenValue | None = None
        if key and riven_prices:
            if key not in values and fetch_medians:
                weapon, positives, harmless = key
                try:
                    values[key] = await riven_value(http, weapon, list(positives), None if harmless else "harmful")
                except MarketError:
                    values[key] = RivenValue(None, 0, "weapon")
            value = values.get(key)
        out_rivens.append(
            SellRiven(
                weapon_slug=w.slug if w else None,
                weapon_name=w.name_ru if w else r.weapon_game_ref.rsplit("/", 1)[-1],
                buffs=_attr_names(catalog, r.buffs),
                curses=_attr_names(catalog, r.curses),
                rerolls=r.rerolls,
                mastery=r.mastery,
                reference_price=value.price if value else None,
                reference_count=value.count if value else 0,
                reference_basis=value.basis if value else None,
                curse_harmless=key[2] if key else True,
                weapon_thumb=getattr(w, "thumb", None) if w else None,
            )
        )
    out_rivens.sort(key=lambda x: -(x.reference_price or 0))
    return SellList(rows, out_rivens, sum(unmatched_groups.values()), inv_at, unmatched_groups)
