"""Prime status: in the active drop pool, vaulted, or available from Varzia (Prime Resurgence).

Sources (both official Digital Extremes data):
* World state  https://api.warframe.com/cdn/worldState.php  -> PrimeVaultTraders: Varzia's current
  rotation (Manifest), permanent offers (EvergreenManifest) and the schedule of rotations.
* Drop tables  https://www.warframe.com/droptables  (redirects to DE's CDN) -> what each relic contains.
Combined with the market's "vaulted" flag on relics this tells which primes currently drop.
"""
from __future__ import annotations

import html as htmlmod
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from .catalog import Catalog
from .http import HttpClient, MarketError, check_host
from .visual import set_slug_for

log = logging.getLogger(__name__)

WORLDSTATE_URL = "https://api.warframe.com/cdn/worldState.php"
DROPTABLES_URL = "https://www.warframe.com/droptables"
CACHE_FILE = "primes.json"
REFRESH_S = 6 * 3600
DROPTABLES_TTL_S = 24 * 3600
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

_HEAD = re.compile(r'<th colspan="2">([^<]+?) \((Intact|Exceptional|Flawless|Radiant)\)</th>')
_CELL = re.compile(r"<tr><td>([^<]+)</td><td>[^<]*</td></tr>")


def parse_relic_rewards(page: str) -> dict[str, list[str]]:
    """{relic slug: [reward names]} from the 'Relics' section (intact refinement only)."""
    a = page.find('id="relicRewards"')
    if a < 0:
        return {}
    b = page.find("<h3", a + 10)
    section = page[a: b if b > 0 else len(page)]
    out: dict[str, list[str]] = {}
    heads = list(_HEAD.finditer(section))
    for i, m in enumerate(heads):
        if m.group(2) != "Intact":
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(section)
        name = htmlmod.unescape(m.group(1)).strip().lower().replace(" ", "_")
        out[name] = [htmlmod.unescape(x).strip() for x in _CELL.findall(section[m.end():end])]
    return out


def _date(v) -> str | None:
    try:
        ms = int(v["$date"]["$numberLong"])
    except (KeyError, TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def _to_ref(store_item: str) -> str:
    return store_item.replace("/StoreItems/", "/", 1)


def _names_from_pack(featured: str) -> list[str]:
    """'.../MPVLokiNovaPrimeDualPack' -> ['Loki', 'Nova']"""
    m = re.search(r"MPV([A-Za-z]+?)Prime(?:Dual|Single)Pack", featured or "")
    return re.findall(r"[A-Z][a-z]+", m.group(1)) if m else []


def parse_varzia(ws: dict, catalog: Catalog) -> dict:
    traders = ws.get("PrimeVaultTraders") or []
    if not traders:
        return {"sets": [], "relics": [], "evergreen_sets": [], "expiry": None, "next": None}
    t = traders[0]

    def resolve(entries):
        sets, relics = [], []
        for e in entries or []:
            ref = _to_ref(e.get("ItemType", ""))
            item = catalog.by_game_ref(ref)
            if item is None and "/Projections/" in ref:
                for suffix in ("Bronze", "Silver", "Gold", "Platinum"):
                    if ref.endswith(suffix):
                        item = catalog.by_game_ref(ref[: -len(suffix)]) or catalog.by_game_ref(ref)
                        break
            if item is None and "/Projections/" in ref:
                item = next((i for i in catalog.items if i.game_ref and ref.startswith(i.game_ref)), None)
            if item is None:
                continue
            if "relic" in item.tags:
                relics.append(item.slug)
            elif "set" in item.tags:
                sets.append(item.slug)
        return sorted(set(sets)), sorted(set(relics))

    sets, relics = resolve(t.get("Manifest"))
    evergreen_sets, _ = resolve(t.get("EvergreenManifest"))
    expiry = _date(t.get("Expiry"))
    nxt = None
    for s in sorted(t.get("ScheduleInfo") or [], key=lambda s: _date(s.get("Expiry")) or ""):
        exp = _date(s.get("Expiry"))
        if expiry and exp and exp > expiry:
            nxt = {"names": _names_from_pack(s.get("FeaturedItem", "")), "from": expiry}
            break
    return {"sets": sets, "relics": relics, "evergreen_sets": evergreen_sets, "expiry": expiry, "next": nxt}


def compute_primes(catalog: Catalog, rewards: dict[str, list[str]], varzia: dict) -> dict:
    by_en = {i.name_en.lower(): i for i in catalog.items}
    set_relics: dict[str, set[str]] = {}
    for relic_slug, names in rewards.items():
        for n in names:
            part = by_en.get(n.lower())
            if part is None:
                continue
            s = set_slug_for(part.slug)
            if s:
                set_relics.setdefault(s, set()).add(relic_slug)
    varzia_sets = set(varzia.get("sets") or [])
    evergreen = set(varzia.get("evergreen_sets") or [])
    primes = []
    for item in catalog.items:
        if "set" not in item.tags or "prime" not in item.tags:
            continue
        relics = sorted(set_relics.get(item.slug, set()))
        active = [r for r in relics if (catalog.by_slug(r) is not None and not catalog.by_slug(r).vaulted)]
        status = "varzia" if item.slug in varzia_sets else ("active" if active else "vaulted")
        primes.append({
            "slug": item.slug, "name": item.name_ru, "name_en": item.name_en, "thumb": item.thumb,
            "kind": "warframe" if "warframe" in item.tags else ("weapon" if "weapon" in item.tags else "other"),
            "status": status, "relics": active or relics, "evergreen": item.slug in evergreen,
        })
    primes.sort(key=lambda p: ({"varzia": 0, "active": 1, "vaulted": 2}[p["status"]], p["name"]))
    return {"primes": primes, "varzia": varzia}


async def fetch_droptables(http: HttpClient) -> str:
    """Drop tables page; DE redirects to its CDN, which must also be an allowed host."""
    url = DROPTABLES_URL
    for _ in range(3):
        resp = await http.request("GET", url, headers=BROWSER_HEADERS)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, resp.headers.get("Location", ""))
            check_host(url)
            continue
        return resp.text
    raise MarketError("too many redirects")


