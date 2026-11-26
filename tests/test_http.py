import httpx
import pytest
import respx

from wfmt.http import ForbiddenHost, HttpClient, MarketError

API = "https://api.warframe.market/v2/items"


class FakeTime:
    """Fake monotonic clock; sleep() advances it instead of waiting."""

    def __init__(self):
        self.now = 1000.0
        self.request_times = []

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def ft():
    return FakeTime()


@pytest.fixture
async def client(ft):
    c = HttpClient(clock=ft.clock, sleep=ft.sleep)
    yield c
    await c.aclose()


@respx.mock(assert_all_called=False)
async def test_forbidden_host_rejected(client):
    with pytest.raises(ForbiddenHost):
        await client.get_json("https://evil.example/x")
    assert respx.calls.call_count == 0


@respx.mock
async def test_user_agent_is_neutral(client):
    route = respx.get(API).mock(return_value=httpx.Response(200, json={"data": []}))
    await client.get_json(API)
    assert route.calls.last.request.headers["User-Agent"] == "WFMarketTracker/1.0"


@respx.mock
async def test_rate_limit_spacing(client, ft):
    def record(request):
        ft.request_times.append(ft.now)
        return httpx.Response(200, json={})

    respx.get(API).mock(side_effect=record)
    for _ in range(5):
        await client.get_json(API)
    gaps = [b - a for a, b in zip(ft.request_times, ft.request_times[1:])]
    assert len(gaps) == 4
    from wfmt import config
    assert all(g >= 1 / config.MARKET_MAX_RPS - 1e-9 for g in gaps)


@respx.mock
async def test_429_retries_then_succeeds(client):
    route = respx.get(API).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    assert await client.get_json(API) == {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_429_three_times_raises(client):
    respx.get(API).mock(return_value=httpx.Response(429))
    with pytest.raises(MarketError) as e:
        await client.get_json(API)
    assert e.value.status == 429
    assert respx.calls.call_count == 4


@respx.mock
async def test_http_error_raises_market_error(client):
    respx.get(API).mock(return_value=httpx.Response(503))
    with pytest.raises(MarketError) as e:
        await client.get_json(API)
    assert e.value.status == 503


# --- final review fixes ---
import asyncio  # noqa: E402

API2 = "https://api.warframe.market/v2/orders/item/x/top"


@respx.mock
async def test_429_blocks_other_requests(client, ft):
    """A 429 on one request pauses every later market request (shared backoff)."""
    respx.post("https://api.warframe.market/v1/auth/signin").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "5"})
    )
    times = []

    def route_b(request):
        times.append(ft.now)
        return httpx.Response(200, json={})

    respx.get(API2).mock(side_effect=route_b)
    t429 = ft.now
    with pytest.raises(MarketError):
        await client.post_json("https://api.warframe.market/v1/auth/signin", {})
    await client.get_json(API2)
    assert times[0] >= t429 + 5


@respx.mock
async def test_retry_after_capped(client, ft):
    respx.get(API).mock(side_effect=[httpx.Response(429, headers={"Retry-After": "3600"}), httpx.Response(200, json={})])
    start = ft.now
    await client.get_json(API)
    assert ft.now - start <= 61


@respx.mock
async def test_post_not_retried_on_429(client):
    route = respx.post("https://api.warframe.market/v1/auth/signin").mock(return_value=httpx.Response(429))
    with pytest.raises(MarketError):
        await client.post_json("https://api.warframe.market/v1/auth/signin", {})
    assert route.call_count == 1


@respx.mock
async def test_game_host_not_retried(client):
    route = respx.get("https://api.warframe.com/api/inventory.php").mock(return_value=httpx.Response(429))
    with pytest.raises(MarketError):
        await client.get_json("https://api.warframe.com/api/inventory.php")
    assert route.call_count == 1


@respx.mock
async def test_cookies_not_stored_or_sent(client):
    respx.get(API).mock(return_value=httpx.Response(200, json={}, headers={"Set-Cookie": "JWT=secret; Path=/"}))
    route2 = respx.get(API2).mock(return_value=httpx.Response(200, json={}))
    await client.get_json(API)
    await client.get_json(API2)
    assert "cookie" not in route2.calls.last.request.headers


@respx.mock
async def test_error_detail_kept(client):
    respx.get(API).mock(return_value=httpx.Response(400, json={"error": {"inputs": {"rank": "app.field.invalid"}}}))
    with pytest.raises(MarketError) as e:
        await client.get_json(API)
    assert "rank" in e.value.detail


AUCTIONS = "https://api.warframe.market/v1/auctions/search"


@respx.mock
async def test_auction_429_does_not_block_other_requests(client, ft):
    respx.get(AUCTIONS).mock(return_value=httpx.Response(429, headers={"Retry-After": "30"}))
    times = []

    def other(request):
        times.append(ft.now)
        return httpx.Response(200, json={})

    respx.get(API2).mock(side_effect=other)
    with pytest.raises(MarketError):
        await client.get_json(AUCTIONS)       # gives up; its queue stays blocked for 30 s
    t1 = ft.now
    await client.get_json(API2)
    assert times[0] - t1 < 1                  # other market requests are not blocked


@respx.mock
async def test_auction_requests_are_spaced_wider(client, ft):
    times = []

    def rec(request):
        times.append(ft.now)
        return httpx.Response(200, json={})

    respx.get(AUCTIONS).mock(side_effect=rec)
    for _ in range(3):
        await client.get_json(AUCTIONS)
    from wfmt import config
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert all(g >= 1 / config.AUCTION_MAX_RPS - 1e-9 for g in gaps)
