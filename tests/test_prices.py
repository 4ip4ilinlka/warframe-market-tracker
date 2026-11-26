import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from wfmt.db import Db
from wfmt.http import HttpClient
from wfmt.models import PriceSnapshot
from wfmt.prices import effective_price, fetch_price, refresh_all, weighted_median

FX = Path(__file__).parent / "fixtures"
API = "https://api.warframe.market"
T0 = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def fx(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def order(plat, status, rank=None):
    o = {"platinum": plat, "user": {"status": status}}
    if rank is not None:
        o["rank"] = rank
    return o


@pytest.fixture
async def http():
    c = HttpClient(max_rps=1000)
    yield c
    await c.aclose()


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "t.sqlite3")


def mock_item(slug, sell, buy, stats):
    respx.get(f"{API}/v2/orders/item/{slug}/top").mock(
        return_value=httpx.Response(200, json={"data": {"sell": sell, "buy": buy}})
    )
    respx.get(f"{API}/v1/items/{slug}/statistics").mock(
        return_value=httpx.Response(200, json={"payload": {"statistics_closed": {"48hours": stats}}})
    )


@respx.mock
async def test_sell_min_ignores_offline(http):
    mock_item("x", [order(5, "offline"), order(9, "online"), order(7, "ingame")], [order(4, "online")], [])
    s = await fetch_price(http, "x", None, now=T0)
    assert s.sell_min == 7
    assert s.buy_max == 4
    assert s.median_48h is None and s.volume_48h == 0


@respx.mock
async def test_rank_filter(http):
    respx.get(f"{API}/v2/orders/item/primed_continuity/top", params={"rank": "10"}).mock(
        return_value=httpx.Response(200, json=fx("top_primed_continuity_r10.json"))
    )
    respx.get(f"{API}/v1/items/primed_continuity/statistics").mock(
        return_value=httpx.Response(200, json=fx("stats_primed_continuity.json"))
    )
    s = await fetch_price(http, "primed_continuity", 10, now=T0)
    assert s.sell_min == 100
    assert s.buy_max == 83
    # only rank-10 rows of real statistics: medians are all > 90
    assert s.median_48h > 90


def test_median_weighted_by_volume():
    rows = [{"median": 10, "volume": 1}, {"median": 20, "volume": 5}, {"median": 30, "volume": 1}]
    assert weighted_median(rows) == 20
    assert weighted_median([]) is None
    assert weighted_median([{"median": 10, "volume": 1}, {"median": 20, "volume": 1}]) == 15


def test_effective_price_fallback_to_sell_min():
    assert effective_price(PriceSnapshot("x", None, 12, 5, 9.6, 3, T0)) == 10
    assert effective_price(PriceSnapshot("x", None, 12, 5, None, 0, T0)) == 12
    assert effective_price(PriceSnapshot("x", None, None, 5, None, 0, T0)) is None


@respx.mock
async def test_refresh_keeps_old_snapshot_on_error(http, db):
    db.watch_add("good", None)
    db.watch_add("bad", None)
    old = PriceSnapshot("bad", None, 50, 40, 45, 3, T0)
    db.price_save(old)
    mock_item("good", [order(9, "online")], [], [])
    respx.get(f"{API}/v2/orders/item/bad/top").mock(return_value=httpx.Response(500))
    snaps = await refresh_all(http, db, now=T0)
    assert [s.slug for s in snaps] == ["good"]
    assert db.price_latest("good", None).sell_min == 9
    assert db.price_latest("bad", None).sell_min == 50


@respx.mock
async def test_refresh_survives_malformed_data(http, db):
    db.watch_add("weird", None)
    db.watch_add("good", None)
    respx.get(f"{API}/v2/orders/item/weird/top").mock(
        return_value=httpx.Response(200, json={"data": {"sell": [{"user": {"status": "online"}}], "buy": []}})
    )
    respx.get(f"{API}/v1/items/weird/statistics").mock(return_value=httpx.Response(200, json={}))
    mock_item("good", [order(9, "online")], [], [])
    snaps = await refresh_all(http, db, now=T0)
    assert [s.slug for s in snaps] == ["good"]


