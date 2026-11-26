from datetime import datetime, timezone

import httpx
import pytest
import respx

from wfmt.alerts import check_price_alerts, riven_notices
from wfmt.catalog import Catalog
from wfmt.db import Db
from wfmt.http import HttpClient
from wfmt.models import Alert, PriceSnapshot, RivenAttr, RivenLot, RivenWatch
from wfmt.scheduler import Scheduler

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
SEARCH = "https://api.warframe.market/v1/auctions/search"


def snap(sell):
    return PriceSnapshot("ash", None, sell, None, None, 0, T0)


def lot(aid, price):
    return RivenLot(aid, "kulstar", "x", price, [RivenAttr("critical_chance", 1, True)], 8, 0, "v", "s", "ingame", "u/" + aid)


def test_price_below_fires_once():
    alerts = [Alert(1, "price_below", "ash", None, 20, None)]
    fired: set[int] = set()
    n = check_price_alerts(alerts, [snap(18)], fired, names={"ash": "Эш"})
    assert len(n) == 1 and "Эш" in n[0].title and "18" in n[0].body
    assert check_price_alerts(alerts, [snap(15)], fired) == []


def test_price_alert_rearms():
    alerts = [Alert(1, "price_above", "ash", None, 30, None)]
    fired: set[int] = set()
    assert len(check_price_alerts(alerts, [snap(31)], fired)) == 1
    assert check_price_alerts(alerts, [snap(25)], fired) == []
    assert len(check_price_alerts(alerts, [snap(35)], fired)) == 1


def test_price_alert_ignores_other_rank_and_missing_price():
    alerts = [Alert(1, "price_below", "ash", 10, 20, None)]
    assert check_price_alerts(alerts, [snap(5)], set()) == []
    alerts = [Alert(2, "price_below", "ash", None, 20, None)]
    assert check_price_alerts(alerts, [snap(None)], set()) == []


def test_riven_notices():
    n = riven_notices(RivenWatch(1, "kulstar"), [lot("a", 50), lot("b", 40)], "Кулстар")
    assert len(n) == 2
    assert n[0].url == "u/b" and "40" in n[0].body and "Кулстар" in n[0].title


def test_riven_notices_capped():
    n = riven_notices(RivenWatch(1, "kulstar"), [lot(str(i), i) for i in range(10)], "Кулстар")
    assert len(n) == 3
    assert "ещё 8" in n[-1].body


# --- scheduler ---

@pytest.fixture
async def http():
    c = HttpClient(max_rps=1000)
    yield c
    await c.aclose()


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "t.sqlite3")


@pytest.fixture
def catalog(tmp_path):
    c = Catalog(None, tmp_path)
    c._index({"fetched_at": 0, "items": [], "attrs": [],
              "weapons": [{"slug": "kulstar", "game_ref": None, "name_ru": "Кулстар", "group": None, "disposition": 1}]})
    return c


def auctions(*pairs):
    return {"payload": {"auctions": [
        {"id": a, "buyout_price": p, "owner": {"status": "ingame", "ingame_name": "s"},
         "item": {"type": "riven", "weapon_url_name": "kulstar", "attributes": []}} for a, p in pairs]}}


@respx.mock
async def test_first_riven_poll_silent(http, db, catalog):
    sent = []
    wid = db.riven_watch_add(RivenWatch(None, "kulstar"))
    db.alert_add(Alert(None, "riven", None, None, None, wid))
    route = respx.get(SEARCH).mock(return_value=httpx.Response(200, json=auctions(("a", 10))))
    s = Scheduler(http, db, catalog, notifier=sent.append)
    await s.riven_tick()
    assert sent == []
    assert [l.id for l in s.riven_lots[wid]["lots"]] == ["a"]
    route.mock(return_value=httpx.Response(200, json=auctions(("a", 10), ("b", 12))))
    await s.riven_tick()
    assert len(sent) == 1 and "12" in sent[0].body
    assert s.riven_lots[wid]["new"] == {"b"}


