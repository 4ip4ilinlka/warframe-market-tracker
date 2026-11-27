from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from wfmt.catalog import Catalog
from wfmt.db import Db
from wfmt.game_memory import GameNotRunning
from wfmt.models import PriceSnapshot
from wfmt.server import AppState, create_app

BASE = "http://127.0.0.1:8777"
H = {"X-WFMT": "1"}


class FakeLoader:
    def __init__(self, exc=None):
        self.exc = exc
        self.on = True

    def enabled(self):
        return self.on

    def set_enabled(self, on):
        self.on = on

    def retry_in(self):
        return 0

    async def fetch(self):
        raise self.exc


@pytest.fixture
def state(tmp_path):
    db = Db(tmp_path / "t.sqlite3")
    cat = Catalog(None, tmp_path)
    cat._index(
        {
            "fetched_at": 0,
            "items": [
                {"id": "i1", "slug": "ash_sys", "game_ref": "/A", "name_ru": "Эш Прайм: Системы", "name_en": "Ash Prime Systems",
                 "tags": ["prime"], "max_rank": None, "thumb": None}
            ],
            "weapons": [],
            "attrs": [],
        }
    )
    st = AppState(http=None, db=db, catalog=cat)
    st.inventory = FakeLoader(GameNotRunning())
    return st


@pytest.fixture
def client(state):
    app = create_app(state, start_background=False)
    with TestClient(app, base_url=BASE, headers=H) as c:
        yield c


def test_mutation_requires_header(client):
    r = client.post("/api/watch", json={"slug": "ash_sys", "rank": None}, headers={"X-WFMT": ""})
    assert r.status_code == 403
    r = client.post("/api/watch", json={"slug": "ash_sys", "rank": None}, headers=H)
    assert r.status_code == 200


def test_bad_host_rejected(client):
    r = client.get("/api/status", headers={"Host": "evil.com"})
    assert r.status_code == 400
    assert client.get("/api/status").status_code == 200


def test_inventory_not_running_409_message(client):
    r = client.post("/api/inventory/load", headers=H)
    assert r.status_code == 409
    assert "Warframe не запущен" in r.json()["error"]


def test_prices_stale_flag(client, state):
    state.db.watch_add("ash_sys", None)
    now = datetime.now(timezone.utc)
    state.db.price_save(PriceSnapshot("ash_sys", None, 30, 20, 25, 4, now - timedelta(minutes=40)))
    state.db.price_save(PriceSnapshot("ash_sys", None, 28, 20, 25, 4, now - timedelta(minutes=20)))
    (row,) = client.get("/api/prices").json()
    assert row["name"] == "Эш Прайм: Системы"
    assert row["latest"]["sell_min"] == 28
    assert row["prev"]["sell_min"] == 30
    assert row["stale"] is True
    assert len(row["history"]) == 2


def test_unknown_item_rejected(client):
    r = client.post("/api/watch", json={"slug": "nope", "rank": None}, headers=H)
    assert r.status_code == 404


def test_search(client):
    r = client.get("/api/search", params={"q": "эш"})
    assert [i["slug"] for i in r.json()] == ["ash_sys"]


