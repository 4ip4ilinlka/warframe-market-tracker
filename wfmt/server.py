"""Local web API (127.0.0.1 only) and static UI."""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .account import Account, AuthError, OrderRejected
from .catalog import Catalog
from .db import Db
from .game_memory import CredentialsNotFound, GameAccessDenied, GameNotRunning
from .http import HttpClient, MarketError
from .inventory import Cooldown, GameRequestFailed, InventoryDisabled, InventoryLoader
from .alerts import PRICE_KINDS
from .models import Alert, PriceSnapshot, RivenWatch
from .prices import default_subtype, fetch_details, fetch_price
from .profiles import _check as check_profile, apply_profile, snapshot
from .scheduler import Scheduler
from .sell import auto_targets, build_sell_list, fill_prices, select_targets
from .sets import buildable_sets, fill_sets
from .visual import category_of, part_of, rarity_of, relic_tier

log = logging.getLogger(__name__)
MEDIAN_TTL_S = 600
ORDERS_TTL_S = 60
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' https://warframe.market; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


def static_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "wfmt" / "static"


@dataclass
class AppState:
    http: HttpClient | None
    db: Db
    catalog: Catalog
    scheduler: Scheduler | None = None
    account: Account | None = None
    inventory: Any = None
    fill: dict = field(default_factory=lambda: {"running": False, "done": 0, "total": 0})
    medians: dict = field(default_factory=dict)
    medians_at: float = 0.0
    tasks: set = field(default_factory=set)
    fill_task: Any = None
    orders_cache: list | None = None
    orders_at: float = 0.0

    def spawn(self, coro):
        t = asyncio.create_task(coro)
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)
        return t


async def build_state() -> AppState:
    http = HttpClient()
    db = Db(config.data_dir() / "data.sqlite3")
    catalog = Catalog(http, config.data_dir())
    st = AppState(http=http, db=db, catalog=catalog)
    st.scheduler = Scheduler(http, db, catalog)
    st.account = Account(http, db)
    st.inventory = InventoryLoader(http, db)
    return st


def err(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status)


def _snap(s: PriceSnapshot | None) -> dict | None:
    if s is None:
        return None
    d = asdict(s)
    d["at"] = s.at.isoformat()
    return d


# --- request bodies ---
class WatchIn(BaseModel):
    slug: str
    rank: int | None = None


class RivenWatchIn(BaseModel):
    weapon_slug: str
    positive: list[str] = []
    negative: str | None = None
    max_price: int | None = None
    notify: bool = False


class EnableIn(BaseModel):
    enabled: bool


class SigninIn(BaseModel):
    email: str
    password: str


class TokenIn(BaseModel):
    token: str


class OrderIn(BaseModel):
    item_id: str
    kind: str = "sell"
    platinum: int
    quantity: int = 1
    rank: int | None = None
    visible: bool = True


class RefreshIn(BaseModel):
    subs: list[str] | None = None
    force: bool = False


class ProfileIn(BaseModel):
    name: str
    ui: dict = {}
    include_inventory: bool = False


class ProfileImport(BaseModel):
    name: str
    data: dict


class BulkItem(BaseModel):
    item_id: str
    platinum: int
    quantity: int = 1
    rank: int | None = None


class BulkIn(BaseModel):
    items: list[BulkItem]
    visible: bool = True


def clean_profile_name(name: str) -> str | None:
    name = " ".join(name.split())
    return name if 0 < len(name) <= 40 else None


class OrderPatch(BaseModel):
    platinum: int | None = None
    quantity: int | None = None
    visible: bool | None = None


class AlertIn(BaseModel):
    kind: str
    slug: str | None = None
    rank: int | None = None
    threshold: int | None = None
    riven_watch_id: int | None = None


