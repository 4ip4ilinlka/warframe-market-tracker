from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from wfmt.catalog import Catalog
from wfmt.db import Db
from wfmt.http import HttpClient
from wfmt.models import InvItem, InvRiven, PriceSnapshot
from wfmt.sell import build_sell_list, fill_prices, price_targets

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
API = "https://api.warframe.market"


def item(slug, ref, max_rank=None, tags=("prime",)):
    return {
        "id": "id_" + slug,
        "slug": slug,
        "game_ref": ref,
        "name_ru": slug.upper(),
        "name_en": slug,
        "tags": list(tags),
        "max_rank": max_rank,
        "thumb": None,
    }


@pytest.fixture
def catalog(tmp_path):
    c = Catalog(None, tmp_path)
    c._index(
        {
            "fetched_at": 0,
            "items": [
                item("ash_sys", "/A/Sys"),
                item("soma_rec", "/S/Rec"),
                item("bullseye", "/M/Bull", max_rank=5, tags=("mod",)),
            ],
            "weapons": [
                {"slug": "kulstar", "game_ref": "/W/Kul", "name_ru": "Кулстар", "group": "secondary", "disposition": 1.3}
            ],
            "attrs": [{"slug": "critical_chance", "game_ref": "WeaponCritChanceMod", "name_ru": "Крит. шанс"},
                      {"slug": "zoom", "game_ref": "WeaponZoomFovMod", "name_ru": "Приближение"}],
        }
    )
    return c


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "t.sqlite3")


@pytest.fixture
async def http():
    c = HttpClient(max_rps=1000)
    yield c
    await c.aclose()


def price(db, slug, rank, median, at=NOW):
    db.price_save(PriceSnapshot(slug, rank, median + 2, median - 2, median, 5, at))


async def test_sorted_by_total(catalog, db, http):
    db.inventory_save([InvItem("/A/Sys", 3, None), InvItem("/S/Rec", 1, None)], [], NOW)
    price(db, "ash_sys", None, 10)
    price(db, "soma_rec", None, 50)
    sl = await build_sell_list(catalog, http, db, now=NOW, riven_prices=False)
    assert [(r.slug, r.count, r.unit_price, r.total) for r in sl.rows] == [
        ("soma_rec", 1, 50, 50),
        ("ash_sys", 3, 10, 30),
    ]


async def test_max_rank_mod_uses_max_rank_price(catalog, db, http):
    db.inventory_save(
        [InvItem("/M/Bull", 2, 5), InvItem("/M/Bull", 1, 2), InvItem("/M/Bull", 4, 0)], [], NOW
    )
    price(db, "bullseye", 5, 30)
    price(db, "bullseye", 0, 5)
    sl = await build_sell_list(catalog, http, db, now=NOW, riven_prices=False)
    got = {(r.rank, r.count, r.unit_price) for r in sl.rows}
    # real ranks are shown; a partly ranked mod is priced as rank 0
    assert got == {(5, 2, 30), (2, 1, 5), (0, 4, 5)}


async def test_unmatched_items_counted_not_listed(catalog, db, http):
    db.inventory_save([InvItem("/A/Sys", 1, None), InvItem("/Unknown/Thing", 7, None)], [], NOW)
    sl = await build_sell_list(catalog, http, db, now=NOW, riven_prices=False)
    assert [r.slug for r in sl.rows] == ["ash_sys"]
    assert sl.unmatched == 1


async def test_missing_price_listed_last(catalog, db, http):
    db.inventory_save([InvItem("/A/Sys", 1, None), InvItem("/S/Rec", 1, None)], [], NOW)
    price(db, "ash_sys", None, 10)
    sl = await build_sell_list(catalog, http, db, now=NOW, riven_prices=False)
    assert [(r.slug, r.unit_price) for r in sl.rows] == [("ash_sys", 10), ("soma_rec", None)]