def test_effective_price_capped_by_cheapest_listing():
    # nobody pays the median if someone sells for less right now
    assert effective_price(PriceSnapshot("x", None, 1, None, 15.0, 40, T0)) == 1


@respx.mock
async def test_bulk_order_priced_per_unit(http):
    # "60 per trade, 6 per trade" means 10 per unit
    mock_item("lith", [{"platinum": 60, "perTrade": 6, "user": {"status": "ingame"}},
                       {"platinum": 12, "user": {"status": "online"}}], [], [])
    s = await fetch_price(http, "lith", None, now=T0)
    assert s.sell_min == 10


@respx.mock
async def test_subtype_filters_orders_and_stats(http):
    route = respx.get(f"{API}/v2/orders/item/lith/top").mock(return_value=httpx.Response(200, json={"data": {
        "sell": [{"platinum": 30, "subtype": "radiant", "user": {"status": "ingame"}},
                 {"platinum": 8, "subtype": "intact", "user": {"status": "ingame"}}], "buy": []}}))
    respx.get(f"{API}/v1/items/lith/statistics").mock(return_value=httpx.Response(200, json={"payload": {
        "statistics_closed": {"48hours": [{"median": 50, "volume": 5, "subtype": "radiant"},
                                          {"median": 5, "volume": 5, "subtype": "intact"}]}}}))
    s = await fetch_price(http, "lith", None, now=T0, subtype="intact")
    assert s.sell_min == 8
    assert s.median_48h == 5
    assert route.calls.last.request.url.params["subtype"] == "intact"


@respx.mock
async def test_stats_fall_back_to_recent_90_days(http):
    from datetime import timedelta
    from wfmt.prices import fetch_stats

    recent = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000+00:00")
    old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%dT00:00:00.000+00:00")
    respx.get(f"{API}/v1/items/x/statistics").mock(return_value=httpx.Response(200, json={"payload": {
        "statistics_closed": {"48hours": [], "90days": [
            {"datetime": old, "median": 30, "volume": 10},
            {"datetime": recent, "median": 7, "volume": 3}]}}}))
    median, volume = await fetch_stats(http, "x", None)
    assert (median, volume) == (7, 3)  # only the last 7 days count, not the old 30


@respx.mock
async def test_fetch_details(http):
    from wfmt.prices import fetch_details

    respx.get(f"{API}/v2/orders/item/x/top").mock(return_value=httpx.Response(200, json={"data": {
        "sell": [{"platinum": 60, "perTrade": 6, "quantity": 24, "user": {"ingameName": "Seller1", "status": "ingame", "reputation": 3}},
                 {"platinum": 4, "quantity": 20, "user": {"ingameName": "Off", "status": "offline"}}],
        "buy": [{"platinum": 3, "quantity": 5, "user": {"ingameName": "B", "status": "online"}}]}}))
    respx.get(f"{API}/v1/items/x/statistics").mock(return_value=httpx.Response(200, json={"payload": {
        "statistics_closed": {"48hours": [{"datetime": "2026-11-25T10:00:00.000+00:00", "median": 9, "min_price": 8, "max_price": 11, "volume": 2}],
                              "90days": [{"datetime": "2026-11-20T00:00:00.000+00:00", "median": 12, "min_price": 5, "max_price": 30, "volume": 7}]}}}))
    d = await fetch_details(http, "x", None)
    assert d["sellers"] == [{"name": "Seller1", "status": "ingame", "unit": 10, "per_trade": 6, "quantity": 24, "reputation": 3}]
    assert d["buyers"][0]["unit"] == 3
    assert d["h48"][0] == {"t": "2026-11-25T10:00:00.000+00:00", "median": 9, "min": 8, "max": 11, "volume": 2}
    assert d["d90"][0]["max"] == 30
