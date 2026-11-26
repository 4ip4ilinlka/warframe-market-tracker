"""Constants shared across the app."""
from __future__ import annotations

import os
from pathlib import Path

PORT = 8777
HOST = "127.0.0.1"
USER_AGENT = "WFMarketTracker/1.0"

# The only external hosts the program may talk to.
ALLOWED_HOSTS = frozenset(
    {
        "api.warframe.market",
        "warframe.market",
        "api.warframe.com",
        "mobile.warframe.com",
    }
)

MARKET_API = "https://api.warframe.market"
MARKET_ASSETS = "https://warframe.market/static/assets/"
MARKET_SITE = "https://warframe.market"

PRICE_INTERVAL_S = 300
RIVEN_INTERVAL_S = 10
MARKET_MAX_RPS = 2.5
RIVEN_MAX_RPS = 0.4  # riven watch polling; auction search allows ~0.5 req/s
AUCTION_MAX_RPS = 0.5
INVENTORY_COOLDOWN_S = 120
PRICE_CACHE_FRESH_S = 30 * 60
INVENTORY_PRICE_FRESH_S = 3600  # inventory prices are refreshed after this long
HOT_PRICE_FRESH_S = 600  # items on sale and the most valuable ones: every 10 min
HOT_TOP_N = 50
AUTO_REFRESH_S = 900  # how often the background job looks for stale prices
STATS_MIN_PLAT = 5  # trade stats only matter for items worth at least this
PRICE_STALE_S = 15 * 60
CATALOG_TTL_S = 24 * 3600


def data_dir() -> Path:
    base = os.environ.get("WFMT_DATA_DIR") or os.path.join(
        os.environ.get("LOCALAPPDATA", str(Path.home())), "WFMarketTracker"
    )
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p