async def test_cached_price_reused(catalog, db, http):
    db.inventory_save([InvItem("/A/Sys", 1, None), InvItem("/S/Rec", 1, None)], [], NOW)
    price(db, "ash_sys", None, 10, at=NOW - timedelta(minutes=5))  # fresh
    price(db, "soma_rec", None, 10, at=NOW - timedelta(hours=4))  # stale
    assert price_targets(catalog, db, now=NOW) == [("soma_rec", None)]
    with respx.mock as router:
        respx.get(f"{API}/v2/orders/item/soma_rec/top").mock(
            return_value=httpx.Response(200, json={"data": {"sell": [], "buy": []}})
        )
        respx.get(f"{API}/v1/items/soma_rec/statistics").mock(
            return_value=httpx.Response(200, json={"payload": {"statistics_closed": {"48hours": []}}})
        )
        done = await fill_prices(catalog, http, db, now=NOW)
        assert done == 1
        assert router.calls.call_count == 2


@respx.mock
async def test_rivens_listed_with_reference(catalog, db, http):
    db.inventory_save([], [InvRiven("/W/Kul", [("WeaponCritChanceMod", 0.5)], [], 3, 10)], NOW)
    respx.get(f"{API}/v1/auctions/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "payload": {
                    "auctions": [
                        {"id": "1", "buyout_price": 40, "owner": {}, "item": {"type": "riven", "attributes": []}},
                        {"id": "2", "buyout_price": 60, "owner": {}, "item": {"type": "riven", "attributes": []}},
                    ]
                }
            },
        )
    )
    sl = await build_sell_list(catalog, http, db, now=NOW)
    (r,) = sl.rivens
    assert r.weapon_slug == "kulstar"
    assert r.weapon_name == "Кулстар"
    assert r.buffs == [("Крит. шанс", 0.5)]
    assert r.reference_price == 50


async def test_sell_list_uses_cached_values_without_fetching(catalog, db):
    from wfmt.rivens import RivenValue

    class NoHttp:
        def __getattr__(self, name):
            raise AssertionError("network used")

    db.inventory_save([], [InvRiven("/W/Kul", [("WeaponCritChanceMod", 0.5)], [], 0, 8)], NOW)
    key = ("kulstar", ("critical_chance",), True)
    sl = await build_sell_list(catalog, NoHttp(), db, now=NOW, median_cache={key: RivenValue(77, 5, "similar")}, fetch_medians=False)
    r = sl.rivens[0]
    assert (r.reference_price, r.reference_count, r.reference_basis, r.curse_harmless) == (77, 5, "similar", True)
    sl = await build_sell_list(catalog, NoHttp(), db, now=NOW, median_cache={}, fetch_medians=False)
    assert sl.rivens[0].reference_price is None


@respx.mock
async def test_fill_riven_values_once_per_kind(catalog, db, http):
    from wfmt.sell import fill_riven_values

    db.inventory_save([], [InvRiven("/W/Kul", [("WeaponCritChanceMod", 0.5)], [("WeaponZoomFovMod", 0.1)], 0, 8),
                           InvRiven("/W/Kul", [("WeaponCritChanceMod", 0.7)], [], 0, 8)], NOW)
    auctions = [{"id": str(i), "buyout_price": p, "owner": {}, "item": {"type": "riven", "attributes": [
        {"value": 100, "positive": True, "url_name": "critical_chance"}]}} for i, p in enumerate((40, 50, 60))]
    route = respx.get(f"{API}/v1/auctions/search").mock(
        return_value=httpx.Response(200, json={"payload": {"auctions": auctions}}))
    cache = {}
    await fill_riven_values(catalog, http, db, cache)
    assert cache[("kulstar", ("critical_chance",), True)].price == 50
    assert route.call_count == 1  # both rivens share the same kind


def test_relic_refinement_suffix_normalized(tmp_path, db):
    from wfmt.sell import normalize_ref

    assert normalize_ref("/Lotus/Types/Game/Projections/T1VoidProjectionGyrePrimeABronze") == \
        "/Lotus/Types/Game/Projections/T1VoidProjectionGyrePrimeA"
    assert normalize_ref("/Lotus/Types/Game/Projections/T2VoidProjectionGyrePrimeBPlatinum") == \
        "/Lotus/Types/Game/Projections/T2VoidProjectionGyrePrimeB"
    assert normalize_ref("/Lotus/Types/Recipes/Bronze") == "/Lotus/Types/Recipes/Bronze"  # only relics