async def fetch_worldstate(http: HttpClient) -> dict:
    resp = await http.request("GET", WORLDSTATE_URL, headers=BROWSER_HEADERS)
    return json.loads(resp.text)


class PrimeTracker:
    """Prime statuses with a disk cache (shown until the refresh at program start finishes)."""

    def __init__(self, http: HttpClient, catalog: Catalog, cache_dir: Path, *, clock=time.time):
        self.http = http
        self.catalog = catalog
        self.cache_path = Path(cache_dir) / CACHE_FILE
        self.clock = clock
        self.data: dict | None = None
        self.rewards: dict[str, list[str]] = {}
        self.rewards_at = 0.0
        self.updated_at = 0.0
        self.error: str | None = None
        self._load_cache()

    def _load_cache(self) -> None:
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            self.rewards, self.rewards_at = raw.get("rewards", {}), raw.get("rewards_at", 0.0)
            self.data, self.updated_at = raw.get("data"), raw.get("updated_at", 0.0)
        except (OSError, ValueError):
            pass

    def _save_cache(self) -> None:
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"rewards": self.rewards, "rewards_at": self.rewards_at,
                                   "data": self.data, "updated_at": self.updated_at}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.cache_path)

    def due(self) -> bool:
        if self.data is None or self.clock() - self.updated_at > REFRESH_S:
            return True
        expiry = (self.data.get("varzia") or {}).get("expiry")
        return bool(expiry and datetime.fromisoformat(expiry).timestamp() < self.clock())

    async def refresh(self) -> None:
        try:
            if not self.rewards or self.clock() - self.rewards_at > DROPTABLES_TTL_S:
                self.rewards = parse_relic_rewards(await fetch_droptables(self.http))
                self.rewards_at = self.clock()
            varzia = parse_varzia(await fetch_worldstate(self.http), self.catalog)
            self.data = compute_primes(self.catalog, self.rewards, varzia)
            self.updated_at = self.clock()
            self.error = None
            self._save_cache()
        except Exception as e:
            self.error = type(e).__name__
            log.warning("prime status refresh failed: %s", self.error)


def localize_next(varzia: dict, catalog: Catalog) -> dict:
    """Add Russian names for the next Varzia rotation ('Sevagoth' -> 'Севагот')."""
    nxt = (varzia or {}).get("next")
    if not nxt:
        return varzia
    names_ru = []
    for n in nxt.get("names", []):
        item = catalog.by_slug(f"{n.lower()}_prime_set")
        names_ru.append(re.sub(r"\s*(Прайм|Prime).*$", "", item.name_ru).strip() if item else n)
    return {**varzia, "next": {**nxt, "names_ru": names_ru}}


PRIME_PRICE_FRESH_S = 6 * 3600


async def fill_prime_prices(http: HttpClient, db, data: dict, *, now: datetime | None = None) -> int:
    """Set prices for every prime warframe and everything Varzia sells now (one request each)."""
    from .models import PriceSnapshot
    from .prices import fetch_top

    now = now or datetime.now(timezone.utc)
    varzia = set((data.get("varzia") or {}).get("sets") or [])
    done = 0
    for p in data.get("primes", []):
        if p["kind"] != "warframe" and p["slug"] not in varzia:
            continue
        snap = db.price_latest(p["slug"], None)
        if snap is not None and (now - snap.at).total_seconds() < PRIME_PRICE_FRESH_S:
            continue
        try:
            sell, buy = await fetch_top(http, p["slug"], None)
        except Exception as e:
            log.info("prime set price %s failed: %s", p["slug"], type(e).__name__)
            continue
        db.price_save(PriceSnapshot(p["slug"], None, sell, buy, None, 0, now))
        done += 1
    return done