def create_app(
    state: AppState | None = None,
    *,
    start_background: bool = True,
    allowed_hosts: set[str] | None = None,
) -> FastAPI:
    hosts = allowed_hosts or {f"127.0.0.1:{config.PORT}", f"localhost:{config.PORT}"}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        st = state or await build_state()
        app.state.s = st
        # Catalog loading happens in the scheduler (with retries), so the port binds at once.
        if start_background:
            if st.scheduler:
                st.scheduler.start()
            if st.db.inventory_load()[2] is not None:
                _start_fill(st)  # finish any price loading an earlier run left behind
            if st.http:
                st.spawn(_auto_refresh(st))
        yield
        if st.scheduler:
            await st.scheduler.stop()
        for t in list(st.tasks):
            t.cancel()
        if st.http:
            await st.http.aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.headers.get("host", "") not in hosts:
            return err(400, "bad host")
        # Other websites must not reach this API or even probe that it exists.
        if request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
            return err(403, "forbidden")
        is_api = request.url.path.startswith("/api/")
        needs_header = is_api or request.method not in ("GET", "HEAD")
        if needs_header and request.headers.get("x-wfmt") != "1":
            return err(403, "forbidden")
        st = getattr(request.app.state, "s", None)
        if is_api and st is not None and st.scheduler:
            st.scheduler.ui_seen()
        try:
            resp = await call_next(request)
        except AuthError as e:
            resp = err(401, str(e), captcha=e.captcha)
        except OrderRejected as e:
            resp = err(400, str(e))
        except MarketError as e:
            resp = err(502, "Маркет недоступен, попробуйте позже", status=e.status)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-cache"  # always revalidate after an update
        return resp

    def S(request: Request) -> AppState:
        return request.app.state.s

    async def _listings(st: AppState) -> dict[str, dict]:
        """My active sell orders grouped by item id (cached for a minute)."""
        if not st.account or not st.account.is_signed_in():
            return {}
        if st.orders_cache is None or time.monotonic() - st.orders_at > ORDERS_TTL_S:
            try:
                st.orders_cache = await st.account.my_orders()
            except Exception as e:
                log.info("orders unavailable: %s", type(e).__name__)
                return {}
            st.orders_at = time.monotonic()
        out: dict[str, dict] = {}
        for o in st.orders_cache:
            if o.kind != "sell":
                continue
            cur = out.setdefault(o.item_id, {"platinum": o.platinum, "quantity": 0, "visible": False, "orders": 0})
            cur["platinum"] = min(cur["platinum"], o.platinum)
            cur["quantity"] += o.quantity
            cur["visible"] = cur["visible"] or o.visible
            cur["orders"] += 1
        return out

    def _orders_changed(st: AppState) -> None:
        st.orders_cache = None

    # --- status / search ---
    @app.get("/api/status")
    async def status(request: Request):
        st = S(request)
        _, _, inv_at = st.db.inventory_load()
        signed = bool(st.account and st.account.is_signed_in())
        return {
            "catalog_loaded": bool(st.catalog.items),
            "scheduler": st.scheduler.status() if st.scheduler else None,
            "signed_in": signed,
            "account_name": st.account.name if st.account else None,
            "inventory_enabled": st.inventory.enabled() if st.inventory else False,
            "inventory_at": inv_at.isoformat() if inv_at else None,
            "inventory_retry_in": st.inventory.retry_in() if st.inventory else 0,
            "fill": st.fill,
            "active_profile": st.db.setting_get("active_profile"),
        }

    @app.get("/api/search")
    async def search(request: Request, q: str = ""):
        return [
            {"id": i.id, "slug": i.slug, "name": i.name_ru, "name_en": i.name_en, "tags": i.tags,
             "max_rank": i.max_rank, "thumb": i.thumb}
            for i in S(request).catalog.search(q)
        ]

    # --- watch list / prices ---
    @app.get("/api/prices")
    async def prices(request: Request):
        st = S(request)
        now = datetime.now(timezone.utc)
        listings = await _listings(st)
        out = []
        for w in st.db.watch_list():
            item = st.catalog.by_slug(w.slug)
            latest = st.db.price_latest(w.slug, w.rank)
            out.append(
                {
                    "category": category_of(item.tags) if item else "other",
                    "part": part_of(w.slug),
                    "rarity": rarity_of(item.tags) if item else None,
                    "tier": relic_tier(w.slug),
                    "ducats": item.ducats if item else None,
                    "vaulted": item.vaulted if item else False,
                    "listed": listings.get(item.id) if item else None,
                    "slug": w.slug,
                    "rank": w.rank,
                    "item_id": item.id if item else None,
                    "name": item.name_ru if item else w.slug,
                    "max_rank": item.max_rank if item else None,
                    "thumb": item.thumb if item else None,
                    "latest": _snap(latest),
                    "prev": _snap(st.db.price_previous(w.slug, w.rank)),
                    "history": [
                        {"at": s.at.isoformat(), "sell_min": s.sell_min, "median": s.median_48h}
                        for s in st.db.price_history(w.slug, w.rank, now - timedelta(hours=48))
                    ],
                    "stale": latest is None or (now - latest.at).total_seconds() > config.PRICE_STALE_S,
                }
            )
        return out

    @app.post("/api/watch")
    async def watch_add(request: Request, body: WatchIn):
        st = S(request)
        if not st.catalog.by_slug(body.slug):
            return err(404, "Предмет не найден")
        st.db.watch_add(body.slug, body.rank)
        if st.http:
            st.spawn(_fetch_one(st, body.slug, body.rank))
        return {"ok": True}

    async def _fetch_one(st: AppState, slug: str, rank: int | None):
        try:
            st.db.price_save(await fetch_price(st.http, slug, rank, subtype=default_subtype(st.catalog, slug)))
        except Exception as e:
            log.warning("price for new item %s failed: %s", slug, type(e).__name__)

    @app.delete("/api/watch")
    async def watch_remove(request: Request, slug: str, rank: int | None = None):
        S(request).db.watch_remove(slug, rank)
        return {"ok": True}

    @app.post("/api/prices/refresh")
    async def prices_refresh(request: Request):
        st = S(request)
        if st.scheduler:
            st.scheduler.refresh_prices_now()
        return {"ok": True}

    # --- rivens ---
    @app.get("/api/rivens/weapons")
    async def riven_weapons(request: Request):
        return sorted(
            [{"slug": w.slug, "name": w.name_ru, "group": w.group, "thumb": w.thumb} for w in S(request).catalog.riven_weapons()],
            key=lambda w: w["name"],
        )

    @app.get("/api/rivens/attributes")
    async def riven_attributes(request: Request):
        return S(request).catalog.riven_attributes()

    @app.get("/api/rivens/watch")
    async def riven_watch_list(request: Request):
        st = S(request)
        alerts = {a.riven_watch_id for a in st.db.alert_list() if a.kind == "riven"}
        out = []
        for w in st.db.riven_watch_list():
            weapon = st.catalog.riven_weapon(w.weapon_slug)
            cache = st.scheduler.riven_lots.get(w.id) if st.scheduler else None
            lots = []
            if cache:
                for l in cache["lots"]:
                    d = asdict(l)
                    d["new"] = l.id in cache["new"]
                    lots.append(d)
            out.append(
                {
                    **asdict(w),
                    "weapon_name": weapon.name_ru if weapon else w.weapon_slug,
                    "weapon_thumb": weapon.thumb if weapon else None,
                    "notify": w.id in alerts,
                    "lots": lots,
                    "updated_at": cache["at"].isoformat() if cache else None,
                }
            )
        return {"interval_s": st.scheduler.riven_interval_s() if st.scheduler else None, "watches": out}

    @app.post("/api/rivens/watch")
    async def riven_watch_add(request: Request, body: RivenWatchIn):
        st = S(request)
        if not st.catalog.riven_weapon(body.weapon_slug):
            return err(404, "Оружие не найдено")
        wid = st.db.riven_watch_add(
            RivenWatch(None, body.weapon_slug, body.positive[:3], body.negative, body.max_price)
        )
        if body.notify:
            st.db.alert_add(Alert(None, "riven", None, None, None, wid))
        return {"id": wid}

    @app.delete("/api/rivens/watch/{watch_id}")
    async def riven_watch_remove(request: Request, watch_id: int):
        st = S(request)
        st.db.riven_watch_remove(watch_id)
        if st.scheduler:
            st.scheduler.riven_lots.pop(watch_id, None)
        return {"ok": True}

    # --- inventory / sell ---
    @app.post("/api/inventory/enable")
    async def inventory_enable(request: Request, body: EnableIn):
        S(request).inventory.set_enabled(body.enabled)
        return {"enabled": body.enabled}

    async def _fill(st: AppState, max_age_s: float, targets=None, job: int = 0):
        def progress(done, total):
            st.fill.update(done=done, total=total)

        me = None
        if st.account and st.account.is_signed_in():
            try:
                me = await st.account.me()
            except Exception:
                me = None
        try:
            await fill_prices(st.catalog, st.http, st.db, progress=progress, medians=st.medians,
                              max_age_s=max_age_s, targets=targets, exclude_user=me)
            await fill_sets(st.catalog, st.http, st.db)
        except Exception as e:
            log.warning("price fill failed: %s", type(e).__name__)
        finally:
            if st.fill.get("job") == job:  # an interrupted job must not mark its successor as done
                st.fill["running"] = False

    def _start_fill(st: AppState, reset_medians: bool = False, max_age_s: float = config.INVENTORY_PRICE_FRESH_S,
                    targets=None, preempt: bool = False) -> None:
        if not st.http:
            return
        if st.fill["running"]:
            if not preempt:
                return
            if st.fill_task is not None:
                st.fill_task.cancel()  # a fresh inventory load beats background re-checks
        if reset_medians or time.monotonic() - st.medians_at > MEDIAN_TTL_S:
            st.medians.clear()
            st.medians_at = time.monotonic()
        job = st.fill.get("job", 0) + 1
        st.fill.update(running=True, done=0, total=0, job=job)  # set before the task runs: no double start
        st.fill_task = st.spawn(_fill(st, max_age_s, targets, job))

    @app.post("/api/inventory/load")
    async def inventory_load(request: Request):
        st = S(request)
        try:
            items, rivens = await st.inventory.fetch()
        except InventoryDisabled:
            return err(409, "Функция инвентаря выключена. Включите её в настройках вкладки.")
        except GameAccessDenied:
            return err(409, "Windows не дала прочитать игру: Warframe запущен от администратора. "
                            "Запустите игру обычным способом или программу тоже от администратора.")
        except GameNotRunning:
            return err(409, "Warframe не запущен. Запустите игру и войдите в аккаунт.")
        except CredentialsNotFound:
            return err(409, "Войдите в аккаунт в игре и повторите (данные сессии не найдены).")
        except Cooldown as e:
            return err(409, f"Повторите через {e.retry_in} с", retry_in=e.retry_in)
        except GameRequestFailed as e:
            wait = st.inventory.retry_in()
            if e.status is not None and e.status < 500:
                msg = f"Сервер игры не принял данные сессии: перезайдите в игру и повторите через {wait} с."
            else:
                msg = f"Сервер игры недоступен, повторите через {wait} с."
            return err(409, msg)
        _start_fill(st, reset_medians=True, preempt=True)
        return {"items": len(items), "rivens": len(rivens)}

    @app.post("/api/sell/prices")
    async def sell_prices(request: Request, body: RefreshIn | None = None):
        st = S(request)
        body = body or RefreshIn()
        subs = set(body.subs) if body.subs is not None else None
        max_age = 0 if body.force else config.PRICE_CACHE_FRESH_S
        targets = select_targets(st.catalog, st.db, subs=subs, max_age_s=max_age)
        if targets and not st.fill["running"]:
            _start_fill(st, targets=targets)
        return {"ok": True, "items": len(targets), "busy": st.fill["running"] and not targets}

    async def _auto_refresh(st: AppState):
        while True:
            await asyncio.sleep(config.AUTO_REFRESH_S)
            try:
                if st.fill["running"] or st.db.inventory_load()[2] is None:
                    continue
                listed = set((await _listings(st)).keys())
                targets = auto_targets(st.catalog, st.db, listed_ids=listed)
                if targets:
                    _start_fill(st, targets=targets)
            except Exception as e:
                log.warning("auto refresh failed: %s", type(e).__name__)

    @app.get("/api/sell")
    async def sell(request: Request):
        st = S(request)
        # Cache-only: prices and riven references are fetched by the background fill job.
        sl = await build_sell_list(st.catalog, st.http, st.db, median_cache=st.medians, fetch_medians=False)
        total_value = sum(r.total or 0 for r in sl.rows)
        now = datetime.now(timezone.utc)
        if sl.rows and not st.fill["running"]:
            st.db.value_record(total_value, now)  # one point per hour; partial loads are not recorded
        history = [[t.isoformat(), v] for t, v in st.db.value_history(now - timedelta(days=30))]
        day_ago = [v for t, v in st.db.value_history(now - timedelta(hours=26)) if t <= now - timedelta(hours=22)]
        listings = await _listings(st)
        summary = {"lots": sum(v["orders"] for v in listings.values()),
                   "platinum": sum(o.platinum * o.quantity for o in (st.orders_cache or []) if o.kind == "sell")
                   if listings else 0}
        rows = []
        for r in sl.rows:
            d = asdict(r)
            d["price_at"] = r.price_at.isoformat() if r.price_at else None
            d["listed"] = listings.get(r.item_id)
            rows.append(d)
        return {
            "rows": rows,
            "rivens": [asdict(r) for r in sl.rivens],
            "unmatched": sl.unmatched,
            "unmatched_groups": sl.unmatched_groups or {},
            "listings_summary": summary,
            "value": {"total": total_value, "history": history,
                      "delta_day": total_value - day_ago[-1] if day_ago else None},
            "inventory_at": sl.inventory_at.isoformat() if sl.inventory_at else None,
            "fill": st.fill,
        }

    # --- account ---
    @app.post("/api/account/signin")
    async def signin(request: Request, body: SigninIn):
        name = await S(request).account.signin(body.email, body.password)
        return {"name": name}

    @app.post("/api/account/token")
    async def set_token(request: Request, body: TokenIn):
        return {"name": await S(request).account.set_token(body.token)}

    @app.post("/api/account/signout")
    async def signout(request: Request):
        S(request).account.signout()
        return {"ok": True}

    @app.get("/api/account/me")
    async def me(request: Request):
        return {"name": await S(request).account.me()}

    def _order_dict(st: AppState, o) -> dict:
        d = asdict(o)
        item = st.catalog.by_id(o.item_id)
        d["slug"] = item.slug if item else None
        d["name"] = item.name_ru if item else o.item_id
        d["thumb"] = item.thumb if item else None
        d["part"] = part_of(item.slug) if item else None
        d["category"] = category_of(item.tags) if item else "other"
        d["rarity"] = rarity_of(item.tags) if item else None
        d["tier"] = relic_tier(item.slug) if item else None
        d["max_rank"] = item.max_rank if item else None
        snap = st.db.price_latest(item.slug, o.rank) if item else None
        d["market_min"] = snap.sell_min if snap else None
        return d

    @app.get("/api/account/orders")
    async def orders(request: Request):
        st = S(request)
        st.orders_cache = await st.account.my_orders()
        st.orders_at = time.monotonic()
        return [_order_dict(st, o) for o in st.orders_cache]

    @app.post("/api/account/orders")
    async def order_create(request: Request, body: OrderIn):
        st = S(request)
        if body.kind not in ("sell", "buy") or body.platinum < 1 or body.quantity < 1:
            return err(400, "Неверные параметры лота")
        item = st.catalog.by_id(body.item_id)
        subtype = item.subtypes[0] if item and item.subtypes else None
        o = await st.account.create_order(
            body.item_id, body.kind, body.platinum, body.quantity, body.rank, visible=body.visible, subtype=subtype
        )
        _orders_changed(st)
        return _order_dict(st, o)

    @app.patch("/api/account/orders/{order_id}")
    async def order_update(request: Request, order_id: str, body: OrderPatch):
        st = S(request)
        o = await st.account.update_order(order_id, body.platinum, body.quantity, body.visible)
        _orders_changed(st)
        return _order_dict(st, o)

    @app.delete("/api/account/orders/{order_id}")
    async def order_delete(request: Request, order_id: str):
        await S(request).account.delete_order(order_id)
        _orders_changed(S(request))
        return {"ok": True}

    # --- alerts ---
    @app.get("/api/alerts")
    async def alerts(request: Request):
        st = S(request)
        out = []
        for a in st.db.alert_list():
            if a.kind == "riven":
                continue
            item = st.catalog.by_slug(a.slug) if a.slug else None
            out.append({**asdict(a), "name": item.name_ru if item else a.slug,
                        "thumb": item.thumb if item else None, "part": part_of(a.slug) if a.slug else None,
                        "category": category_of(item.tags) if item else "other",
                        "rarity": rarity_of(item.tags) if item else None})
        return out

    @app.post("/api/alerts")
    async def alert_add(request: Request, body: AlertIn):
        if body.kind not in PRICE_KINDS or body.threshold is None or not body.slug:
            return err(400, "Неверное правило")
        aid = S(request).db.alert_add(Alert(None, body.kind, body.slug, body.rank, body.threshold, None))
        return {"id": aid}

    @app.delete("/api/alerts/{alert_id}")
    async def alert_remove(request: Request, alert_id: int):
        S(request).db.alert_remove(alert_id)
        return {"ok": True}

    @app.get("/api/sets")
    async def sets(request: Request):
        return {"sets": buildable_sets(S(request).catalog, S(request).db)}

    @app.get("/api/item/{slug}")
    async def item_details(request: Request, slug: str, rank: int | None = None):
        st = S(request)
        item = st.catalog.by_slug(slug)
        if item is None:
            return err(404, "Предмет не найден")
        details = await fetch_details(st.http, slug, rank, default_subtype(st.catalog, slug))
        listings = await _listings(st)
        snap = st.db.price_latest(slug, rank)
        return {
            "slug": slug, "item_id": item.id, "name": item.name_ru, "name_en": item.name_en,
            "thumb": item.thumb, "part": part_of(slug), "category": category_of(item.tags),
            "rarity": rarity_of(item.tags), "tier": relic_tier(slug), "max_rank": item.max_rank,
            "ducats": item.ducats, "vaulted": item.vaulted,
            "rank": rank, "subtype": default_subtype(st.catalog, slug),
            "listed": listings.get(item.id), "latest": _snap(snap), **details,
        }

    # --- profiles ---
    @app.get("/api/profiles")
    async def profiles(request: Request):
        st = S(request)
        return {"profiles": st.db.profile_list(), "active": st.db.setting_get("active_profile")}

    @app.post("/api/profiles")
    async def profile_save(request: Request, body: ProfileIn):
        st = S(request)
        name = clean_profile_name(body.name)
        if not name:
            return err(400, "Введите название профиля (до 40 символов)")
        st.db.profile_save(name, snapshot(st.db, body.ui, body.include_inventory))
        st.db.setting_set("active_profile", name)
        return {"ok": True, "name": name}

    @app.post("/api/profiles/import")
    async def profile_import(request: Request, body: ProfileImport):
        st = S(request)
        name = clean_profile_name(body.name)
        if not name:
            return err(400, "Введите название профиля (до 40 символов)")
        try:
            check_profile(body.data)
        except ValueError:
            return err(400, "Это не файл профиля WF Market Tracker или он повреждён")
        st.db.profile_save(name, body.data)
        return {"ok": True, "name": name}

    @app.post("/api/profiles/{name}/load")
    async def profile_load(request: Request, name: str):
        st = S(request)
        data = st.db.profile_get(name)
        if data is None:
            return err(404, "Профиль не найден")
        try:
            ui = apply_profile(st.db, data)
        except (ValueError, KeyError, TypeError):
            return err(400, "Профиль повреждён")
        st.db.setting_set("active_profile", name)
        if st.scheduler:
            st.scheduler.riven_lots.clear()
            st.scheduler.refresh_prices_now()
        return {"ok": True, "ui": ui, "inventory": "inventory" in data}

    @app.get("/api/profiles/{name}/export")
    async def profile_export(request: Request, name: str):
        data = S(request).db.profile_get(name)
        if data is None:
            return err(404, "Профиль не найден")
        from urllib.parse import quote
        return JSONResponse(data, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}.wfmt-profile.json"})

    @app.delete("/api/profiles/{name}")
    async def profile_delete(request: Request, name: str):
        st = S(request)
        st.db.profile_delete(name)
        if st.db.setting_get("active_profile") == name:
            st.db.setting_set("active_profile", "")
        return {"ok": True}

    # --- bulk listing (one order at a time, through the normal rate limit) ---
    @app.post("/api/account/orders/bulk")
    async def orders_bulk(request: Request, body: BulkIn):
        st = S(request)
        results = []
        for it in body.items[:100]:
            if it.platinum < 1 or it.quantity < 1:
                results.append({"item_id": it.item_id, "ok": False, "error": "Неверная цена или количество"})
                continue
            item = st.catalog.by_id(it.item_id)
            subtype = item.subtypes[0] if item and item.subtypes else None
            try:
                await st.account.create_order(it.item_id, "sell", it.platinum, it.quantity, it.rank,
                                              visible=body.visible, subtype=subtype)
                results.append({"item_id": it.item_id, "ok": True})
            except (OrderRejected, MarketError) as e:
                results.append({"item_id": it.item_id, "ok": False, "error": str(e)})
        _orders_changed(st)
        return {"results": results, "ok": sum(r["ok"] for r in results)}

    @app.post("/api/quit")
    async def quit_app(request: Request):
        server = getattr(request.app.state, "server", None)
        if server is not None:
            server.should_exit = True
        return {"ok": True}

    # --- static UI ---
    sd = static_dir()

    @app.get("/")
    async def index():
        return FileResponse(sd / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=sd), name="static")
    return app