async def test_relics_matched_in_sell_list(tmp_path, db, http):
    c = Catalog(None, tmp_path)
    c._index({"fetched_at": 0, "weapons": [], "attrs": [], "items": [
        item("lith_g1_relic", "/Lotus/Types/Game/Projections/T1VoidProjectionGyrePrimeA", tags=("relic",))]})
    db.inventory_save([InvItem("/Lotus/Types/Game/Projections/T1VoidProjectionGyrePrimeABronze", 4, None),
                       InvItem("/Lotus/Types/Game/Projections/T1VoidProjectionGyrePrimeASilver", 1, None)], [], NOW)
    sl = await build_sell_list(c, http, db, now=NOW, riven_prices=False)
    assert [(r.slug, r.count) for r in sl.rows] == [("lith_g1_relic", 5)]
    assert sl.unmatched == 0


def test_melee_riven_tags_aliased(tmp_path):
    from wfmt.sell import _attr_names

    c = Catalog(None, tmp_path)
    c._index({"fetched_at": 0, "items": [], "weapons": [], "attrs": [
        {"slug": "base_damage_/_melee_damage", "game_ref": "WeaponDamageAmountMod", "name_ru": "Урон"},
        {"slug": "damage_vs_infested", "game_ref": "WeaponFactionDamageInfested", "name_ru": "Урон по заражённым"}]})
    assert _attr_names(c, [("WeaponMeleeDamageMod", 0.5), ("WeaponMeleeFactionDamageInfested", 0.1)]) == [
        ("Урон", 0.5), ("Урон по заражённым", 0.1)]


async def test_rows_carry_market_min_part_and_category(catalog, db, http):
    db.inventory_save([InvItem("/A/Sys", 1, None)], [], NOW)
    price(db, "ash_sys", None, 10)  # sell_min = 12
    (r,) = (await build_sell_list(catalog, http, db, now=NOW, riven_prices=False)).rows
    assert r.market_min == 12
    assert r.category == "prime"


async def test_unmatched_groups(catalog, db, http):
    db.inventory_save([InvItem("/Lotus/Types/Items/MiscItems/OrokinCell", 5, None),
                       InvItem("/Lotus/Types/Items/MiscItems/Neurode", 5, None),
                       InvItem("/Lotus/Types/Recipes/X", 1, None)], [], NOW)
    sl = await build_sell_list(catalog, http, db, now=NOW, riven_prices=False)
    assert sl.unmatched == 3
    assert sl.unmatched_groups == {"Ресурсы": 2, "Чертежи": 1}


@respx.mock
async def test_fill_rivens_first_then_tops_by_priority_then_stats(catalog, db, http):
    from wfmt.sell import fill_prices

    db.inventory_save([InvItem("/S/Rec", 1, None), InvItem("/M/Bull", 1, 0)],
                      [InvRiven("/W/Kul", [], [], 0, 8)], NOW)
    calls = []

    def rec(kind):
        def f(request):
            calls.append((kind, request.url.path))
            if kind == "riven":
                return httpx.Response(200, json={"payload": {"auctions": []}})
            if kind == "top":
                return httpx.Response(200, json={"data": {"sell": [{"platinum": 7, "user": {"status": "ingame"}}], "buy": []}})
            return httpx.Response(200, json={"payload": {"statistics_closed": {"48hours": []}}})
        return f

    respx.get(f"{API}/v1/auctions/search").mock(side_effect=rec("riven"))
    respx.get(url__regex=r".*/v2/orders/item/.*/top").mock(side_effect=rec("top"))
    respx.get(url__regex=r".*/v1/items/.*/statistics").mock(side_effect=rec("stats"))
    medians = {}
    await fill_prices(catalog, http, db, now=NOW, medians=medians)
    kinds = [k for k, _ in calls]
    assert kinds == ["riven", "top", "top", "stats", "stats"]
    assert "bullseye" in calls[1][1]  # mods before prime parts
    assert db.price_latest("soma_rec", None).sell_min == 7


