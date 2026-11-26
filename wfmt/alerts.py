"""Alert rules -> notices."""
from __future__ import annotations

from .models import Alert, Notice, PriceSnapshot, RivenLot, RivenWatch

MAX_RIVEN_NOTICES = 3
PRICE_KINDS = ("price_below", "price_above", "median_below", "median_above")


def check_price_alerts(
    alerts: list[Alert],
    snaps: list[PriceSnapshot],
    fired: set[int],
    names: dict[str, str] | None = None,
) -> list[Notice]:
    """Fire when the min sell price crosses the threshold; re-arm once it is back on the other side."""
    names = names or {}
    by_key = {(s.slug, s.rank): s for s in snaps}
    out = []
    for a in alerts:
        if a.kind not in PRICE_KINDS or a.threshold is None:
            continue
        s = by_key.get((a.slug, a.rank))
        if s is None:
            continue
        median = a.kind.startswith("median")
        value = s.median_48h if median else s.sell_min
        if value is None:
            continue
        value = int(round(value))
        below = a.kind.endswith("_below")
        hit = value <= a.threshold if below else value >= a.threshold
        if not hit:
            fired.discard(a.id)
            continue
        if a.id in fired:
            continue
        fired.add(a.id)
        name = names.get(a.slug, a.slug)
        word = "подешевел" if below else "подорожал"
        sign = "≤" if below else "≥"
        what = "Медиана сделок за 48 ч" if median else "Цена продажи"
        out.append(
            Notice(
                title=f"{name} {word}",
                body=f"{what}: {value} пл. ({sign} {a.threshold})",
                url=f"https://warframe.market/items/{a.slug}",
            )
        )
    return out


def riven_notices(watch: RivenWatch, new: list[RivenLot], weapon_name: str) -> list[Notice]:
    lots = sorted(new, key=lambda l: l.price)
    if not lots:
        return []
    shown = lots if len(lots) <= MAX_RIVEN_NOTICES else lots[: MAX_RIVEN_NOTICES - 1]
    out = [
        Notice(
            title=f"Мод разлома: {weapon_name}",
            body=f"{l.name} — {l.price} пл. ({l.seller})",
            url=l.url,
        )
        for l in shown
    ]
    rest = len(lots) - len(shown)
    if rest:
        out.append(Notice(title=f"Мод разлома: {weapon_name}", body=f"И ещё {rest} новых лотов", url=None))
    return out
