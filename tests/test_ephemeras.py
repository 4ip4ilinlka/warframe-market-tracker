import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from wfmt.db import Db
from wfmt.ephemeras import (
    RECENT_URL,
    SEARCH_URL,
    EphemeraTracker,
    EphWatch,
    lots_from_auctions,
    parse_ephemeras,
    watch_matches,
)
from wfmt.http import HttpClient

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def eph_data(kind, rows):
    return {"data": [
        {"slug": slug, "element": el, "i18n": {
            "en": {"name": en, "thumb": f"{kind}_ephemeras/images/thumbs/{slug}.png"},
            "ru": {"name": ru}}}
        for slug, el, en, ru in rows]}


LICH = eph_data("lich", [("vengeful_charge", "electricity", "Vengeful Charge Ephemera", "Эфемера: Заряд Мщения"),
                         ("vengeful_flame", "heat", "Vengeful Flame Ephemera", "Эфемера: Пламя Мщения")])
SISTER = eph_data("sister", [("zarina", "heat", "Zarina Ephemera", "Эфемера: Царина")])
WEAPONS = {"data": [{"slug": "kuva_kohm", "i18n": {"en": {"name": "Kuva Kohm"}, "ru": {"name": "Кува Ком"}}}]}
SIS_WEAPONS = {"data": [{"slug": "tenet_tetra", "i18n": {"en": {"name": "Tenet Tetra"}, "ru": {"name": "Тетра Догмат"}}}]}


def auction(aid, kind="lich", element="electricity", eph=True, price=150, weapon="kuva_kohm",
            direct=True, closed=False, visible=True, created=NOW, status="ingame"):
    return {
        "id": aid, "buyout_price": price, "starting_price": price, "is_direct_sell": direct,
        "closed": closed, "visible": visible, "created": created.isoformat(),
        "owner": {"ingame_name": "seller" + aid, "status": status},
        "item": {"type": kind, "element": element, "having_ephemera": eph, "damage": 35, "weapon_url_name": weapon},
    }


def riven_auction(aid):
    return {"id": aid, "buyout_price": 50, "is_direct_sell": True, "closed": False, "visible": True,
            "created": NOW.isoformat(), "owner": {"ingame_name": "x", "status": "ingame"},
            "item": {"type": "riven", "weapon_url_name": "phenmor", "name": "hexatis", "attributes": []}}


def test_parse_ephemeras_names_and_thumbs():
    e = parse_ephemeras("lich", LICH)
    assert [(x.kind, x.element, x.slug, x.name) for x in e] == [
        ("lich", "electricity", "vengeful_charge", "Заряд Мщения"),
        ("lich", "heat", "vengeful_flame", "Пламя Мщения")]
    assert e[0].name_en == "Vengeful Charge Ephemera"
    assert e[0].thumb == "lich_ephemeras/images/thumbs/vengeful_charge.png"


def test_lots_only_direct_open_lich_and_sister_with_ephemera():
    lots = lots_from_auctions([
        auction("a1"), auction("a2", eph=False), auction("a3", direct=False), auction("a4", closed=True),
        auction("a5", visible=False), riven_auction("r1"), auction("s1", kind="sister", element="heat", weapon="tenet_tetra"),
    ])
    assert [l.id for l in lots] == ["a1", "s1"]
    a1 = lots[0]
    assert (a1.kind, a1.element, a1.weapon, a1.price, a1.damage, a1.seller_status) == ("lich", "electricity", "kuva_kohm", 150, 35, "ingame")
    assert a1.url == "https://warframe.market/auction/a1"


def test_watch_matches_kind_element_weapon_and_price():
    lot = lots_from_auctions([auction("a1", price=150)])[0]
    assert watch_matches(EphWatch(1, "lich", "electricity", None, None, False), lot)
    assert watch_matches(EphWatch(1, "lich", "electricity", "kuva_kohm", 150, False), lot)
    assert not watch_matches(EphWatch(1, "lich", "electricity", None, 149, False), lot)
    assert not watch_matches(EphWatch(1, "lich", "heat", None, None, False), lot)
    assert not watch_matches(EphWatch(1, "sister", "electricity", None, None, False), lot)
    assert not watch_matches(EphWatch(1, "lich", "electricity", "kuva_bramma", None, False), lot)


@pytest.fixture
def tracker(tmp_path):
    db = Db(tmp_path / "t.db")
    http = HttpClient(sleep=lambda s: _noop(), clock=lambda: 0.0)
    notices = []
    clock = {"t": NOW.timestamp()}
    t = EphemeraTracker(http, db, tmp_path, notifier=notices.append, clock=lambda: clock["t"])
    t.notices, t.clk = notices, clock
    return t


async def _noop():
    return None


def mock_catalog():
    respx.get("https://api.warframe.market/v2/lich/ephemeras").mock(return_value=httpx.Response(200, json=LICH))
    respx.get("https://api.warframe.market/v2/sister/ephemeras").mock(return_value=httpx.Response(200, json=SISTER))
    respx.get("https://api.warframe.market/v2/lich/weapons").mock(return_value=httpx.Response(200, json=WEAPONS))
    respx.get("https://api.warframe.market/v2/sister/weapons").mock(return_value=httpx.Response(200, json=SIS_WEAPONS))