def test_price_targets_respect_max_age(catalog, db):
    db.inventory_save([InvItem("/A/Sys", 1, None)], [], NOW)
    price(db, "ash_sys", None, 10, at=NOW - timedelta(hours=1))
    assert price_targets(catalog, db, now=NOW) == []  # inventory prices stay fresh for 3 h
    assert price_targets(catalog, db, now=NOW, max_age_s=30 * 60) == [("ash_sys", None)]


@respx.mock
async def test_fill_skips_stats_for_cheap_items(catalog, db, http):
    from wfmt.sell import fill_prices

    db.inventory_save([InvItem("/A/Sys", 1, None), InvItem("/S/Rec", 1, None)], [], NOW)

    def top(request):
        plat = 2 if "ash_sys" in request.url.path else 20
        return httpx.Response(200, json={"data": {"sell": [{"platinum": plat, "user": {"status": "online"}}], "buy": []}})

    respx.get(url__regex=r".*/v2/orders/item/.*/top").mock(side_effect=top)
    stats = respx.get(url__regex=r".*/v1/items/.*/statistics").mock(
        return_value=httpx.Response(200, json={"payload": {"statistics_closed": {"48hours": []}}}))
    await fill_prices(catalog, http, db, now=NOW)
    assert [c.request.url.path for c in stats.calls] == ["/v1/items/soma_rec/statistics"]
    assert db.price_latest("ash_sys", None).sell_min == 2


async def test_rows_carry_rarity_and_tier(tmp_path, db, http):
    c = Catalog(None, tmp_path)
    c._index({"fetched_at": 0, "weapons": [], "attrs": [], "items": [
        item("vitality", "/M/V", max_rank=10, tags=("mod", "common")),
        item("lith_g1_relic", "/R/G1", tags=("relic",))]})
    db.inventory_save([InvItem("/M/V", 1, 0), InvItem("/R/G1", 1, None)], [], NOW)
    rows = {r.slug: r for r in (await build_sell_list(c, http, db, now=NOW, riven_prices=False)).rows}
    assert rows["vitality"].rarity == "common"
    assert rows["lith_g1_relic"].tier == "lith"


@respx.mock
async def test_fill_reports_riven_stage_first(catalog, db, http):
    from wfmt.sell import fill_prices

    db.inventory_save([InvItem("/A/Sys", 1, None)], [], NOW)
    respx.get(url__regex=r".*/v2/orders/item/.*/top").mock(
        return_value=httpx.Response(200, json={"data": {"sell": [], "buy": []}}))
    respx.get(url__regex=r".*/v1/items/.*/statistics").mock(
        return_value=httpx.Response(200, json={"payload": {"statistics_closed": {"48hours": []}}}))
    seen = []
    await fill_prices(catalog, http, db, now=NOW, medians={}, progress=lambda d, t: seen.append((d, t)))
    assert seen[0] == (0, 0)  # 0/0 = "valuing rivens" stage, before the price total is known
    assert seen[1] == (0, 2)


@respx.mock
async def test_fill_uses_item_default_subtype(tmp_path, db, http):
    from wfmt.sell import fill_prices

    c = Catalog(None, tmp_path)
    rel = item("lith_s16_relic", "/R/S16", tags=("relic",))
    rel["subtypes"] = ["intact", "exceptional", "flawless", "radiant"]
    c._index({"fetched_at": 0, "weapons": [], "attrs": [], "items": [rel]})
    db.inventory_save([InvItem("/R/S16", 3, None)], [], NOW)
    top = respx.get(url__regex=r".*/v2/orders/item/.*/top").mock(
        return_value=httpx.Response(200, json={"data": {"sell": [], "buy": []}}))
    respx.get(url__regex=r".*/v1/items/.*/statistics").mock(
        return_value=httpx.Response(200, json={"payload": {"statistics_closed": {"48hours": []}}}))
    await fill_prices(c, http, db, now=NOW)
    assert top.calls.last.request.url.params["subtype"] == "intact"


