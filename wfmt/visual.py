"""Visual hints for the UI: which part of a warframe/weapon an item is, its category."""
from __future__ import annotations

PART_LABELS = {
    "set": "Комплект",
    "blueprint": "Чертёж",
    "chassis": "Каркас",
    "neuroptics": "Нейрооптика",
    "systems": "Системы",
    "harness": "Упряжь",
    "wings": "Крылья",
    "carapace": "Панцирь",
    "cerebrum": "Мозг",
    "barrel": "Ствол",
    "receiver": "Приёмник",
    "stock": "Приклад",
    "blade": "Клинок",
    "handle": "Рукоять",
    "hilt": "Эфес",
    "grip": "Хват",
    "string": "Тетива",
    "limbs": "Плечи лука",
    "upper_limb": "Верхнее плечо",
    "lower_limb": "Нижнее плечо",
    "link": "Связка",
    "chain": "Цепь",
    "head": "Навершие",
    "guard": "Гарда",
    "gauntlet": "Перчатка",
    "pouch": "Подсумок",
    "ornament": "Орнамент",
    "disc": "Диск",
    "stars": "Звёзды",
    "boot": "Ботинок",
    "motor": "Мотор",
}

# Checked in order: specific parts before the generic "blueprint".
_SUFFIXES = sorted((k for k in PART_LABELS if k not in ("set", "blueprint")), key=len, reverse=True)


def part_of(slug: str) -> str | None:
    if slug.endswith("_set"):
        return "set"
    base = slug[: -len("_blueprint")] if slug.endswith("_blueprint") else slug
    for key in _SUFFIXES:
        if base.endswith("_" + key):
            return key
    if slug.endswith("_blueprint"):
        return "blueprint"
    return None


RARITIES = ("common", "uncommon", "rare", "legendary")
RELIC_TIERS = ("lith", "meso", "neo", "axi", "requiem")


def rarity_of(tags: list[str]) -> str | None:
    return next((t for t in RARITIES if t in tags), None)


def relic_tier(slug: str) -> str | None:
    if not slug.endswith("_relic"):
        return None
    head = slug.split("_", 1)[0]
    return head if head in RELIC_TIERS else None


def category_of(tags: list[str]) -> str:
    if "mod" in tags:
        return "mod"
    if "arcane_enhancement" in tags:
        return "arcane"
    if "relic" in tags:
        return "relic"
    if "prime" in tags:
        return "prime"
    return "other"


_GROUPS = (
    ("/Lotus/Types/Items/", "Ресурсы"),
    ("/Lotus/Types/Gameplay/", "Ресурсы"),
    ("/Lotus/Types/Recipes/", "Чертежи"),
    ("/Lotus/Upgrades/Mods/", "Моды"),
    ("/Lotus/Types/Restoratives/", "Расходники"),
    ("/Lotus/Weapons/", "Оружие"),
    ("/Lotus/Types/Game/", "Снаряжение"),
)


def unmatched_group(game_ref: str) -> str:
    for prefix, label in _GROUPS:
        if game_ref.startswith(prefix):
            return label
    return "Прочее"


SUBCAT_LABELS = {
    "prime:warframe": "Варфреймы", "prime:primary": "Основное", "prime:secondary": "Вторичное",
    "prime:melee": "Ближний бой", "prime:companion": "Компаньоны", "prime:archwing": "Арчвинг", "prime:other": "Другое",
    "mod:warframe": "Варфрейм", "mod:aura": "Ауры", "mod:primary": "Основное", "mod:secondary": "Вторичное",
    "mod:melee": "Ближний бой", "mod:stance": "Стойки", "mod:companion": "Компаньоны", "mod:parazon": "Паразон",
    "mod:railjack": "Рейлджек", "mod:necramech": "Некрамех", "mod:archwing": "Арчвинг", "mod:other": "Другое",
    "arcane:legendary": "Легендарные", "arcane:rare": "Редкие", "arcane:uncommon": "Необычные",
    "arcane:common": "Обычные", "arcane:other": "Другие",
    "relic:lith": "Лит", "relic:meso": "Мезо", "relic:neo": "Нео", "relic:axi": "Акси", "relic:requiem": "Реквием",
    "relic:other": "Другие",
    "other:scene": "Сцены", "other:fish": "Рыба", "other:lens": "Линзы", "other:ayatan": "Скульптуры аятан",
    "other:parts": "Детали оружия", "other:key": "Ключи", "other:imprint": "Отпечатки", "other:other": "Остальное",
}
_COMPANION = {"sentinel", "companion", "kubrow", "kavat", "beast", "robotic", "moa", "hound"}
_ARCHWING = {"archwing", "archgun", "archmelee"}


def _weapon_class(tags) -> str | None:
    t = set(tags)
    if t & _ARCHWING:
        return "archwing"
    if t & _COMPANION:
        return "companion"
    for key in ("warframe", "primary", "secondary", "melee"):
        if key in t:
            return key
    if t & {"rifle", "shotgun", "bow", "sniper"}:
        return "primary"
    if "pistol" in t:
        return "secondary"
    return None


def subcategory_of(tags: list[str], slug: str, set_tags: list[str] | None = None) -> str:
    """'category:subcategory' key used by the filters and the refresh picker."""
    t = set(tags)
    cat = category_of(tags)
    if cat == "prime":
        cls = _weapon_class(tags) or (_weapon_class(set_tags) if set_tags else None)
        return f"prime:{cls or 'other'}"
    if cat == "mod":
        for key in ("aura", "stance", "parazon", "railjack", "necramech"):
            if key in t:
                return f"mod:{key}"
        cls = _weapon_class(tags)
        return f"mod:{cls or 'other'}"
    if cat == "arcane":
        return f"arcane:{rarity_of(tags) or 'other'}"
    if cat == "relic":
        return f"relic:{relic_tier(slug) or 'other'}"
    for key, tag in (("scene", "scene"), ("fish", "fish"), ("lens", "lens"), ("ayatan", "ayatan_sculpture"),
                     ("key", "key"), ("imprint", "imprint")):
        if tag in t:
            return f"other:{key}"
    if "component" in t and "weapon" in t:
        return "other:parts"
    return "other:other"


def set_slug_for(slug: str) -> str | None:
    """'soma_prime_barrel' -> 'soma_prime_set' (the set a part belongs to)."""
    part = part_of(slug)
    if part in (None, "set"):
        return None
    base = slug[: -len("_blueprint")] if slug.endswith("_blueprint") else slug
    if part != "blueprint":
        base = base[: -len("_" + part)]
    return base + "_set"
