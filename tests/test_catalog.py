import json
from pathlib import Path

import httpx
import pytest
import respx

from wfmt.catalog import Catalog
from wfmt.http import HttpClient

FX = Path(__file__).parent / "fixtures"
API = "https://api.warframe.market"


def fx(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def items_route(request):
    lang = request.headers.get("Language")
    return httpx.Response(200, json=fx(f"items_{lang}.json"))


def mock_api():
    respx.get(f"{API}/v2/items").mock(side_effect=items_route)
    respx.get(f"{API}/v2/riven/weapons").mock(return_value=httpx.Response(200, json=fx("riven_weapons_ru.json")))
    respx.get(f"{API}/v2/riven/attributes").mock(
        return_value=httpx.Response(200, json=fx("riven_attributes_ru.json"))
    )


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
async def http():
    c = HttpClient(max_rps=1000)
    yield c
    await c.aclose()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
async def cat(http, tmp_path, clock):
    with respx.mock:
        mock_api()
        c = Catalog(http, tmp_path, clock=clock)
        await c.load()
    return c


async def test_search_ru_case_insensitive(cat):
    slugs = [i.slug for i in cat.search("эш ПРАЙМ")]
    assert "ash_prime_systems_blueprint" in slugs
    assert "ash_prime_set" in slugs


async def test_search_en(cat):
    assert [i.slug for i in cat.search("continuity")] == ["primed_continuity"]


async def test_search_yo_e(cat):
    assert [i.slug for i in cat.search("зараженный алад")] == ["mutalist_alad_v_assassinate_key"]


async def test_search_prefix_first(cat):
    res = cat.search("ash prime")
    assert res[0].slug == "ash_prime_set"  # shortest name wins among prefix matches


async def test_by_game_ref(cat):
    item = cat.by_game_ref("/Lotus/Types/Recipes/WarframeRecipes/AshPrimeSystemsBlueprint")
    assert item.slug == "ash_prime_systems_blueprint"
    assert item.name_en == "Ash Prime Systems Blueprint"
    assert item.name_ru.startswith("Эш Прайм")
    assert cat.by_slug("primed_continuity").max_rank == 10


async def test_riven_data(cat):
    w = cat.riven_weapon_by_game_ref("/Lotus/Weapons/Grineer/Pistols/GrnTorpedoPistol/GrnTorpedoPistol")
    assert w.slug == "kulstar"
    assert w.disposition == 1.3
    assert cat.riven_attr_by_game_ref("WeaponPunctureDepthMod")["slug"] == "punch_through"


async def test_cache_used_within_24h(http, tmp_path, clock, cat):
    with respx.mock(assert_all_called=False) as router:
        c2 = Catalog(http, tmp_path, clock=clock)
        await c2.load()
        assert router.calls.call_count == 0
    assert c2.by_slug("arcane_energize") is not None


async def test_cache_refreshed_after_24h(http, tmp_path, clock, cat):
    clock.t += 25 * 3600
    with respx.mock as router:
        mock_api()
        c2 = Catalog(http, tmp_path, clock=clock)
        await c2.load()
        assert router.calls.call_count == 4


async def test_expired_cache_used_when_fetch_fails(http, tmp_path, clock, cat):
    clock.t += 25 * 3600
    with respx.mock:
        respx.get(f"{API}/v2/items").mock(return_value=httpx.Response(503))
        c2 = Catalog(http, tmp_path, clock=clock)
        with pytest.raises(Exception):
            await c2.load()
    assert c2.by_slug("arcane_energize") is not None  # stale cache indexed anyway
    assert c2.needs_refresh()


async def test_needs_refresh(cat, clock):
    assert not cat.needs_refresh()
    clock.t += 25 * 3600
    assert cat.needs_refresh()


async def test_relic_subtypes_kept(http, tmp_path, clock):
    ru = fx("items_ru.json")
    en = fx("items_en.json")
    for d in (ru, en):
        d["data"][0]["subtypes"] = ["intact", "radiant"]
    with respx.mock:
        respx.get(f"{API}/v2/items").mock(side_effect=lambda r: httpx.Response(200, json=ru if r.headers["Language"] == "ru" else en))
        respx.get(f"{API}/v2/riven/weapons").mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(f"{API}/v2/riven/attributes").mock(return_value=httpx.Response(200, json={"data": []}))
        c = Catalog(http, tmp_path, clock=clock)
        await c.load()
    assert c.items[0].subtypes == ["intact", "radiant"]


async def test_old_cache_format_refetched(http, tmp_path, clock, cat):
    import json as _json

    path = tmp_path / "catalog.json"
    data = _json.loads(path.read_text(encoding="utf-8"))
    data.pop("version", None)
    for i in data["items"]:
        i.pop("subtypes", None)
    path.write_text(_json.dumps(data), encoding="utf-8")
    with respx.mock as router:
        mock_api()
        c2 = Catalog(http, tmp_path, clock=clock)
        await c2.load()
        assert router.calls.call_count == 4


async def test_riven_weapon_has_thumb(cat):
    w = cat.riven_weapon("kulstar")
    assert w.thumb and w.thumb.endswith(".png")
