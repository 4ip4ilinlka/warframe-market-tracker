from datetime import datetime, timedelta, timezone

import pytest

from wfmt.db import Db
from wfmt.models import Alert, InvItem, InvRiven, PriceSnapshot, RivenWatch

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "t.sqlite3")


def snap(at, sell=10, slug="ash_prime_systems", rank=None):
    return PriceSnapshot(slug, rank, sell, 8, 9, 20, at)


def test_watch_roundtrip(db):
    db.watch_add("ash_prime_systems", None)
    db.watch_add("primed_continuity", 10)
    db.watch_add("primed_continuity", 10)  # duplicate ignored
    assert {(w.slug, w.rank) for w in db.watch_list()} == {
        ("ash_prime_systems", None),
        ("primed_continuity", 10),
    }
    db.watch_remove("primed_continuity", 10)
    assert [(w.slug, w.rank) for w in db.watch_list()] == [("ash_prime_systems", None)]


def test_price_history_since(db):
    for h in range(5):
        db.price_save(snap(T0 + timedelta(hours=h), sell=10 + h))
    hist = db.price_history("ash_prime_systems", None, T0 + timedelta(hours=2))
    assert [s.sell_min for s in hist] == [12, 13, 14]
    assert db.price_latest("ash_prime_systems", None).sell_min == 14
    assert db.price_latest("ash_prime_systems", 0) is None


def test_price_previous(db):
    db.price_save(snap(T0, sell=10))
    db.price_save(snap(T0 + timedelta(minutes=5), sell=12))
    assert db.price_previous("ash_prime_systems", None).sell_min == 10


def test_inventory_roundtrip(db):
    items = [InvItem("/Lotus/A", 3, None), InvItem("/Lotus/B", 1, 10)]
    rivens = [InvRiven("/Lotus/W", [("crit", 0.5)], [("zoom", 0.1)], 4, 12)]
    db.inventory_save(items, rivens, T0)
    got_items, got_rivens, at = db.inventory_load()
    assert got_items == items
    assert got_rivens == rivens
    assert at == T0


def test_inventory_empty(db):
    assert db.inventory_load() == ([], [], None)


def test_riven_watch_and_seen_ids(db):
    wid = db.riven_watch_add(RivenWatch(None, "rubico", ["critical_chance"], None, 500))
    assert db.riven_watch_list()[0].positive == ["critical_chance"]
    db.riven_mark_seen(wid, ["a", "b"])
    db.riven_mark_seen(wid, ["b", "c"])
    assert db.riven_seen_ids(wid) == {"a", "b", "c"}
    db.riven_watch_remove(wid)
    assert db.riven_watch_list() == []
    assert db.riven_seen_ids(wid) == set()


def test_alerts(db):
    aid = db.alert_add(Alert(None, "price_below", "ash_prime_systems", None, 20, None))
    assert db.alert_list()[0].id == aid
    db.alert_remove(aid)
    assert db.alert_list() == []


def test_settings(db):
    assert db.setting_get("x", "d") == "d"
    db.setting_set("x", "1")
    assert db.setting_get("x") == "1"


def test_secret_stored_as_blob(db):
    db.secret_set("k", b"\x00\x01secret")
    assert db.secret_get("k") == b"\x00\x01secret"
    db.secret_delete("k")
    assert db.secret_get("k") is None


def test_watch_remove_deletes_its_alerts(db):
    db.watch_add("ash", None)
    db.alert_add(Alert(None, "price_below", "ash", None, 20, None))
    db.alert_add(Alert(None, "price_below", "other", None, 20, None))
    db.watch_remove("ash", None)
    assert [a.slug for a in db.alert_list()] == ["other"]


def test_riven_seen_pruned_after_two_days(db):
    wid = db.riven_watch_add(RivenWatch(None, "rubico"))
    db.riven_mark_seen(wid, ["old"], at=T0)
    db.riven_mark_seen(wid, ["__polled__"], at=T0)
    db.riven_mark_seen(wid, ["new"], at=T0 + timedelta(days=2, hours=1))
    db.riven_prune_seen(T0 + timedelta(days=2, hours=1), keep={"__polled__"})
    assert db.riven_seen_ids(wid) == {"new", "__polled__"}
