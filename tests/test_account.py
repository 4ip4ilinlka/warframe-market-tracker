import json
import logging
import sys
from pathlib import Path

import httpx
import pytest
import respx

from wfmt.account import Account, AuthError
from wfmt.db import Db
from wfmt.dpapi import protect, unprotect
from wfmt.http import HttpClient

API = "https://api.warframe.market"
PASSWORD = "Sup3r-Secret-Pa55"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.payload-token.signature"

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")


@pytest.fixture
async def http():
    c = HttpClient(max_rps=1000)
    yield c
    await c.aclose()


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "t.sqlite3")


def me_route():
    return respx.get(f"{API}/v2/me").mock(
        return_value=httpx.Response(200, json={"data": {"ingameName": "Tenno42", "id": "u1"}})
    )


def signin_ok():
    return respx.post(f"{API}/v1/auth/signin").mock(
        return_value=httpx.Response(200, headers={"Authorization": f"JWT {TOKEN}"}, json={"payload": {"user": {}}})
    )


@windows_only
def test_protect_roundtrip():
    blob = protect(b"hello")
    assert blob != b"hello" and b"hello" not in blob
    assert unprotect(blob) == b"hello"


@windows_only
@respx.mock
async def test_signin_stores_encrypted_token(http, db):
    route = signin_ok()
    me_route()
    acc = Account(http, db)
    assert await acc.signin("me@example.com", PASSWORD) == "Tenno42"
    body = json.loads(route.calls.last.request.content)
    assert body["auth_type"] == "header" and body["email"] == "me@example.com"
    blob = db.secret_get("market_token")
    assert TOKEN.encode() not in blob
    assert acc.is_signed_in()


@windows_only
@respx.mock
async def test_password_never_persisted(http, db, caplog):
    caplog.set_level(logging.DEBUG)
    signin_ok()
    me_route()
    acc = Account(http, db)
    await acc.signin("me@example.com", PASSWORD)
    respx.post(f"{API}/v1/auth/signin").mock(return_value=httpx.Response(400, json={"error": {"password": ["x"]}}))
    with pytest.raises(AuthError):
        await acc.signin("me@example.com", PASSWORD)
    db.close()
    raw = Path(db.path).read_bytes()
    assert PASSWORD.encode() not in raw and TOKEN.encode() not in raw
    assert PASSWORD not in caplog.text and TOKEN not in caplog.text


@respx.mock
async def test_signin_bad_password_raises_auth_error(http, db):
    respx.post(f"{API}/v1/auth/signin").mock(
        return_value=httpx.Response(400, json={"error": {"password": ["app.account.password_invalid"]}})
    )
    with pytest.raises(AuthError) as e:
        await Account(http, db).signin("me@example.com", "wrong")
    assert e.value.captcha is False
    assert not Account(http, db).is_signed_in()


@respx.mock
async def test_signin_blocked_suggests_token(http, db):
    respx.post(f"{API}/v1/auth/signin").mock(return_value=httpx.Response(403, json={"error": "forbidden"}))
    with pytest.raises(AuthError) as e:
        await Account(http, db).signin("me@example.com", "pw")
    assert e.value.captcha is True


@windows_only
@respx.mock
async def test_set_token_validates_with_me(http, db):
    me_route()
    acc = Account(http, db)
    assert await acc.set_token("  JWT " + TOKEN + "  ") == "Tenno42"
    assert acc.is_signed_in()


@windows_only
@respx.mock
async def test_create_order_sends_auth_header(http, db):
    me_route()
    acc = Account(http, db)
    await acc.set_token(TOKEN)
    route = respx.post(f"{API}/v2/order").mock(
        return_value=httpx.Response(
            201,
            json={
                "data": {
                    "id": "o1",
                    "itemId": "i1",
                    "type": "sell",
                    "platinum": 25,
                    "quantity": 3,
                    "rank": None,
                    "visible": False,
                }
            },
        )
    )
    o = await acc.create_order("i1", "sell", 25, 3, None, visible=False)
    req = route.calls.last.request
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(req.content) == {"itemId": "i1", "type": "sell", "platinum": 25, "quantity": 3, "visible": False}
    assert (o.id, o.platinum, o.visible) == ("o1", 25, False)


@windows_only
@respx.mock
async def test_signout_deletes_token(http, db):
    me_route()
    acc = Account(http, db)
    await acc.set_token(TOKEN)
    acc.signout()
    assert db.secret_get("market_token") is None
    assert not acc.is_signed_in()


async def test_orders_require_signin(http, db):
    with pytest.raises(AuthError):
        await Account(http, db).my_orders()


@respx.mock
async def test_network_error_is_not_captcha(http, db):
    respx.post(f"{API}/v1/auth/signin").mock(side_effect=httpx.ConnectError("offline"))
    with pytest.raises(AuthError) as e:
        await Account(http, db).signin("me@example.com", "pw")
    assert e.value.captcha is False
    assert "сети" in str(e.value) or "network" in str(e.value)


@windows_only
@respx.mock
async def test_order_rejection_raises_order_rejected(http, db):
    from wfmt.account import OrderRejected

    me_route()
    acc = Account(http, db)
    await acc.set_token(TOKEN)
    respx.post(f"{API}/v2/order").mock(
        return_value=httpx.Response(400, json={"error": {"inputs": {"subtype": "app.field.required"}}})
    )
    with pytest.raises(OrderRejected) as e:
        await acc.create_order("i1", "sell", 10, 1, None)
    assert "subtype" in str(e.value)


@windows_only
@respx.mock
async def test_create_order_sends_subtype(http, db):
    me_route()
    acc = Account(http, db)
    await acc.set_token(TOKEN)
    route = respx.post(f"{API}/v2/order").mock(
        return_value=httpx.Response(201, json={"data": {"id": "o", "itemId": "i1", "type": "sell", "platinum": 5, "quantity": 1}})
    )
    await acc.create_order("i1", "sell", 5, 1, None, subtype="intact")
    assert json.loads(route.calls.last.request.content)["subtype"] == "intact"
