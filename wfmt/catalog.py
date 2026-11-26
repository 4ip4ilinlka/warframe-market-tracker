"""Item catalog from warframe.market (names in ru/en, game refs, riven data)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from . import config
from .http import HttpClient
from .models import CatalogItem, RivenWeapon

CACHE_FILE = "catalog.json"
CACHE_VERSION = 3  # bump when the cached fields change


def norm(s: str) -> str:
    return s.lower().replace("ё", "е").strip()


class Catalog:
    def __init__(self, http: HttpClient, cache_dir: Path, *, clock: Callable[[], float] = time.time):
        self.http = http
        self.cache_path = Path(cache_dir) / CACHE_FILE
        self.clock = clock
        self.items: list[CatalogItem] = []
        self._by_slug: dict[str, CatalogItem] = {}
        self._by_id: dict[str, CatalogItem] = {}
        self._by_ref: dict[str, CatalogItem] = {}
        self._weapons: list[RivenWeapon] = []
        self._weapon_by_ref: dict[str, RivenWeapon] = {}
        self._weapon_by_slug: dict[str, RivenWeapon] = {}
        self._attrs: list[dict] = []
        self._attr_by_ref: dict[str, dict] = {}
        self._attr_by_slug: dict[str, dict] = {}
        self._search_keys: list[tuple[str, str]] = []
        self.loaded_at: float | None = None

    async def _get(self, path: str, lang: str) -> list[dict]:
        data = await self.http.get_json(
            f"{config.MARKET_API}{path}", headers={"Language": lang, "Platform": "pc"}
        )
        return data.get("data", [])

    async def _fetch(self) -> dict:
        ru = await self._get("/v2/items", "ru")
        en = await self._get("/v2/items", "en")
        weapons = await self._get("/v2/riven/weapons", "ru")
        attrs = await self._get("/v2/riven/attributes", "ru")
        en_names = {i["id"]: i.get("i18n", {}).get("en", {}).get("name", i["slug"]) for i in en}
        en_thumbs = {i["id"]: i.get("i18n", {}).get("en", {}).get("thumb") for i in en}
        items = []
        for i in ru:
            i18n = i.get("i18n", {})
            ru_n = i18n.get("ru", {}) or i18n.get("en", {})
            items.append(
                {
                    "id": i["id"],
                    "slug": i["slug"],
                    "game_ref": i.get("gameRef"),
                    "name_ru": ru_n.get("name") or en_names.get(i["id"], i["slug"]),
                    "name_en": en_names.get(i["id"], i["slug"]),
                    "tags": i.get("tags", []),
                    "max_rank": i.get("maxRank"),
                    "thumb": ru_n.get("thumb") or en_thumbs.get(i["id"]),
                    "subtypes": i.get("subtypes") or [],
                }
            )
        return {
            "version": CACHE_VERSION,
            "fetched_at": self.clock(),
            "items": items,
            "weapons": [
                {
                    "slug": w["slug"],
                    "game_ref": w.get("gameRef"),
                    "name_ru": (w.get("i18n", {}).get("ru") or w.get("i18n", {}).get("en") or {}).get(
                        "name", w["slug"]
                    ),
                    "group": w.get("group"),
                    "disposition": w.get("disposition"),
                    "thumb": (w.get("i18n", {}).get("ru") or w.get("i18n", {}).get("en") or {}).get("thumb"),
                }
                for w in weapons
            ],
            "attrs": [
                {
                    "slug": a["slug"],
                    "game_ref": a.get("gameRef"),
                    "name_ru": (a.get("i18n", {}).get("ru") or a.get("i18n", {}).get("en") or {}).get(
                        "name", a["slug"]
                    ),
                    "positive_only": a.get("positiveOnly", False),
                    "negative_only": a.get("negativeOnly", False),
                }
                for a in attrs
            ],
        }

    def _index(self, data: dict) -> None:
        self.items = [CatalogItem(**i) for i in data["items"]]
        self._by_slug = {i.slug: i for i in self.items}
        self._by_id = {i.id: i for i in self.items}
        self._by_ref = {i.game_ref: i for i in self.items if i.game_ref}
        self._weapons = [RivenWeapon(**w) for w in data["weapons"]]
        self._weapon_by_ref = {w.game_ref: w for w in self._weapons if w.game_ref}
        self._weapon_by_slug = {w.slug: w for w in self._weapons}
        self._attrs = data["attrs"]
        self._attr_by_ref = {a["game_ref"]: a for a in self._attrs if a.get("game_ref")}
        self._attr_by_slug = {a["slug"]: a for a in self._attrs}
        self._search_keys = [(norm(i.name_ru), norm(i.name_en)) for i in self.items]
        self.loaded_at = data["fetched_at"]

    def needs_refresh(self) -> bool:
        return self.loaded_at is None or self.clock() - self.loaded_at >= config.CATALOG_TTL_S

    async def load(self, force: bool = False) -> None:
        cached = None
        if self.cache_path.exists():
            try:
                cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
                current = cached.get("version") == CACHE_VERSION
                if not force and current and self.clock() - cached["fetched_at"] < config.CATALOG_TTL_S:
                    self._index(cached)
                    return
            except (ValueError, KeyError, TypeError):
                cached = None
        try:
            data = await self._fetch()
        except Exception:
            # Market unreachable: keep working with the expired cache, retry later.
            if cached is not None and not self.items:
                self._index(cached)
            raise
        self._index(data)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.cache_path)

    def search(self, q: str, limit: int = 20) -> list[CatalogItem]:
        tokens = norm(q).split()
        if not tokens:
            return []
        qn = " ".join(tokens)
        hits = []
        for item, (ru, en) in zip(self.items, self._search_keys):
            for name in (ru, en):
                if all(t in name for t in tokens):
                    hits.append((0 if name.startswith(qn) else 1, len(name), item))
                    break
        hits.sort(key=lambda h: (h[0], h[1]))
        return [h[2] for h in hits[:limit]]

    def by_slug(self, slug: str) -> CatalogItem | None:
        return self._by_slug.get(slug)

    def by_id(self, item_id: str) -> CatalogItem | None:
        return self._by_id.get(item_id)

    def by_game_ref(self, ref: str) -> CatalogItem | None:
        return self._by_ref.get(ref)

    def riven_weapons(self) -> list[RivenWeapon]:
        return list(self._weapons)

    def riven_weapon(self, slug: str) -> RivenWeapon | None:
        return self._weapon_by_slug.get(slug)

    def riven_weapon_by_game_ref(self, ref: str) -> RivenWeapon | None:
        return self._weapon_by_ref.get(ref)

    def riven_attributes(self) -> list[dict]:
        return list(self._attrs)

    def riven_attr(self, slug: str) -> dict | None:
        return self._attr_by_slug.get(slug)

    def riven_attr_by_game_ref(self, ref: str) -> dict | None:
        return self._attr_by_ref.get(ref)
