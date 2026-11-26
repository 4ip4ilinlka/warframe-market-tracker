import json
from pathlib import Path

import httpx
import pytest
import respx

from wfmt.db import Db
from wfmt.http import HttpClient
from wfmt.models import RivenAttr, RivenLot, RivenWatch
from wfmt.rivens import matches, new_lots, riven_interval, search_lots, weapon_median

FX = Path(__file__).parent / "fixtures"
SEARCH = "https://api.warframe.market/v1/auctions/search"


def auction(aid, price, status="ingame", direct=True, attrs=None):
    return {
        "id": aid,
        "buyout_price": price,
        "starting_price": price,
        "is_direct_sell": direct,
        "visible": True,
        "closed": False,
        "owner": {"ingame_name": "s" + aid, "status": status},
        "item": {
            "type": "riven",
            "weapon_url_name": "phenmor",
            "name": "hexatis",
            "re_rolls": 1,
            "mastery_level": 12,
            "polarity": "vazarin",
            "attributes": attrs
            or [
                {"value": 100, "positive": True, "url_name": "critical_chance"},
                {"value": 80, "positive": True, "url_name": "critical_damage"},
                {"value": -20, "positive": False, "url_name": "zoom"},
            ],
        },
    }


def lot(price=100, attrs=None):
    attrs = attrs or [
        RivenAttr("critical_chance", 100, True),
        RivenAttr("critical_damage", 80, True),
        RivenAttr("zoom", -20, False),
    ]
    return RivenLot("a1", "phenmor", "hexatis", price, attrs, 12, 1, "vazarin", "s", "ingame", "u")


@pytest.fixture
async def http():
    c = HttpClient(max_rps=1000)
    yield c
    await c.aclose()


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "t.sqlite3")


def test_matches_positive_attrs():
    assert matches(lot(), RivenWatch(1, "phenmor", ["critical_chance", "critical_damage"]))
    assert not matches(lot(), RivenWatch(1, "phenmor", ["multishot"]))


def test_matches_negative():
    assert matches(lot(), RivenWatch(1, "phenmor", [], "zoom"))
    assert not matches(lot(), RivenWatch(1, "phenmor", [], "recoil"))


def test_matches_max_price():
    assert matches(lot(price=100), RivenWatch(1, "phenmor", [], None, 100))
    assert not matches(lot(price=101), RivenWatch(1, "phenmor", [], None, 100))


@respx.mock
async def test_only_buyout_and_online(http):
    route = respx.get(SEARCH).mock(
        return_value=httpx.Response(
            200,
            json={
                "payload": {
                    "auctions": [
                        auction("1", 50, status="offline"),
                        auction("2", None, direct=False),
                        auction("3", 70),
                        auction("4", 60, status="online"),
                    ]
                }
            },
        )
    )
    lots = await search_lots(http, RivenWatch(1, "phenmor", ["critical_chance"], "zoom", None))
    assert [l.id for l in lots] == ["4", "3"]
    q = route.calls.last.request.url.params
    assert q["weapon_url_name"] == "phenmor"
    assert q["positive_stats"] == "critical_chance"
    assert q["negative_stats"] == "zoom"
    assert q["buyout_policy"] == "direct"
    assert lots[0].url == "https://warframe.market/auction/4"


@respx.mock
async def test_parses_real_response(http):
    data = json.loads((FX / "riven_search.json").read_text(encoding="utf-8"))
    for a in data["payload"]["auctions"]:
        a["owner"]["status"] = "ingame"
    respx.get(SEARCH).mock(return_value=httpx.Response(200, json=data))
    lots = await search_lots(http, RivenWatch(1, "phenmor"))
    assert len(lots) == 3
    assert lots[0].weapon_slug == "phenmor"
    assert lots[0].attributes[0].url_name


