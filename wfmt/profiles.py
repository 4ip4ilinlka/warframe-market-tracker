"""Profiles: save the user's setup under a name and load it back (or move it as a file).

A profile holds the watch list, riven watches, price alerts, a few settings and the UI state
(tab, filters, sort), optionally an inventory snapshot. It never holds the market token or
any game session data.
"""
from __future__ import annotations

from datetime import datetime

from .db import Db
from .models import Alert, InvItem, InvRiven, RivenWatch

VERSION = 1
SETTING_KEYS = ("inventory_enabled",)


def snapshot(db: Db, ui: dict, include_inventory: bool) -> dict:
    alerts = db.alert_list()
    notify = {a.riven_watch_id for a in alerts if a.kind == "riven"}
    data: dict = {
        "version": VERSION,
        "watch": [{"slug": w.slug, "rank": w.rank} for w in db.watch_list()],
        "rivens": [
            {"weapon_slug": w.weapon_slug, "positive": w.positive, "negative": w.negative,
             "max_price": w.max_price, "notify": w.id in notify}
            for w in db.riven_watch_list()
        ],
        "alerts": [
            {"kind": a.kind, "slug": a.slug, "rank": a.rank, "threshold": a.threshold}
            for a in alerts if a.kind != "riven"
        ],
        "settings": {k: v for k in SETTING_KEYS if (v := db.setting_get(k)) is not None},
        "ui": dict(ui or {}),
    }
    if include_inventory:
        items, rivens, at = db.inventory_load()
        if at is not None:
            data["inventory"] = {
                "at": at.isoformat(),
                "items": [[i.game_ref, i.count, i.rank] for i in items],
                "rivens": [[r.weapon_game_ref, r.buffs, r.curses, r.rerolls, r.mastery] for r in rivens],
            }
    return data


def _check(data: dict) -> None:
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise ValueError("unsupported profile format")
    for key in ("watch", "rivens", "alerts"):
        if not isinstance(data.get(key, []), list):
            raise ValueError(f"bad profile field: {key}")


def apply_profile(db: Db, data: dict) -> dict:
    """Replace the current setup with the profile; returns the saved UI state."""
    _check(data)
    db.clear_setup()
    for w in data.get("watch", []):
        db.watch_add(str(w["slug"]), w.get("rank"))
    for r in data.get("rivens", []):
        wid = db.riven_watch_add(RivenWatch(None, str(r["weapon_slug"]), list(r.get("positive") or [])[:3],
                                            r.get("negative"), r.get("max_price")))
        if r.get("notify"):
            db.alert_add(Alert(None, "riven", None, None, None, wid))
    for a in data.get("alerts", []):
        db.alert_add(Alert(None, a["kind"], a.get("slug"), a.get("rank"), a.get("threshold"), None))
    for k, v in (data.get("settings") or {}).items():
        if k in SETTING_KEYS:
            db.setting_set(k, str(v))
    inv = data.get("inventory")
    if inv:
        items = [InvItem(g, int(c), r) for g, c, r in inv.get("items", [])]
        rivens = [InvRiven(w, [tuple(b) for b in bu], [tuple(c) for c in cu], rr, m)
                  for w, bu, cu, rr, m in inv.get("rivens", [])]
        db.inventory_save(items, rivens, datetime.fromisoformat(inv["at"]))
    return dict(data.get("ui") or {})
