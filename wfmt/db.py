"""SQLite storage. Never stores game session data or passwords."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .models import Alert, InvItem, InvRiven, PriceSnapshot, RivenWatch, WatchEntry

SCHEMA = """
CREATE TABLE IF NOT EXISTS watch (
  slug TEXT NOT NULL, rank INTEGER NOT NULL DEFAULT -1,
  PRIMARY KEY (slug, rank));
CREATE TABLE IF NOT EXISTS price (
  slug TEXT NOT NULL, rank INTEGER NOT NULL DEFAULT -1, at TEXT NOT NULL,
  sell_min INTEGER, buy_max INTEGER, median REAL, volume INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS price_idx ON price(slug, rank, at);
CREATE TABLE IF NOT EXISTS riven_watch (
  id INTEGER PRIMARY KEY AUTOINCREMENT, weapon_slug TEXT NOT NULL,
  positive TEXT NOT NULL, negative TEXT, max_price INTEGER);
CREATE TABLE IF NOT EXISTS riven_seen (
  watch_id INTEGER NOT NULL, auction_id TEXT NOT NULL, seen_at TEXT,
  PRIMARY KEY (watch_id, auction_id));
CREATE TABLE IF NOT EXISTS inventory (
  id INTEGER PRIMARY KEY CHECK (id = 1), at TEXT NOT NULL,
  items TEXT NOT NULL, rivens TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alert (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, slug TEXT,
  rank INTEGER, threshold INTEGER, riven_watch_id INTEGER);
CREATE TABLE IF NOT EXISTS setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS secret (key TEXT PRIMARY KEY, value BLOB NOT NULL);
"""

_NONE_RANK = -1


def _r(rank: int | None) -> int:
    return _NONE_RANK if rank is None else rank


def _unr(rank: int) -> int | None:
    return None if rank == _NONE_RANK else rank


class Db:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(riven_seen)")}
            if "seen_at" not in cols:  # databases created by the first version
                self._conn.execute("ALTER TABLE riven_seen ADD COLUMN seen_at TEXT")
            self._conn.commit()

    def _exec(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur

    def _all(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- watch list ---
    def watch_add(self, slug: str, rank: int | None) -> None:
        self._exec("INSERT OR IGNORE INTO watch(slug, rank) VALUES (?, ?)", (slug, _r(rank)))

    def watch_remove(self, slug: str, rank: int | None) -> None:
        self._exec("DELETE FROM watch WHERE slug=? AND rank=?", (slug, _r(rank)))
        self._exec("DELETE FROM alert WHERE kind != 'riven' AND slug=? AND rank IS ?", (slug, rank))

    def watch_list(self) -> list[WatchEntry]:
        return [WatchEntry(s, _unr(r)) for s, r in self._all("SELECT slug, rank FROM watch ORDER BY rowid")]

    # --- prices ---
    def price_save(self, s: PriceSnapshot) -> None:
        self._exec(
            "INSERT INTO price(slug, rank, at, sell_min, buy_max, median, volume) VALUES (?,?,?,?,?,?,?)",
            (s.slug, _r(s.rank), s.at.isoformat(), s.sell_min, s.buy_max, s.median_48h, s.volume_48h),
        )

    @staticmethod
    def _snap(row: tuple) -> PriceSnapshot:
        slug, rank, at, sell, buy, med, vol = row
        return PriceSnapshot(slug, _unr(rank), sell, buy, med, vol, datetime.fromisoformat(at))

    _PCOLS = "slug, rank, at, sell_min, buy_max, median, volume"

    def price_latest(self, slug: str, rank: int | None) -> PriceSnapshot | None:
        rows = self._all(
            f"SELECT {self._PCOLS} FROM price WHERE slug=? AND rank=? ORDER BY at DESC LIMIT 1",
            (slug, _r(rank)),
        )
        return self._snap(rows[0]) if rows else None

    def price_previous(self, slug: str, rank: int | None) -> PriceSnapshot | None:
        rows = self._all(
            f"SELECT {self._PCOLS} FROM price WHERE slug=? AND rank=? ORDER BY at DESC LIMIT 1 OFFSET 1",
            (slug, _r(rank)),
        )
        return self._snap(rows[0]) if rows else None

    def price_history(self, slug: str, rank: int | None, since: datetime) -> list[PriceSnapshot]:
        rows = self._all(
            f"SELECT {self._PCOLS} FROM price WHERE slug=? AND rank=? AND at>=? ORDER BY at",
            (slug, _r(rank), since.isoformat()),
        )
        return [self._snap(r) for r in rows]

    # --- riven watches ---
    def riven_watch_add(self, w: RivenWatch) -> int:
        cur = self._exec(
            "INSERT INTO riven_watch(weapon_slug, positive, negative, max_price) VALUES (?,?,?,?)",
            (w.weapon_slug, json.dumps(w.positive), w.negative, w.max_price),
        )
        return int(cur.lastrowid)

    def riven_watch_remove(self, watch_id: int) -> None:
        self._exec("DELETE FROM riven_watch WHERE id=?", (watch_id,))
        self._exec("DELETE FROM riven_seen WHERE watch_id=?", (watch_id,))
        self._exec("DELETE FROM alert WHERE riven_watch_id=?", (watch_id,))

    def riven_watch_list(self) -> list[RivenWatch]:
        rows = self._all("SELECT id, weapon_slug, positive, negative, max_price FROM riven_watch ORDER BY id")
        return [RivenWatch(i, s, json.loads(p), n, m) for i, s, p, n, m in rows]

    def riven_seen_ids(self, watch_id: int) -> set[str]:
        return {r[0] for r in self._all("SELECT auction_id FROM riven_seen WHERE watch_id=?", (watch_id,))}

    def riven_mark_seen(self, watch_id: int, ids: Iterable[str], at: datetime | None = None) -> None:
        stamp = (at or datetime.now(timezone.utc)).isoformat()
        with self._lock:
            self._conn.executemany(
                "INSERT INTO riven_seen(watch_id, auction_id, seen_at) VALUES (?, ?, ?) "
                "ON CONFLICT(watch_id, auction_id) DO UPDATE SET seen_at=excluded.seen_at",
                [(watch_id, i, stamp) for i in ids],
            )
            self._conn.commit()

    def riven_prune_seen(self, now: datetime, keep: set[str], max_age: timedelta = timedelta(days=2)) -> None:
        """Forget lots not seen for max_age (they are gone from the market)."""
        cutoff = (now - max_age).isoformat()
        marks = list(keep) or [""]
        q = ",".join("?" * len(marks))
        self._exec(
            f"DELETE FROM riven_seen WHERE (seen_at IS NULL OR seen_at < ?) AND auction_id NOT IN ({q})",
            (cutoff, *marks),
        )

    # --- inventory (no session data) ---
    def inventory_save(self, items: list[InvItem], rivens: list[InvRiven], fetched_at: datetime) -> None:
        self._exec(
            "INSERT OR REPLACE INTO inventory(id, at, items, rivens) VALUES (1, ?, ?, ?)",
            (
                fetched_at.isoformat(),
                json.dumps([[i.game_ref, i.count, i.rank] for i in items]),
                json.dumps([[r.weapon_game_ref, r.buffs, r.curses, r.rerolls, r.mastery] for r in rivens]),
            ),
        )

    def inventory_load(self) -> tuple[list[InvItem], list[InvRiven], datetime | None]:
        rows = self._all("SELECT at, items, rivens FROM inventory WHERE id=1")
        if not rows:
            return [], [], None
        at, items, rivens = rows[0]
        return (
            [InvItem(g, c, r) for g, c, r in json.loads(items)],
            [
                InvRiven(w, [tuple(b) for b in bu], [tuple(c) for c in cu], rr, m)
                for w, bu, cu, rr, m in json.loads(rivens)
            ],
            datetime.fromisoformat(at),
        )

    # --- alerts ---
    def alert_add(self, a: Alert) -> int:
        cur = self._exec(
            "INSERT INTO alert(kind, slug, rank, threshold, riven_watch_id) VALUES (?,?,?,?,?)",
            (a.kind, a.slug, a.rank, a.threshold, a.riven_watch_id),
        )
        return int(cur.lastrowid)

    def alert_remove(self, alert_id: int) -> None:
        self._exec("DELETE FROM alert WHERE id=?", (alert_id,))

    def alert_list(self) -> list[Alert]:
        rows = self._all("SELECT id, kind, slug, rank, threshold, riven_watch_id FROM alert ORDER BY id")
        return [Alert(*r) for r in rows]

    # --- settings / secrets ---
    def setting_get(self, key: str, default: str | None = None) -> str | None:
        rows = self._all("SELECT value FROM setting WHERE key=?", (key,))
        return rows[0][0] if rows else default

    def setting_set(self, key: str, value: str) -> None:
        self._exec("INSERT OR REPLACE INTO setting(key, value) VALUES (?, ?)", (key, value))

    def secret_set(self, key: str, blob: bytes) -> None:
        self._exec("INSERT OR REPLACE INTO secret(key, value) VALUES (?, ?)", (key, sqlite3.Binary(blob)))

    def secret_get(self, key: str) -> bytes | None:
        rows = self._all("SELECT value FROM secret WHERE key=?", (key,))
        return bytes(rows[0][0]) if rows else None

    def secret_delete(self, key: str) -> None:
        self._exec("DELETE FROM secret WHERE key=?", (key,))