async def test_new_lots_only_unseen(db):
    wid = db.riven_watch_add(RivenWatch(None, "phenmor"))
    w = db.riven_watch_list()[0]
    a, b = lot(), lot()
    b.id = "b2"
    assert [l.id for l in new_lots(db, w, [a])] == ["a1"]
    assert [l.id for l in new_lots(db, w, [a, b])] == ["b2"]
    assert db.riven_seen_ids(wid) == {"a1", "b2"}


def test_interval_scales_with_weapon_count():
    from wfmt import config

    assert riven_interval(0) == 10
    assert riven_interval(1) == 10
    n_fast = int(10 * config.RIVEN_MAX_RPS)          # weapons that still fit in 10 s
    assert riven_interval(n_fast) == 10
    assert riven_interval(30) > 10
    assert 30 / riven_interval(30) <= config.RIVEN_MAX_RPS + 1e-9


@respx.mock
async def test_weapon_median(http):
    respx.get(SEARCH).mock(
        return_value=httpx.Response(
            200, json={"payload": {"auctions": [auction("1", 10, "offline"), auction("2", 30), auction("3", 50)]}}
        )
    )
    assert await weapon_median(http, "phenmor") == 30


def test_is_harmless():
    from wfmt.rivens import is_harmless

    assert is_harmless(None)
    assert is_harmless("zoom")
    assert is_harmless("damage_vs_grineer")
    assert is_harmless("damage_to_orokin")
    assert not is_harmless("critical_damage")
    assert not is_harmless("multishot")


def _lot(aid, price, neg):
    attrs = [{"value": 100, "positive": True, "url_name": "critical_chance"},
             {"value": 90, "positive": True, "url_name": "multishot"}]
    if neg:
        attrs.append({"value": -30, "positive": False, "url_name": neg})
    return {"id": aid, "buyout_price": price, "owner": {"status": "offline"},
            "item": {"type": "riven", "weapon_url_name": "rubico", "attributes": attrs}}


@respx.mock
async def test_riven_value_uses_similar_lots_with_same_curse_kind(http):
    from wfmt.rivens import riven_value

    route = respx.get(SEARCH).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [
        _lot("1", 100, "zoom"), _lot("2", 200, None), _lot("3", 300, "damage_vs_corpus"),
        _lot("4", 10, "critical_damage"), _lot("5", 20, "multishot_x")]}}))
    v = await riven_value(http, "rubico", ["critical_chance", "multishot"], "zoom")
    assert (v.price, v.count, v.basis) == (200, 3, "similar")
    q = route.calls.last.request.url.params
    assert q["positive_stats"] == "critical_chance,multishot"


@respx.mock
async def test_riven_value_harmful_curse_uses_harmful_lots(http):
    from wfmt.rivens import riven_value

    respx.get(SEARCH).mock(return_value=httpx.Response(200, json={"payload": {"auctions": [
        _lot("1", 100, "zoom"), _lot("2", 10, "critical_damage"), _lot("3", 20, "fire_rate"), _lot("4", 30, "magazine_capacity")]}}))
    v = await riven_value(http, "rubico", ["critical_chance", "multishot"], "critical_damage")
    assert (v.price, v.count) == (20, 3)


@respx.mock
async def test_riven_value_falls_back_to_weapon(http):
    from wfmt.rivens import riven_value

    calls = []

    def route(request):
        calls.append(request.url.params.get("positive_stats"))
        if request.url.params.get("positive_stats"):
            return httpx.Response(200, json={"payload": {"auctions": [_lot("1", 100, None)]}})
        return httpx.Response(200, json={"payload": {"auctions": [_lot("a", 40, None), _lot("b", 60, None)]}})

    respx.get(SEARCH).mock(side_effect=route)
    v = await riven_value(http, "rubico", ["critical_chance", "multishot", "fire_rate"], None)
    assert calls == ["critical_chance,multishot,fire_rate", "critical_chance,multishot", None]
    assert (v.price, v.basis) == (50, "weapon")
