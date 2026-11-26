"""warframe.market account: sign-in and the user's own orders.

API (checked 2026-11-25 against the community OpenAPI spec and live responses):
  POST /v1/auth/signin   headers {"Authorization": "JWT"}
       body {"auth_type": "header", "email", "password", "device_id"}
       -> token in response header "Authorization: JWT <token>"
  v2 requests: "Authorization: Bearer <token>"
  GET    /v2/me            -> {"data": {"ingameName", ...}}
  GET    /v2/orders/my     -> {"data": [Order]}
  POST   /v2/order         body {"itemId","type","platinum","quantity","rank"?,"visible"?} -> {"data": Order}
  PATCH  /v2/order/{id}    body {"platinum"?,"quantity"?,"visible"?,"rank"?} -> {"data": Order}
  DELETE /v2/order/{id}
Community reports say email/password sign-in may be blocked for third-party apps
(App Check); in that case AuthError(captcha=True) and the UI offers token entry.

The password is only sent to api.warframe.market and is never stored or logged.
The token is stored encrypted with DPAPI.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from . import config, dpapi
from .db import Db
from .http import HttpClient, MarketError
from .models import MyOrder

log = logging.getLogger(__name__)
TOKEN_KEY = "market_token"
V2_HEADERS = {"Platform": "pc", "Crossplay": "true", "Language": "en"}


class OrderRejected(Exception):
    """The market refused an order change (validation); retrying will not help."""


def _reason(detail: str) -> str:
    try:
        err = json.loads(detail).get("error")
    except (ValueError, AttributeError):
        return ""
    if isinstance(err, dict):
        parts = []
        for k, v in (err.get("inputs") or {}).items():
            parts.append(f"{k}: {v}")
        parts += [str(x) for x in err.get("request") or []]
        return "; ".join(parts)
    return str(err or "")


class AuthError(Exception):
    def __init__(self, message: str, captcha: bool = False):
        super().__init__(message)
        self.captcha = captcha


def _order(d: dict) -> MyOrder:
    return MyOrder(
        id=d["id"],
        item_id=d.get("itemId", ""),
        slug=None,
        kind=d.get("type", "sell"),
        platinum=int(d.get("platinum") or 0),
        quantity=int(d.get("quantity") or 0),
        rank=d.get("rank"),
        visible=bool(d.get("visible", True)),
    )


def _clean_token(token: str) -> str:
    t = token.strip()
    for prefix in ("JWT ", "Bearer ", "JWT=", "jwt="):
        if t.startswith(prefix):
            t = t[len(prefix) :].strip()
    return t


class Account:
    def __init__(self, http: HttpClient, db: Db):
        self.http = http
        self.db = db
        self._token: str | None = None
        self.name: str | None = None

    # --- token storage ---
    def _load_token(self) -> str | None:
        if self._token:
            return self._token
        blob = self.db.secret_get(TOKEN_KEY)
        if not blob:
            return None
        try:
            self._token = dpapi.unprotect(blob).decode()
        except OSError:
            log.warning("stored market token could not be decrypted; signing out")
            self.db.secret_delete(TOKEN_KEY)
            return None
        return self._token

    def _store_token(self, token: str) -> None:
        self.db.secret_set(TOKEN_KEY, dpapi.protect(token.encode()))
        self._token = token

    def is_signed_in(self) -> bool:
        return self._load_token() is not None

    def signout(self) -> None:
        self.db.secret_delete(TOKEN_KEY)
        self._token = None
        self.name = None

    def _auth(self) -> dict:
        token = self._load_token()
        if not token:
            raise AuthError("not signed in")
        return {**V2_HEADERS, "Authorization": f"Bearer {token}"}

    def _device_id(self) -> str:
        dev = self.db.setting_get("device_id")
        if not dev:
            dev = "d-" + uuid.uuid4().hex
            self.db.setting_set("device_id", dev)
        return dev

    # --- sign-in ---
    async def _me(self, headers: dict) -> str:
        data = await self.http.get_json(f"{config.MARKET_API}/v2/me", headers=headers)
        return (data.get("data") or {}).get("ingameName") or ""

    async def signin(self, email: str, password: str) -> str:
        try:
            _, headers = await self.http.post_json(
                f"{config.MARKET_API}/v1/auth/signin",
                {"auth_type": "header", "email": email, "password": password, "device_id": self._device_id()},
                headers={"Authorization": "JWT", "Content-Type": "application/json"},
            )
        except MarketError as e:
            if e.status is None:
                raise AuthError("Нет связи с маркетом (ошибка сети)") from None
            if e.status in (400, 401, 422):
                raise AuthError("wrong email or password") from None
            raise AuthError(f"sign-in blocked (HTTP {e.status})", captcha=True) from None
        finally:
            del password
        token = _clean_token(headers.get("Authorization", ""))
        if not token or token == "JWT":
            raise AuthError("no token in sign-in response", captcha=True)
        return await self.set_token(token)

    async def set_token(self, token: str) -> str:
        token = _clean_token(token)
        if not token:
            raise AuthError("empty token")
        try:
            name = await self._me({**V2_HEADERS, "Authorization": f"Bearer {token}"})
        except MarketError as e:
            raise AuthError(f"token rejected (HTTP {e.status})") from None
        self._store_token(token)
        self.name = name
        return name

    async def me(self) -> str:
        if self.name is None:
            try:
                self.name = await self._me(self._auth())
            except MarketError as e:
                if e.status == 401:
                    self.signout()
                    raise AuthError("session expired") from None
                raise
        return self.name

    # --- orders ---
    async def _call(self, coro):
        try:
            return await coro
        except MarketError as e:
            if e.status == 401:
                self.signout()
                raise AuthError("session expired") from None
            if e.status in (400, 404, 409, 422):
                raise OrderRejected(f"Маркет отклонил запрос: {_reason(e.detail) or e.status}") from None
            raise

    async def my_orders(self) -> list[MyOrder]:
        auth = self._auth()
        data = await self._call(self.http.get_json(f"{config.MARKET_API}/v2/orders/my", headers=auth))
        return [_order(o) for o in data.get("data") or []]

    async def create_order(
        self,
        item_id: str,
        kind: Literal["sell", "buy"],
        platinum: int,
        quantity: int,
        rank: int | None,
        *,
        visible: bool = True,
        subtype: str | None = None,
    ) -> MyOrder:
        auth = self._auth()
        body: dict = {"itemId": item_id, "type": kind, "platinum": int(platinum), "quantity": int(quantity)}
        if rank is not None:
            body["rank"] = int(rank)
        if subtype:
            body["subtype"] = subtype
        body["visible"] = bool(visible)
        data, _ = await self._call(self.http.post_json(f"{config.MARKET_API}/v2/order", body, headers=auth))
        return _order(data["data"])

    async def update_order(
        self, order_id: str, platinum: int | None = None, quantity: int | None = None, visible: bool | None = None
    ) -> MyOrder:
        auth = self._auth()
        body = {k: v for k, v in {"platinum": platinum, "quantity": quantity, "visible": visible}.items() if v is not None}
        data = await self._call(
            self.http.patch_json(f"{config.MARKET_API}/v2/order/{order_id}", body, headers=auth)
        )
        return _order(data["data"])

    async def delete_order(self, order_id: str) -> None:
        auth = self._auth()
        await self._call(self.http.delete(f"{config.MARKET_API}/v2/order/{order_id}", headers=auth))
