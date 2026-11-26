from datetime import datetime, timezone

import pytest

from wfmt.db import Db
from wfmt.models import Alert, InvItem, RivenWatch
from wfmt.profiles import apply_profile, snapshot

T0 = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "t.sqlite3")


def fill(db):
    db.watch_add("ash_prime_set", None)
    db.watch_add("primed_continuity", 10)
    wid = db.riven_watch_add(RivenWatch(None, "rubico", ["critical_chance"], "zoom", 500))
    db.alert_add(Alert(None, "riven", None, None, None, wid))
    db.alert_add(Alert(None, "price_below", "ash_prime_set", None, 40, None))
    db.setting_set("inventory_enabled", "1")
    db.inventory_save([InvItem("/A", 3, None)], [], T0)


def test_profile_crud(db):
    db.profile_save("Основной", {"x": 1})
    db.profile_save("Твинк", {"x": 2})
    db.profile_save("Основной", {"x": 3})  # overwrite
    names = [p["name"] for p in db.profile_list()]
    assert names == ["Основной", "Твинк"]
    assert db.profile_get("Основной")["x"] == 3
    db.profile_delete("Твинк")
    assert db.profile_get("Твинк") is None


def test_snapshot_contains_settings_but_never_secrets(db):
    fill(db)
    db.secret_set("market_token", b"secret-token-bytes")
    snap = snapshot(db, ui={"tab": "orders"}, include_inventory=False)
    assert snap["version"] == 1
    assert {(w["slug"], w["rank"]) for w in snap["watch"]} == {("ash_prime_set", None), ("primed_continuity", 10)}
    assert snap["rivens"] == [{"weapon_slug": "rubico", "positive": ["critical_chance"], "negative": "zoom",
                               "max_price": 500, "notify": True}]
    assert snap["alerts"] == [{"kind": "price_below", "slug": "ash_prime_set", "rank": None, "threshold": 40}]
    assert snap["settings"] == {"inventory_enabled": "1"}
    assert snap["ui"] == {"tab": "orders"}
    assert "inventory" not in snap
    assert "secret" not in str(snap) and "token" not in str(snap).lower()


def test_snapshot_with_inventory(db):
    fill(db)
    snap = snapshot(db, ui={}, include_inventory=True)
    assert snap["inventory"]["items"] == [["/A", 3, None]]


def test_apply_replaces_current_setup(db, tmp_path):
    fill(db)
    snap = snapshot(db, ui={"tab": "watch"}, include_inventory=True)
    other = Db(tmp_path / "other.sqlite3")
    other.watch_add("something_else", None)
    other.alert_add(Alert(None, "price_above", "something_else", None, 5, None))
    ui = apply_profile(other, snap)
    assert ui == {"tab": "watch"}
    assert {(w.slug, w.rank) for w in other.watch_list()} == {("ash_prime_set", None), ("primed_continuity", 10)}
    (rw,) = other.riven_watch_list()
    assert (rw.weapon_slug, rw.positive, rw.negative, rw.max_price) == ("rubico", ["critical_chance"], "zoom", 500)
    kinds = sorted(a.kind for a in other.alert_list())
    assert kinds == ["price_below", "riven"]
    assert other.setting_get("inventory_enabled") == "1"
    items, _, at = other.inventory_load()
    assert [i.game_ref for i in items] == ["/A"] and at is not None


def test_apply_without_inventory_keeps_current_inventory(db, tmp_path):
    fill(db)
    snap = snapshot(db, ui={}, include_inventory=False)
    other = Db(tmp_path / "other.sqlite3")
    other.inventory_save([InvItem("/KEEP", 1, None)], [], T0)
    apply_profile(other, snap)
    assert [i.game_ref for i in other.inventory_load()[0]] == ["/KEEP"]


def test_apply_rejects_unknown_format(db):
    with pytest.raises(ValueError):
        apply_profile(db, {"version": 99})
    with pytest.raises(ValueError):
        apply_profile(db, {"watch": "not a list", "version": 1})
