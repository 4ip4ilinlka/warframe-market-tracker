"""Plain data types shared across modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class WatchEntry:
    slug: str
    rank: int | None


@dataclass
class PriceSnapshot:
    slug: str
    rank: int | None
    sell_min: int | None
    buy_max: int | None
    median_48h: float | None
    volume_48h: int
    at: datetime


@dataclass
class CatalogItem:
    id: str
    slug: str
    game_ref: str | None
    name_ru: str
    name_en: str
    tags: list[str]
    max_rank: int | None
    thumb: str | None
    subtypes: list[str] = field(default_factory=list)
    ducats: int | None = None
    vaulted: bool = False


@dataclass
class RivenWeapon:
    slug: str
    game_ref: str | None
    name_ru: str
    group: str | None
    disposition: float | None
    thumb: str | None = None


@dataclass
class RivenAttr:
    url_name: str
    value: float
    positive: bool


@dataclass
class RivenWatch:
    id: int | None
    weapon_slug: str
    positive: list[str] = field(default_factory=list)
    negative: str | None = None
    max_price: int | None = None


@dataclass
class RivenLot:
    id: str
    weapon_slug: str
    name: str
    price: int
    attributes: list[RivenAttr]
    mastery: int | None
    rerolls: int | None
    polarity: str | None
    seller: str
    seller_status: str
    url: str


@dataclass
class InvItem:
    game_ref: str
    count: int
    rank: int | None


@dataclass
class InvRiven:
    weapon_game_ref: str
    buffs: list[tuple[str, float]]
    curses: list[tuple[str, float]]
    rerolls: int | None
    mastery: int | None


@dataclass
class Alert:
    id: int | None
    kind: Literal["price_below", "price_above", "median_below", "median_above", "riven"]
    slug: str | None
    rank: int | None
    threshold: int | None
    riven_watch_id: int | None


@dataclass
class MyOrder:
    id: str
    item_id: str
    slug: str | None
    kind: Literal["sell", "buy"]
    platinum: int
    quantity: int
    rank: int | None
    visible: bool


@dataclass
class Notice:
    title: str
    body: str
    url: str | None = None


@dataclass
class EphWatch:
    id: int | None
    kind: str
    element: str
    weapon: str | None
    max_price: int | None
    notify: bool


@dataclass
class EphLot:
    id: str
    kind: str
    element: str
    weapon: str
    damage: int | None
    price: int
    seller: str
    seller_status: str
    created: str | None
    seen_at: float

    @property
    def url(self) -> str:
        return f"{"https://warframe.market"}/auction/{self.id}"
