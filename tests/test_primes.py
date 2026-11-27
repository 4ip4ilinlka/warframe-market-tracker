import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from wfmt.catalog import Catalog
from wfmt.http import HttpClient
from wfmt.primes import DROPTABLES_URL, WORLDSTATE_URL, compute_primes, fetch_droptables, parse_dropping_relics, parse_relic_rewards, parse_varzia

FX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
MS = lambda dt: {"$date": {"$numberLong": str(int(dt.timestamp() * 1000))}}  # noqa: E731


def item(slug, ref, name_en, tags, vaulted=False):
    return {"id": "id_" + slug, "slug": slug, "game_ref": ref, "name_ru": name_en, "name_en": name_en,
            "tags": list(tags), "max_rank": None, "thumb": None, "vaulted": vaulted}


@pytest.fixture
def catalog(tmp_path):
    c = Catalog(None, tmp_path)
    c._index({"fetched_at": 0, "weapons": [], "attrs": [], "items": [
        item("ash_prime_set", "/Lotus/Powersuits/Ninja/AshPrime", "Ash Prime Set", ("warframe", "prime", "set")),
        item("ash_prime_systems_blueprint", "/A/Sys", "Ash Prime Systems Blueprint", ("component", "prime", "warframe", "blueprint")),
        item("nidus_prime_set", "/Lotus/Powersuits/Infestation/InfestationPrime", "Nidus Prime Set", ("warframe", "prime", "set")),
        item("soma_prime_set", "/Lotus/Weapons/Tenno/LongGuns/PrimeSoma/PrimeSomaRifle", "Soma Prime Set", ("weapon", "prime", "primary", "set")),
        item("soma_prime_barrel", "/S/Barrel", "Soma Prime Barrel", ("component", "prime", "weapon")),
        item("loki_prime_set", "/Lotus/Powersuits/Loki/LokiPrime", "Loki Prime Set", ("warframe", "prime", "set")),
        item("axi_a1_relic", "/Lotus/Types/Game/Projections/T4VoidProjectionA", "Axi A1 Relic", ("axi", "relic"), vaulted=False),
        item("lith_s16_relic", "/Lotus/Types/Game/Projections/T1VoidProjectionLavosPrimeD", "Lith S16 Relic", ("lith", "relic"), vaulted=True),
        item("lith_n1_relic", "/Lotus/Types/Game/Projections/T1VoidProjectionNidusSarynVaultABronze", "Lith N1 Relic", ("lith", "relic"), vaulted=True),
    ]})
    return c


def worldstate():
    return {"PrimeVaultTraders": [{
        "Activation": MS(datetime(2026, 10, 29, 18, tzinfo=timezone.utc)),
        "Expiry": MS(datetime(2026, 11, 26, 19, tzinfo=timezone.utc)),
        "Manifest": [{"ItemType": "/Lotus/StoreItems/Powersuits/Infestation/InfestationPrime", "PrimePrice": 3},
                     {"ItemType": "/Lotus/StoreItems/Types/Game/Projections/T1VoidProjectionNidusSarynVaultABronze", "RegularPrice": 1}],
        "EvergreenManifest": [{"ItemType": "/Lotus/StoreItems/Weapons/Tenno/LongGuns/PrimeSoma/PrimeSomaRifle"}],
        "ScheduleInfo": [
            {"Expiry": MS(datetime(2026, 11, 26, 19, tzinfo=timezone.utc)), "FeaturedItem": "/Lotus/Types/StoreItems/Packages/MegaPrimeVault/MPVNidusSarynPrimeDualPack"},
            {"Expiry": MS(datetime(2026, 12, 24, 19, tzinfo=timezone.utc)), "FeaturedItem": "/Lotus/Types/StoreItems/Packages/MegaPrimeVault/MPVLokiNovaPrimeDualPack"}],
    }]}


def test_parse_relic_rewards_intact_only():
    rewards = parse_relic_rewards((FX / "droptables_sample.html").read_text(encoding="utf-8"))
    assert rewards == {"axi_a1_relic": ["Ash Prime Systems Blueprint", "Forma Blueprint"], "lith_s16_relic": ["Soma Prime Barrel"]}


def test_parse_varzia(catalog):
    v = parse_varzia(worldstate(), catalog)
    assert v["sets"] == ["nidus_prime_set"]
    assert v["relics"] == ["lith_n1_relic"]
    assert v["evergreen_sets"] == ["soma_prime_set"]
    assert v["expiry"] == "2026-11-26T19:00:00+00:00"
    assert v["next"] == {"names": ["Loki", "Nova"], "from": "2026-11-26T19:00:00+00:00"}


