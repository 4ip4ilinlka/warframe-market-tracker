import json
import logging
from pathlib import Path

import httpx
import pytest
import respx

from wfmt import game_memory
from wfmt.db import Db
from wfmt.game_memory import CredentialsNotFound, GameNotRunning, scan_buffer
from wfmt.http import HttpClient
from wfmt.inventory import Cooldown, InventoryDisabled, InventoryLoader, parse_inventory

FX = Path(__file__).parent / "fixtures"
ACC = "0123456789abcdef01234567"
INV_API = "https://api.warframe.com/api/inventory.php"
INV_MOBILE = "https://mobile.warframe.com/api/inventory.php"


def sample():
    return json.loads((FX / "inventory_sample.json").read_text(encoding="utf-8"))


# --- memory scan (pure) ---

def test_scan_buffer_finds_credentials():
    buf = b"\x00junk?accountId=" + ACC.encode() + b"&nonce=987654321&ct=MSI\x00"
    assert scan_buffer(buf) == (ACC, "987654321")


def test_scan_buffer_last_match_wins():
    other = "ffffffffffffffffffffffff"
    buf = f"accountId={other}&nonce=1 .... accountId={ACC}&nonce=2".encode()
    assert scan_buffer(buf) == (ACC, "2")


def test_scan_buffer_none():
    assert scan_buffer(b"accountId=xyz&nonce=") is None


def test_open_process_access_mask():
    # PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION, nothing else
    assert game_memory.ACCESS == 0x0010 | 0x1000


# --- loader ---

class Clock:
    def __init__(self):
        self.t = 5000.0

    def __call__(self):
        return self.t


@pytest.fixture
async def http():
    c = HttpClient(max_rps=1000)
    yield c
    await c.aclose()


@pytest.fixture
def db(tmp_path):
    d = Db(tmp_path / "t.sqlite3")
    return d


def make_loader(http, db, clock, pid=1234, creds=(ACC, "8675309123")):
    def find_pid():
        return pid

    def find_credentials(p):
        if creds is None:
            raise CredentialsNotFound()
        return creds

    return InventoryLoader(http, db, clock=clock, find_pid=find_pid, find_credentials=find_credentials)


async def test_disabled_by_default(http, db):
    with pytest.raises(InventoryDisabled):
        await make_loader(http, db, Clock()).fetch()


async def test_no_process_returns_not_running(http, db):
    db.setting_set("inventory_enabled", "1")
    with pytest.raises(GameNotRunning):
        await make_loader(http, db, Clock(), pid=None).fetch()


async def test_no_credentials_found(http, db):
    db.setting_set("inventory_enabled", "1")
    with pytest.raises(CredentialsNotFound):
        await make_loader(http, db, Clock(), creds=None).fetch()


@respx.mock
async def test_fetch_saves_inventory_and_never_logs_credentials(http, db, caplog):
    caplog.set_level(logging.DEBUG)
    db.setting_set("inventory_enabled", "1")
    route = respx.get(INV_API).mock(return_value=httpx.Response(200, json=sample()))
    items, rivens = await make_loader(http, db, Clock()).fetch()
    assert route.calls.last.request.url.params["accountId"] == ACC
    assert "WFMarketTracker" not in route.calls.last.request.headers["User-Agent"]
    assert len(items) > 0 and len(rivens) == 1
    saved_items, saved_rivens, at = db.inventory_load()
    assert len(saved_items) == len(items) and at is not None
    assert ACC not in caplog.text and "8675309123" not in caplog.text
    assert ACC.encode() not in Path(db.path).read_bytes()


@respx.mock
async def test_falls_back_to_mobile_host(http, db):
    db.setting_set("inventory_enabled", "1")
    respx.get(INV_API).mock(return_value=httpx.Response(503))
    respx.get(INV_MOBILE).mock(return_value=httpx.Response(200, json=sample()))
    items, _ = await make_loader(http, db, Clock()).fetch()
    assert items


@respx.mock
async def test_cooldown_enforced(http, db):
    db.setting_set("inventory_enabled", "1")
    respx.get(INV_API).mock(return_value=httpx.Response(200, json=sample()))
    clock = Clock()
    loader = make_loader(http, db, clock)
    await loader.fetch()
    clock.t += 30
    with pytest.raises(Cooldown) as e:
        await loader.fetch()
    assert e.value.retry_in == 90
    clock.t += 90
    await loader.fetch()


# --- parsing ---

def test_parse_inventory_counts():
    items, _ = parse_inventory(sample())
    got = {(i.game_ref, i.rank): i.count for i in items}
    bull = "/Lotus/Upgrades/Mods/Pistol/DualStat/CorruptedCritChanceFireRatePistol"
    assert got[(bull, 0)] == 4
    assert got[(bull, 5)] == 2
    assert got[(bull, 2)] == 1
    assert got[("/Lotus/Types/Recipes/WarframeRecipes/AshPrimeSystemsBlueprint", None)] == 3
    assert got[("/Lotus/Types/Recipes/Weapons/WeaponParts/SomaPrimeReceiver", None)] == 2
    assert ("/Lotus/Types/Items/FusionTreasures/OroFusexOrnamentB", None) in got


def test_parse_riven_fingerprint():
    _, rivens = parse_inventory(sample())
    (r,) = rivens
    assert r.weapon_game_ref.endswith("GrnTorpedoPistol")
    assert [t for t, _ in r.buffs] == ["WeaponCritChanceMod", "WeaponCritDamageMod"]
    assert r.buffs[1][1] == pytest.approx(1.0)
    assert r.curses[0][0] == "WeaponZoomFovMod"
    assert r.rerolls == 4
    assert r.mastery == 11


@respx.mock
async def test_game_rejects_session_is_not_market_error(http, db):
    from wfmt.inventory import GameRequestFailed

    db.setting_set("inventory_enabled", "1")
    respx.get(INV_API).mock(return_value=httpx.Response(403))
    mobile = respx.get(INV_MOBILE).mock(return_value=httpx.Response(200, json=sample()))
    with pytest.raises(GameRequestFailed):
        await make_loader(http, db, Clock()).fetch()
    assert mobile.call_count == 0  # session is not re-sent to a second host on 4xx


def test_scan_all_unique_newest_last():
    from wfmt.game_memory import scan_all

    other = "ffffffffffffffffffffffff"
    buf = f"accountId={ACC}&nonce=1 accountId={other}&nonce=2 accountId={ACC}&nonce=1".encode()
    assert scan_all(buf) == [(other, "2"), (ACC, "1")]


@respx.mock
async def test_second_session_candidate_tried_on_rejection(http, db):
    db.setting_set("inventory_enabled", "1")
    seen = []

    def route(request):
        seen.append(request.url.params["nonce"])
        return httpx.Response(403) if request.url.params["nonce"] == "111" else httpx.Response(200, json=sample())

    respx.get(INV_API).mock(side_effect=route)
    loader = InventoryLoader(http, db, clock=Clock(), find_pid=lambda: 1,
                             find_credentials=lambda p: [(ACC, "111"), (ACC, "222"), (ACC, "333")])
    items, _ = await loader.fetch()
    assert items and seen == ["111", "222"]


async def test_access_denied_is_reported(http, db):
    from wfmt.game_memory import GameAccessDenied

    db.setting_set("inventory_enabled", "1")

    def deny(p):
        raise GameAccessDenied()

    with pytest.raises(GameAccessDenied):
        await InventoryLoader(http, db, clock=Clock(), find_pid=lambda: 1, find_credentials=deny).fetch()