@respx.mock
async def test_riven_without_alert_does_not_notify(http, db, catalog):
    sent = []
    db.riven_watch_add(RivenWatch(None, "kulstar"))
    route = respx.get(SEARCH).mock(return_value=httpx.Response(200, json=auctions(("a", 10))))
    s = Scheduler(http, db, catalog, notifier=sent.append)
    await s.riven_tick()
    route.mock(return_value=httpx.Response(200, json=auctions(("a", 10), ("b", 12))))
    await s.riven_tick()
    assert sent == []


async def test_scheduler_survives_exception(http, db, catalog):
    s = Scheduler(http, db, catalog, notifier=lambda n: None)
    calls = []

    async def boom():
        calls.append(1)
        raise RuntimeError("kaboom")

    await s._safe("prices", boom)
    await s._safe("prices", boom)
    assert len(calls) == 2
    assert "kaboom" in s.status()["last_error"]


@respx.mock
async def test_first_lot_after_empty_first_poll_notifies(http, db, catalog):
    sent = []
    wid = db.riven_watch_add(RivenWatch(None, "kulstar"))
    db.alert_add(Alert(None, "riven", None, None, None, wid))
    route = respx.get(SEARCH).mock(return_value=httpx.Response(200, json=auctions()))
    s = Scheduler(http, db, catalog, notifier=sent.append)
    await s.riven_tick()
    route.mock(return_value=httpx.Response(200, json=auctions(("a", 10))))
    await s.riven_tick()
    assert len(sent) == 1


@respx.mock
async def test_idle_ui_pauses_unalerted_watches(http, db, catalog):
    t = {"now": 1000.0}
    a = db.riven_watch_add(RivenWatch(None, "kulstar"))
    b = db.riven_watch_add(RivenWatch(None, "kulstar", ["critical_chance"]))
    db.alert_add(Alert(None, "riven", None, None, None, b))
    s = Scheduler(http, db, catalog, notifier=lambda n: None, clock=lambda: t["now"])
    s.ui_seen()
    assert [w.id for w in s.active_watches()] == [a, b]
    t["now"] += 601
    assert [w.id for w in s.active_watches()] == [b]


async def test_price_request_during_tick_not_lost(http, db, catalog):
    s = Scheduler(http, db, catalog, notifier=lambda n: None)

    async def tick():
        s.refresh_prices_now()  # e.g. a watch added while the tick runs

    s.price_tick = tick
    await s._price_once()
    assert s._price_now.is_set()


async def test_catalog_tick_loads_when_empty(http, db, tmp_path):
    calls = []

    class Cat:
        items = []

        def needs_refresh(self):
            return True

        async def load(self, force=False):
            calls.append(force)

    s = Scheduler(http, db, Cat(), notifier=lambda n: None)
    await s.catalog_tick()
    assert calls == [False]


def test_median_alerts():
    s = PriceSnapshot("ash", None, 50, None, 18.0, 4, T0)
    fired: set[int] = set()
    n = check_price_alerts([Alert(7, "median_below", "ash", None, 20, None)], [s], fired, names={"ash": "Эш"})
    assert len(n) == 1 and "медиана" in n[0].body.lower()
    assert check_price_alerts([Alert(8, "median_above", "ash", None, 20, None)], [s], set()) == []


@respx.mock
async def test_new_lot_highlight_lasts_a_minute(http, db, catalog):
    t = {"now": 1000.0}
    wid = db.riven_watch_add(RivenWatch(None, "kulstar"))
    route = respx.get(SEARCH).mock(return_value=httpx.Response(200, json=auctions(("a", 10))))
    s = Scheduler(http, db, catalog, notifier=lambda n: None, clock=lambda: t["now"])
    await s.riven_tick()
    route.mock(return_value=httpx.Response(200, json=auctions(("a", 10), ("b", 12))))
    await s.riven_tick()
    t["now"] += 30
    await s.riven_tick()
    assert s.riven_lots[wid]["new"] == {"b"}  # still highlighted after 30 s
    t["now"] += 31
    await s.riven_tick()
    assert s.riven_lots[wid]["new"] == set()