async def test_rows_carry_subcategory_from_set(tmp_path, db, http):
    c = Catalog(None, tmp_path)
    c._index({"fetched_at": 0, "weapons": [], "attrs": [], "items": [
        item("soma_prime_barrel", "/S/Barrel", tags=("component", "prime", "weapon")),
        item("soma_prime_set", "/S/Set", tags=("weapon", "prime", "primary", "set"))]})
    db.inventory_save([InvItem("/S/Barrel", 2, None)], [], NOW)
    (r,) = (await build_sell_list(c, http, db, now=NOW, riven_prices=False)).rows
    assert (r.sub, r.sub_label) == ("prime:primary", "Основное")


def test_select_targets_by_subcategory(catalog, db):
    from wfmt.sell import select_targets

    db.inventory_save([InvItem("/A/Sys", 1, None), InvItem("/M/Bull", 1, 0)], [], NOW)
    price(db, "bullseye", 0, 5, at=NOW)  # fresh, but forced refresh ignores age
    assert select_targets(catalog, db, subs={"mod:other"}, max_age_s=0, now=NOW) == [("bullseye", 0)]
    assert set(select_targets(catalog, db, subs=None, max_age_s=0, now=NOW)) == {("bullseye", 0), ("ash_sys", None)}


@respx.mock
async def test_fill_with_explicit_targets_and_own_orders_excluded(catalog, db, http):
    from wfmt.sell import fill_prices

    route = respx.get(url__regex=r".*/v2/orders/item/.*/top").mock(return_value=httpx.Response(200, json={"data": {
        "sell": [{"platinum": 3, "user": {"ingameName": "Me", "status": "ingame"}},
                 {"platinum": 9, "user": {"ingameName": "Other", "status": "ingame"}}], "buy": []}}))
    respx.get(url__regex=r".*/v1/items/.*/statistics").mock(
        return_value=httpx.Response(200, json={"payload": {"statistics_closed": {"48hours": []}}}))
    await fill_prices(catalog, http, db, now=NOW, targets=[("soma_rec", None)], exclude_user="me")
    assert [c.request.url.path for c in route.calls] == ["/v2/orders/item/soma_rec/top"]
    assert db.price_latest("soma_rec", None).sell_min == 9  # my own 3-plat lot is not "the market"


def test_auto_targets_hot_items_refresh_sooner(catalog, db):
    from wfmt.sell import auto_targets

    db.inventory_save([InvItem("/A/Sys", 1, None), InvItem("/S/Rec", 1, None), InvItem("/M/Bull", 1, 0)], [], NOW)
    price(db, "ash_sys", None, 10, at=NOW - timedelta(minutes=20))   # listed by me -> hot
    price(db, "soma_rec", None, 10, at=NOW - timedelta(minutes=20))  # ordinary, still fresh (< 1 h)
    price(db, "bullseye", 0, 10, at=NOW - timedelta(hours=2))        # ordinary, stale
    got = auto_targets(catalog, db, listed_ids={"id_ash_sys"}, top_n=0, now=NOW)
    assert set(got) == {("ash_sys", None), ("bullseye", 0)}


def test_items_without_price_come_first(catalog, db):
    from wfmt.sell import auto_targets, select_targets

    # a mod (top category) with an old price, and a prime part with no price at all
    db.inventory_save([InvItem("/M/Bull", 1, 0), InvItem("/S/Rec", 1, None)], [], NOW)
    price(db, "bullseye", 0, 5, at=NOW - timedelta(hours=5))
    assert price_targets(catalog, db, now=NOW)[0] == ("soma_rec", None)
    assert select_targets(catalog, db, subs=None, max_age_s=0, now=NOW)[0] == ("soma_rec", None)
    assert auto_targets(catalog, db, listed_ids={"id_bullseye"}, now=NOW)[0] == ("soma_rec", None)


async def test_rows_carry_ducats_and_vaulted(tmp_path, db, http):
    c = Catalog(None, tmp_path)
    it = item("ash_sys", "/A/Sys")
    it["ducats"] = 45
    it["vaulted"] = True
    c._index({"fetched_at": 0, "weapons": [], "attrs": [], "items": [it]})
    db.inventory_save([InvItem("/A/Sys", 1, None)], [], NOW)
    (r,) = (await build_sell_list(c, http, db, now=NOW, riven_prices=False)).rows
    assert (r.ducats, r.vaulted) == (45, True)