def test_parse_dropping_relics_only_outside_relic_contents():
    page = (FX / "droptables_sample.html").read_text(encoding="utf-8")
    assert parse_dropping_relics(page) == {"axi_a1_relic"}


def test_market_unvaulted_flag_alone_does_not_make_active(catalog):
    # lith_s16 is unvaulted on the market in this variant, but it drops nowhere -> soma stays vaulted
    catalog.by_slug("lith_s16_relic").vaulted = False
    page = (FX / "droptables_sample.html").read_text(encoding="utf-8")
    data = compute_primes(catalog, parse_relic_rewards(page), parse_varzia(worldstate(), catalog), parse_dropping_relics(page))
    assert {p["slug"]: p["status"] for p in data["primes"]}["soma_prime_set"] == "vaulted"


def test_compute_primes_statuses(catalog):
    page = (FX / "droptables_sample.html").read_text(encoding="utf-8")
    rewards = parse_relic_rewards(page)
    data = compute_primes(catalog, rewards, parse_varzia(worldstate(), catalog), parse_dropping_relics(page))
    by = {p["slug"]: p for p in data["primes"]}
    assert by["ash_prime_set"]["status"] == "active"          # its part drops from an unvaulted relic
    assert by["ash_prime_set"]["relics"] == ["axi_a1_relic"]
    assert by["nidus_prime_set"]["status"] == "varzia"
    assert by["soma_prime_set"]["status"] == "vaulted"        # only in a vaulted relic (evergreen is noted separately)
    assert by["soma_prime_set"]["evergreen"] is True
    assert by["loki_prime_set"]["status"] == "vaulted"
    assert by["ash_prime_set"]["kind"] == "warframe" and by["soma_prime_set"]["kind"] == "weapon"


@respx.mock
async def test_fetch_droptables_follows_redirect_to_allowed_cdn():
    http = HttpClient(max_rps=1000)
    cdn = "https://warframe-web-assets.nyc3.cdn.digitaloceanspaces.com/uploads/cms/x.html"
    respx.get(DROPTABLES_URL).mock(return_value=httpx.Response(302, headers={"Location": cdn}))
    respx.get(cdn).mock(return_value=httpx.Response(200, text=(FX / "droptables_sample.html").read_text(encoding="utf-8")))
    html = await fetch_droptables(http)
    assert "Axi A1 Relic" in html
    await http.aclose()


@respx.mock
async def test_fetch_droptables_refuses_foreign_redirect():
    from wfmt.http import ForbiddenHost

    http = HttpClient(max_rps=1000)
    respx.get(DROPTABLES_URL).mock(return_value=httpx.Response(302, headers={"Location": "https://evil.example/x"}))
    with pytest.raises(ForbiddenHost):
        await fetch_droptables(http)
    await http.aclose()


def test_worldstate_url_is_official():
    assert WORLDSTATE_URL.startswith("https://api.warframe.com/")


@respx.mock
async def test_fill_prime_prices_for_warframes_and_varzia(catalog, tmp_path):
    from wfmt.db import Db
    from wfmt.primes import fill_prime_prices

    db = Db(tmp_path / "t.sqlite3")
    page = (FX / "droptables_sample.html").read_text(encoding="utf-8")
    data = compute_primes(catalog, parse_relic_rewards(page), parse_varzia(worldstate(), catalog), parse_dropping_relics(page))
    route = respx.get(url__regex=r".*/v2/orders/item/.*/top").mock(return_value=httpx.Response(200, json={"data": {
        "sell": [{"platinum": 50, "user": {"status": "ingame"}}], "buy": []}}))
    http = HttpClient(max_rps=1000)
    n = await fill_prime_prices(http, db, data)
    paths = sorted(c.request.url.path for c in route.calls)
    # all prime warframe sets (ash, nidus, loki); weapons only when sold by Varzia (soma is evergreen only)
    assert paths == ["/v2/orders/item/ash_prime_set/top", "/v2/orders/item/loki_prime_set/top", "/v2/orders/item/nidus_prime_set/top"]
    assert n == 3 and db.price_latest("nidus_prime_set", None).sell_min == 50
    assert await fill_prime_prices(http, db, data) == 0  # fresh prices are not fetched again
    await http.aclose()


def test_next_names_translated(catalog):
    from wfmt.primes import localize_next

    v = parse_varzia(worldstate(), catalog)
    assert localize_next(v, catalog)["next"]["names_ru"] == ["Loki", "Nova"]  # fixture has en names only
