from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from wfmt.catalog import Catalog
from wfmt.db import Db
from wfmt.http import HttpClient
from wfmt.models import InvItem, PriceSnapshot
from wfmt.sets import buildable_sets, candidate_sets, fetch_set_parts

API = "https://api.warframe.market"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def item(slug, ref, tags=("component", "prime", "weapon"), ducats=None):
    return {"id": "id_" + slug, "slug": slug, "game_ref": ref, "name_ru": slug, "name_en": slug,
            "tags": list(tags), "max_rank": None, "thumb": None, "ducats": ducats}


@pytest.fixture
def catalog(tmp_path):
    c = Catalog(None, tmp_path)
    c._index({"fetched_at": 0, "weapons": [], "attrs": [], "items": [
        item("kamas_prime_set", "/K/Set", tags=("weapon", "prime", "set")),
        item("kamas_prime_blade", "/K/Blade", ducats=100),
        item("kamas_prime_handle", "/K/Handle", ducats=45),
        item("kamas_prime_blueprint", "/K/BP", tags=("blueprint", "prime", "weapon"), ducats=25),
        item("soma_prime_set", "/S/Set", tags=("weapon", "prime", "set")),
        item("soma_prime_barrel", "/S/Barrel", ducats=15),
        item("soma_prime_stock", "/S/Stock", ducats=15),
    ]})
    return c


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "t.sqlite3")


@pytest.fixture
async def http():
    c = HttpClient(max_rps=1000)
    yield c
    await c.aclose()


def test_candidate_sets_need_every_part(catalog, db):
    db.inventory_save([InvItem("/K/Blade", 4, None), InvItem("/K/Handle", 2, None), InvItem("/K/BP", 2, None),
                       InvItem("/S/Barrel", 1, None)], [], NOW)  # soma is missing its stock
    assert candidate_sets(catalog, db) == ["kamas_prime_set"]


def test_buildable_uses_real_quantities_and_compares_prices(catalog, db):
    db.inventory_save([InvItem("/K/Blade", 3, None), InvItem("/K/Handle", 5, None), InvItem("/K/BP", 5, None)], [], NOW)
    db.set_parts_save("kamas_prime_set", [("kamas_prime_blade", 2), ("kamas_prime_handle", 1), ("kamas_prime_blueprint", 1)])
    for slug, p in (("kamas_prime_set", 60), ("kamas_prime_blade", 10), ("kamas_prime_handle", 5), ("kamas_prime_blueprint", 8)):
        db.price_save(PriceSnapshot(slug, None, p, None, None, 0, NOW))
    (s,) = buildable_sets(catalog, db)
    assert s["slug"] == "kamas_prime_set"
    assert s["count"] == 1                     # only 3 blades, 2 per set
    assert s["set_price"] == 60
    assert s["parts_price"] == 2 * 10 + 5 + 8  # 33
    assert s["gain"] == 27 and s["better"] == "set"


@respx.mock
async def test_fetch_set_parts_with_quantity(catalog, db, http):
    respx.get(f"{API}/v2/item/kamas_prime_set").mock(return_value=httpx.Response(200, json={"data": {
        "setParts": ["id_kamas_prime_set", "id_kamas_prime_blade", "id_kamas_prime_handle", "id_kamas_prime_blueprint"]}}))
    respx.get(f"{API}/v2/item/kamas_prime_blade").mock(return_value=httpx.Response(200, json={"data": {"quantityInSet": 2}}))
    respx.get(f"{API}/v2/item/kamas_prime_handle").mock(return_value=httpx.Response(200, json={"data": {}}))
    respx.get(f"{API}/v2/item/kamas_prime_blueprint").mock(return_value=httpx.Response(200, json={"data": {"quantityInSet": 1}}))
    parts = await fetch_set_parts(http, catalog, db, "kamas_prime_set")
    assert sorted(parts) == [("kamas_prime_blade", 2), ("kamas_prime_blueprint", 1), ("kamas_prime_handle", 1)]
    assert sorted(db.set_parts_get("kamas_prime_set")) == sorted(parts)  # cached for good


def test_value_history(db):
    db.value_record(1000, NOW - timedelta(days=1, hours=1))
    db.value_record(1200, NOW + timedelta(minutes=10))
    db.value_record(1300, NOW + timedelta(minutes=40))  # same hour: replaces the previous point
    hist = db.value_history(NOW - timedelta(days=7))
    assert [v for _, v in hist] == [1000, 1300]
