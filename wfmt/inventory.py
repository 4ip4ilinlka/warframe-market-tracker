"""Load the player's inventory from the game servers (on user request only)."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

from . import config, game_memory
from .db import Db
from .http import HttpClient, MarketError
from .models import InvItem, InvRiven

log = logging.getLogger(__name__)

INVENTORY_URLS = (
    "https://api.warframe.com/api/inventory.php",
    "https://mobile.warframe.com/api/inventory.php",
)
# Generic UA for game servers: do not advertise a third-party tool.
GAME_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
ENABLED_KEY = "inventory_enabled"
COUNT_LISTS = ("MiscItems", "Recipes", "RawUpgrades", "FusionTreasures", "Consumables", "LevelKeys")
FP_MAX = 0x3FFFFFFF


class InventoryDisabled(Exception):
    pass


class GameRequestFailed(Exception):
    """Game servers refused or could not serve the inventory request."""

    def __init__(self, status: int | None):
        super().__init__(f"game server answered {status}")
        self.status = status


class Cooldown(Exception):
    def __init__(self, retry_in: int):
        super().__init__(f"retry in {retry_in}s")
        self.retry_in = retry_in


def _fingerprint(entry: dict) -> dict:
    fp = entry.get("UpgradeFingerprint")
    if isinstance(fp, str):
        try:
            return json.loads(fp)
        except ValueError:
            return {}
    return fp if isinstance(fp, dict) else {}


def parse_inventory(data: dict) -> tuple[list[InvItem], list[InvRiven]]:
    counts: dict[tuple[str, int | None], int] = defaultdict(int)
    for key in COUNT_LISTS:
        rank = 0 if key == "RawUpgrades" else None
        for e in data.get(key) or []:
            ref = e.get("ItemType")
            n = int(e.get("ItemCount") or 0)
            if ref and n > 0:
                counts[(ref, rank)] += n
    rivens: list[InvRiven] = []
    for e in data.get("Upgrades") or []:
        ref = e.get("ItemType")
        if not ref:
            continue
        fp = _fingerprint(e)
        if "/Randomized/" in ref and fp.get("compat"):
            rivens.append(
                InvRiven(
                    weapon_game_ref=fp["compat"],
                    buffs=[(b.get("Tag", ""), (b.get("Value") or 0) / FP_MAX) for b in fp.get("buffs", [])],
                    curses=[(c.get("Tag", ""), (c.get("Value") or 0) / FP_MAX) for c in fp.get("curses", [])],
                    rerolls=fp.get("rerolls"),
                    mastery=fp.get("lvlReq"),
                )
            )
            continue
        counts[(ref, int(fp.get("lvl") or 0))] += 1
    items = [InvItem(ref, n, rank) for (ref, rank), n in counts.items()]
    return items, rivens


class InventoryLoader:
    def __init__(
        self,
        http: HttpClient,
        db: Db,
        *,
        clock: Callable[[], float] = time.monotonic,
        find_pid: Callable[[], int | None] = game_memory.find_pid,
        find_credentials: Callable[[int], tuple[str, str]] = game_memory.find_credentials,
    ):
        self.http = http
        self.db = db
        self.clock = clock
        self.find_pid = find_pid
        self.find_credentials = find_credentials
        self._last: float | None = None
        self._lock = asyncio.Lock()

    def enabled(self) -> bool:
        return self.db.setting_get(ENABLED_KEY, "0") == "1"

    def set_enabled(self, on: bool) -> None:
        self.db.setting_set(ENABLED_KEY, "1" if on else "0")

    def retry_in(self) -> int:
        if self._last is None:
            return 0
        return max(0, math.ceil(self._last + config.INVENTORY_COOLDOWN_S - self.clock()))

    async def fetch(self) -> tuple[list[InvItem], list[InvRiven]]:
        if not self.enabled():
            raise InventoryDisabled()
        async with self._lock:
            wait = self.retry_in()
            if wait > 0:
                raise Cooldown(wait)
            pid = self.find_pid()
            if pid is None:
                raise game_memory.GameNotRunning()
            found = await asyncio.to_thread(self.find_credentials, pid)
            candidates = [found] if isinstance(found, tuple) else list(found)
            self._last = self.clock()
            data = None
            status = None
            for account_id, nonce in candidates[: game_memory.MAX_CANDIDATES]:
                rejected = False
                for url in INVENTORY_URLS:
                    try:
                        data = await self.http.get_json(
                            url, headers=GAME_HEADERS, params={"accountId": account_id, "nonce": nonce}
                        )
                        break
                    except MarketError as e:
                        status = e.status
                        log.info("inventory host failed (%s)", e.status)
                        # A 4xx means the session was rejected: do not re-send it elsewhere.
                        if e.status is not None and e.status < 500:
                            rejected = True
                            break
                if data is not None or not rejected:
                    break
            del candidates, found
            if data is None:
                raise GameRequestFailed(status)
            items, rivens = parse_inventory(data)
            self.db.inventory_save(items, rivens, datetime.now(timezone.utc))
            log.info("inventory loaded: %d items, %d rivens", len(items), len(rivens))
            return items, rivens