@respx.mock
async def test_catalog_loads_once_and_is_cached_on_disk(tracker, tmp_path):
    mock_catalog()
    await tracker.load_catalog()
    assert [e.slug for e in tracker.ephemeras] == ["vengeful_charge", "vengeful_flame", "zarina"]
    assert tracker.weapon_name("lich", "kuva_kohm") == "Кува Ком"
    calls = respx.calls.call_count
    again = EphemeraTracker(tracker.http, tracker.db, tmp_path, notifier=lambda n: None, clock=tracker.clock)
    await again.load_catalog()
    assert respx.calls.call_count == calls
    assert len(again.ephemeras) == 3


@respx.mock
async def test_tick_collects_lots_from_recent_feed_and_keeps_them(tracker):
    route = respx.get(RECENT_URL).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [
        auction("a1", price=150), riven_auction("r1")]}}))
    await tracker.tick()
    route.mock(return_value=httpx.Response(200, json={"payload": {"auctions": [auction("a2", price=90)]}}))
    await tracker.tick()
    assert [l.id for l in tracker.lots()] == ["a2", "a1"]  # cheapest first, a1 kept though it left the feed
    assert [l.id for l in tracker.lots(kind="lich", element="electricity")] == ["a2", "a1"]
    assert tracker.lots(kind="lich", element="heat") == []


@respx.mock
async def test_lots_are_dropped_after_two_days_and_when_closed(tracker):
    route = respx.get(RECENT_URL).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [
        auction("a1"), auction("a2")]}}))
    await tracker.tick()
    route.mock(return_value=httpx.Response(200, json={"payload": {"auctions": [auction("a2", closed=True)]}}))
    await tracker.tick()
    assert [l.id for l in tracker.lots()] == ["a1"]
    tracker.clk["t"] += 49 * 3600
    route.mock(return_value=httpx.Response(200, json={"payload": {"auctions": []}}))
    await tracker.tick()
    assert tracker.lots() == []


@respx.mock
async def test_lots_survive_restart(tracker, tmp_path):
    respx.get(RECENT_URL).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [auction("a1")]}}))
    await tracker.tick()
    again = EphemeraTracker(tracker.http, tracker.db, tmp_path, notifier=lambda n: None, clock=tracker.clock)
    assert [l.id for l in again.lots()] == ["a1"]


@respx.mock
async def test_new_matching_lot_notifies_once_and_only_with_notify(tracker):
    mock_catalog()
    await tracker.load_catalog()
    tracker.add_watch("lich", "electricity", None, 200, notify=True)
    tracker.add_watch("lich", "heat", None, None, notify=True)
    tracker.add_watch("lich", "electricity", None, None, notify=False)
    route = respx.get(RECENT_URL).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [
        auction("a1", price=150), auction("a2", price=500)]}}))
    await tracker.tick()
    await tracker.tick()
    assert len(tracker.notices) == 1
    n = tracker.notices[0]
    assert "Заряд Мщения" in n.title and "150" in n.body and "Кува Ком" in n.body
    assert n.url == "https://warframe.market/auction/a1"


@respx.mock
async def test_old_lots_do_not_notify(tracker):
    tracker.add_watch("lich", "electricity", None, None, notify=True)
    respx.get(RECENT_URL).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [
        auction("a1", created=NOW - timedelta(hours=3))]}}))
    await tracker.tick()
    assert tracker.notices == []
    assert [l.id for l in tracker.lots()] == ["a1"]


@respx.mock
async def test_search_tick_queries_each_watch_and_merges(tracker):
    w = tracker.add_watch("sister", "heat", "tenet_tetra", None, notify=False)
    route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [
        auction("s1", kind="sister", element="heat", weapon="tenet_tetra", price=300)]}}))
    await tracker.search_tick()
    q = dict(route.calls.last.request.url.params)
    assert q == {"type": "sister", "has_ephemera": "true", "element": "heat", "weapon_url_name": "tenet_tetra",
                 "buyout_policy": "direct", "sort_by": "price_asc"}
    assert [l.id for l in tracker.lots(kind="sister")] == ["s1"]
    assert tracker.watches()[0].id == w


@respx.mock
async def test_search_failure_does_not_break(tracker):
    tracker.add_watch("lich", "heat", None, None, notify=False)
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(400, json={"error": {}}))
    await tracker.search_tick()
    assert tracker.lots() == []


def test_watches_add_list_remove(tracker):
    a = tracker.add_watch("lich", "heat", None, 100, notify=True)
    b = tracker.add_watch("sister", "cold", "tenet_tetra", None, notify=False)
    assert [(w.id, w.kind, w.element, w.weapon, w.max_price, w.notify) for w in tracker.watches()] == [
        (a, "lich", "heat", None, 100, True), (b, "sister", "cold", "tenet_tetra", None, False)]
    tracker.remove_watch(a)
    assert [w.id for w in tracker.watches()] == [b]


def test_add_watch_rejects_unknown_kind_or_element(tracker):
    with pytest.raises(ValueError):
        tracker.add_watch("coda", "heat", None, None, notify=False)
    with pytest.raises(ValueError):
        tracker.add_watch("lich", "void", None, None, notify=False)


@respx.mock
async def test_summary_counts_and_cheapest_per_ephemera(tracker):
    mock_catalog()
    await tracker.load_catalog()
    respx.get(RECENT_URL).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [
        auction("a1", price=150), auction("a2", price=90), auction("s1", kind="sister", element="heat", weapon="tenet_tetra", price=300)]}}))
    await tracker.tick()
    s = {(x["kind"], x["element"]): x for x in tracker.summary()}
    assert (s[("lich", "electricity")]["count"], s[("lich", "electricity")]["min_price"]) == (2, 90)
    assert (s[("lich", "heat")]["count"], s[("lich", "heat")]["min_price"]) == (0, None)
    assert s[("sister", "heat")]["name"] == "Царина"