def test_index_served_without_external_resources(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<html" in r.text.lower()


def test_bind_address_is_loopback(monkeypatch, tmp_path):
    import wfmt.__main__ as main

    seen = {}
    monkeypatch.setenv("WFMT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main, "port_in_use", lambda: False)
    monkeypatch.setattr(main, "open_browser_later", lambda: None)
    class FakeServer:
        def __init__(self, cfg):
            seen["host"], seen["port"] = cfg.host, cfg.port

        def run(self):
            seen["ran"] = True

    monkeypatch.setattr(main.uvicorn, "Server", FakeServer)
    main.main()
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 8777
    assert seen["ran"]


def test_orders_without_signin_401(client, state):
    from wfmt.account import Account

    state.account = Account(None, state.db)
    r = client.get("/api/account/orders")
    assert r.status_code == 401
    assert r.json()["captcha"] is False


def test_csp_header(client):
    csp = client.get("/").headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "img-src 'self' https://warframe.market" in csp
    assert client.get("/").headers["referrer-policy"] == "no-referrer"


def test_api_get_requires_header(client):
    assert client.get("/api/status", headers={"X-WFMT": ""}).status_code == 403
    assert client.get("/").status_code == 200  # the page itself is a plain navigation


def test_cross_site_requests_blocked(client):
    r = client.get("/static/app.js", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403
    assert client.get("/", headers={"Sec-Fetch-Site": "none"}).status_code == 200


def test_inventory_game_rejected_409(client, state):
    from wfmt.inventory import GameRequestFailed

    state.inventory = FakeLoader(GameRequestFailed(403))
    r = client.post("/api/inventory/load")
    assert r.status_code == 409
    assert "перезайдите" in r.json()["error"]


def test_order_rejected_400(client, state):
    from wfmt.account import OrderRejected

    class Acc:
        def is_signed_in(self):
            return True

        async def create_order(self, *a, **kw):
            raise OrderRejected("Маркет отклонил запрос: rank: invalid")

    state.account = Acc()
    r = client.post("/api/account/orders", json={"item_id": "i1", "platinum": 5, "quantity": 1})
    assert r.status_code == 400
    assert "rank" in r.json()["error"]


def test_quit_sets_should_exit(client):
    class Srv:
        should_exit = False

    client.app.state.server = Srv()
    assert client.post("/api/quit").status_code == 200
    assert client.app.state.server.should_exit is True


def test_watch_add_fetches_new_item_and_fill_spawns_once(client, state):
    spawned = []

    class FakeHttp:
        async def aclose(self):
            pass

    state.http = FakeHttp()

    def spawn(coro):
        spawned.append(coro)
        coro.close()

    state.spawn = spawn
    from wfmt.models import InvItem

    state.db.inventory_save([InvItem("/A", 1, None)], [], datetime.now(timezone.utc))
    client.post("/api/watch", json={"slug": "ash_sys", "rank": None})
    assert len(spawned) == 1
    client.post("/api/sell/prices", json={"force": True})
    client.post("/api/sell/prices", json={"force": True})  # already running: no second job
    assert len(spawned) == 2


class OrdersAcc:
    name = "Tenno"

    def __init__(self, orders):
        self.orders = orders

    def is_signed_in(self):
        return True

    async def my_orders(self):
        return self.orders


def test_sell_rows_marked_listed(client, state):
    from wfmt.models import InvItem, MyOrder

    state.db.inventory_save([InvItem("/A", 3, None)], [], datetime.now(timezone.utc))
    state.account = OrdersAcc([MyOrder("o1", "i1", None, "sell", 41, 13, None, False)])
    (row,) = client.get("/api/sell").json()["rows"]
    assert row["listed"] == {"platinum": 41, "quantity": 13, "visible": False, "orders": 1}
    assert "unmatched_groups" in client.get("/api/sell").json()


def test_prices_rows_have_part_and_listing(client, state):
    from wfmt.models import MyOrder

    state.db.watch_add("ash_sys", None)
    state.account = OrdersAcc([MyOrder("o1", "i1", None, "sell", 20, 1, None, True)])
    (row,) = client.get("/api/prices").json()
    assert row["category"] == "prime"
    assert row["listed"]["platinum"] == 20


def test_access_denied_message(client, state):
    from wfmt.game_memory import GameAccessDenied

    state.inventory = FakeLoader(GameAccessDenied())
    r = client.post("/api/inventory/load")
    assert r.status_code == 409
    assert "администратор" in r.json()["error"]


def test_median_alert_kind_accepted(client, state):
    state.db.watch_add("ash_sys", None)
    r = client.post("/api/alerts", json={"kind": "median_below", "slug": "ash_sys", "threshold": 10})
    assert r.status_code == 200


def test_static_files_not_cached(client):
    assert client.get("/static/app.js").headers["cache-control"] == "no-cache"


def test_sell_summary_counts_all_my_orders(client, state):
    from wfmt.models import MyOrder

    state.account = OrdersAcc([MyOrder("o1", "zzz", None, "sell", 41, 13, None, False),
                               MyOrder("o2", "i1", None, "sell", 10, 2, None, True),
                               MyOrder("o3", "i1", None, "buy", 5, 1, None, True)])
    s = client.get("/api/sell").json()["listings_summary"]
    assert s == {"lots": 2, "platinum": 41 * 13 + 10 * 2}


def test_item_details_endpoint(client, state, monkeypatch):
    import wfmt.server as srv

    async def fake_details(http, slug, rank, subtype=None):
        return {"sellers": [{"name": "S", "status": "ingame", "unit": 10, "per_trade": 1, "quantity": 2, "reputation": 1}],
                "buyers": [], "h48": [], "d90": []}

    class FakeHttp:
        async def aclose(self):
            pass

    state.http = FakeHttp()
    monkeypatch.setattr(srv, "fetch_details", fake_details)
    d = client.get("/api/item/ash_sys").json()
    assert d["name"] == "Эш Прайм: Системы"
    assert d["sellers"][0]["unit"] == 10
    assert "listed" in d and "part" in d
    assert client.get("/api/item/nope").status_code == 404


def test_fill_resumes_on_start_when_inventory_present(state):
    from wfmt.models import InvItem

    class FakeHttp:
        async def aclose(self):
            pass

    state.http = FakeHttp()
    state.db.inventory_save([InvItem("/A", 1, None)], [], datetime.now(timezone.utc))
    spawned = []

    def spawn(coro):
        spawned.append(coro)
        coro.close()

    state.spawn = spawn
    app = create_app(state, start_background=True)
    with TestClient(app, base_url=BASE, headers=H):
        pass
    names = [c.__name__ for c in spawned]
    assert names.count("_fill") == 1 and names.count("_auto_refresh") == 1


def test_refresh_prices_by_subcategory(client, state):
    from wfmt.models import InvItem

    class FakeHttp:
        async def aclose(self):
            pass

    state.http = FakeHttp()
    state.db.inventory_save([InvItem("/A", 1, None)], [], datetime.now(timezone.utc))
    spawned = []

    def spawn(coro):
        spawned.append(coro)
        coro.close()

    state.spawn = spawn
    r = client.post("/api/sell/prices", json={"subs": ["mod:melee"], "force": True}).json()
    assert r["items"] == 0 and spawned == []
    r = client.post("/api/sell/prices", json={"subs": ["prime:other"], "force": True}).json()
    assert r["items"] == 1 and len(spawned) == 1


def test_inventory_load_interrupts_background_refresh(client, state):
    import asyncio

    class OkLoader(FakeLoader):
        async def fetch(self):
            return [], []

    class FakeHttp:
        async def aclose(self):
            pass

    class FakeTask:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    state.http = FakeHttp()
    state.inventory = OkLoader()
    old = FakeTask()
    state.fill.update(running=True)
    state.fill_task = old
    spawned = []

    def spawn(coro):
        spawned.append(coro)
        coro.close()
        return FakeTask()

    state.spawn = spawn
    assert client.post("/api/inventory/load").status_code == 200
    assert old.cancelled
    assert len(spawned) == 1  # a new price job for the freshly loaded inventory


def test_profiles_api_roundtrip(client, state):
    state.db.watch_add("ash_sys", None)
    r = client.post("/api/profiles", json={"name": "Основной", "ui": {"tab": "watch"}, "include_inventory": False})
    assert r.status_code == 200
    assert [p["name"] for p in client.get("/api/profiles").json()["profiles"]] == ["Основной"]
    state.db.watch_remove("ash_sys", None)
    r = client.post("/api/profiles/Основной/load").json()
    assert r["ui"] == {"tab": "watch"}
    assert [w.slug for w in state.db.watch_list()] == ["ash_sys"]
    assert client.get("/api/status").json()["active_profile"] == "Основной"
    exp = client.get("/api/profiles/Основной/export")
    assert exp.status_code == 200 and exp.json()["version"] == 1
    assert "attachment" in exp.headers["content-disposition"]
    assert client.delete("/api/profiles/Основной").status_code == 200
    assert client.get("/api/profiles").json()["profiles"] == []


def test_profile_import_validates(client):
    bad = client.post("/api/profiles/import", json={"name": "X", "data": {"version": 7}})
    assert bad.status_code == 400
    ok = client.post("/api/profiles/import", json={"name": "Друг", "data": {"version": 1, "watch": [], "rivens": [], "alerts": []}})
    assert ok.status_code == 200
    assert client.post("/api/profiles", json={"name": "  ", "ui": {}}).status_code == 400
    assert client.post("/api/profiles/нет/load").status_code == 404


def test_bulk_orders(client, state):
    from wfmt.account import OrderRejected
    from wfmt.models import MyOrder

    made = []

    class Acc:
        def is_signed_in(self):
            return True

        async def create_order(self, item_id, kind, platinum, quantity, rank, visible=True, subtype=None):
            if item_id == "bad":
                raise OrderRejected("Маркет отклонил запрос: rank")
            made.append((item_id, platinum, quantity, visible))
            return MyOrder("o" + item_id, item_id, None, kind, platinum, quantity, rank, visible)

    state.account = Acc()
    r = client.post("/api/account/orders/bulk", json={"visible": False, "items": [
        {"item_id": "i1", "platinum": 10, "quantity": 3, "rank": None},
        {"item_id": "bad", "platinum": 5, "quantity": 1, "rank": None}]}).json()
    assert made == [("i1", 10, 3, False)]
    assert [x["ok"] for x in r["results"]] == [True, False]
    assert "rank" in r["results"][1]["error"]


def test_sets_and_value_history_endpoints(client, state):
    from wfmt.models import InvItem, PriceSnapshot

    assert client.get("/api/sets").json() == {"sets": []}
    state.db.inventory_save([InvItem("/A", 2, None)], [], datetime.now(timezone.utc))
    state.db.price_save(PriceSnapshot("ash_sys", None, 10, None, None, 0, datetime.now(timezone.utc)))
    d = client.get("/api/sell").json()
    assert d["value"]["total"] == 20
    assert d["value"]["history"][-1][1] == 20
    row = d["rows"][0]
    assert "ducats" in row and "vaulted" in row


def test_primes_endpoint_with_ownership(client, state):
    from wfmt.models import InvItem, PriceSnapshot

    class FakePrimes:
        updated_at = 1_800_000_000.0
        error = None
        data = {"primes": [{"slug": "ash_sys", "name": "Эш", "name_en": "Ash", "thumb": None, "kind": "warframe",
                            "status": "active", "relics": ["axi_a1_relic"], "evergreen": False}],
                "varzia": {"sets": [], "relics": [], "evergreen_sets": [], "expiry": None, "next": None}}
        refreshed = 0

        async def refresh(self):
            self.refreshed += 1

    state.primes = FakePrimes()
    state.db.price_save(PriceSnapshot("ash_sys", None, 40, None, None, 0, datetime.now(timezone.utc)))
    d = client.get("/api/primes").json()
    (p,) = d["primes"]
    assert p["status"] == "active" and p["set_price"] == 40
    assert "owned_parts" in p and "total_parts" in p
    assert client.post("/api/primes/refresh").status_code == 200
    assert state.primes.refreshed == 1


def _eph_tracker(state, tmp_path):
    from wfmt.ephemeras import Ephemera, EphemeraTracker
    from wfmt.models import EphLot

    tr = EphemeraTracker(None, state.db, tmp_path, notifier=lambda n: None, clock=lambda: 1000.0)
    tr.ephemeras = [Ephemera("lich", "heat", "vengeful_flame", "Пламя Мщения", "Vengeful Flame Ephemera", None)]
    tr.weapons = {"lich": {"kuva_kohm": "Кува Ком"}, "sister": {}}
    state.db.eph_lot_save([EphLot("a1", "lich", "heat", "kuva_kohm", 35, 150, "seller1", "ingame", None, 990.0)])
    state.ephemeras = tr
    return tr


def test_ephemeras_endpoint_lists_summary_lots_and_watches(client, state, tmp_path):
    _eph_tracker(state, tmp_path)
    r = client.post("/api/ephemeras/watch", json={"kind": "lich", "element": "heat", "max_price": 200, "notify": True})
    assert r.status_code == 200
    d = client.get("/api/ephemeras").json()
    (s,) = d["summary"]
    assert (s["name"], s["count"], s["min_price"], s["watched"]) == ("Пламя Мщения", 1, 150, True)
    (lot,) = d["lots"]
    assert (lot["id"], lot["weapon_name"], lot["ephemera"], lot["url"]) == (
        "a1", "Кува Ком", "Пламя Мщения", "https://warframe.market/auction/a1")
    (w,) = d["watches"]
    assert (w["kind"], w["element"], w["max_price"], w["notify"], w["name"], w["matches"]) == ("lich", "heat", 200, True, "Пламя Мщения", 1)
    assert client.delete(f"/api/ephemeras/watch/{w['id']}").status_code == 200
    assert client.get("/api/ephemeras").json()["watches"] == []


def test_ephemera_watch_rejects_unknown(client, state, tmp_path):
    _eph_tracker(state, tmp_path)
    assert client.post("/api/ephemeras/watch", json={"kind": "coda", "element": "heat"}).status_code == 400


def test_ephemera_weapons(client, state, tmp_path):
    _eph_tracker(state, tmp_path)
    assert client.get("/api/ephemeras/weapons?kind=lich").json() == [{"slug": "kuva_kohm", "name": "Кува Ком"}]
