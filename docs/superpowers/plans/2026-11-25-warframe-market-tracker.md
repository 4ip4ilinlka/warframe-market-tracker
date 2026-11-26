# Warframe Market Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Локальная программа (один `.exe`), которая отслеживает цены и моды разлома на warframe.market, загружает инвентарь Warframe, показывает «что продать», выставляет лоты и шлёт уведомления Windows.

**Architecture:** Python-сервер на `127.0.0.1:8777` (FastAPI) с фоновыми задачами (цены раз в 5 мин, моды разлома раз в 10 с), SQLite для состояния, все внешние запросы через один HTTP-клиент с белым списком хостов и лимитом скорости. Интерфейс — статическая страница (vanilla JS, без CDN), встроенная в `.exe` через PyInstaller.

**Tech Stack:** Python 3.12, FastAPI + uvicorn, httpx, sqlite3 (stdlib), ctypes (чтение памяти, DPAPI — без pywin32/pymem), windows-toasts (уведомления), pytest + respx (моки HTTP), PyInstaller (onefile).

**Spec:** `docs/design.md`

## Global Constraints

- Внешние хосты — только `api.warframe.market`, `warframe.market` (картинки), `api.warframe.com`, `mobile.warframe.com`. Любой другой хост — исключение `ForbiddenHost`.
- Сервер слушает только `127.0.0.1`, порт `8777`; при запуске открывается вкладка браузера.
- User-Agent: `WFMarketTracker/1.0` — никаких данных о системе в заголовках.
- Лимит к маркету: не более 2 запросов/с суммарно; на 429 — пауза (Retry-After или 5 с) и повтор до 3 раз.
- Цены — раз в 5 минут; моды разлома — 1 запрос на оружие раз в 10 с, запросы распределены во времени; если N оружий × (1/10 с) > 1.5 req/s — интервал = ceil(N/1.5) с, и API отдаёт фактический интервал в интерфейс.
- Память игры: `OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION)`, только `ReadProcessMemory`/`VirtualQueryEx`. Никакой записи, внедрения, хуков. Только по запросу пользователя. Не чаще 1 раза в 120 с.
- Функция инвентаря выключена по умолчанию (`settings.inventory_enabled = false`), включается в интерфейсе с предупреждением.
- accountId/nonce и пароль маркета — никогда не пишутся на диск и в логи. Токен маркета — только зашифрованный DPAPI (`CryptProtectData`) в SQLite.
- Лоты создаются/меняются/удаляются только по явному действию пользователя (POST от интерфейса); никаких циклов выставления.
- Интерфейс на русском, тёмная тема. Названия предметов — `Language: ru`, поиск по ru и en.
- Цена в «что продать» = медиана сделок за 48 ч; если сделок нет — минимальная цена продажи среди продавцов `ingame`/`online`. Показываются все продаваемые предметы, без порога.
- Учитываются только продавцы со статусом `ingame` или `online`.
- Все скрипты/стили/шрифты страницы — локальные файлы в `wfmt/static/`.

## Review Focus

1. **Игра не запущена / не выполнен вход** — понятное сообщение «Запустите Warframe и войдите в аккаунт», без падения; последний сохранённый инвентарь остаётся доступен. (Task 6: `test_no_process_returns_not_running`, `test_no_credentials_found`.)
2. **Маркет недоступен или отвечает 429/5xx** — программа показывает последние известные цены с временем обновления и пометкой «устарело», фоновая задача не умирает. (Task 1: `test_429_retries_then_succeeds`; Task 4: `test_refresh_keeps_old_snapshot_on_error`.)
3. **Предмет инвентаря без пары на маркете** (непродаваемый, неизвестный gameRef) — пропускается, в ответе есть счётчик `unmatched`. (Task 7: `test_unmatched_items_counted_not_listed`.)
4. **Много отслеживаемых оружий для модов разлома** — интервал растёт, лимит не превышается. (Task 5: `test_interval_scales_with_weapon_count`.)
5. **Неверный пароль / капча при входе на маркет** — понятная ошибка и предложение вставить токен вручную; пароль не сохраняется даже при ошибке. (Task 8: `test_signin_bad_password_raises_auth_error`, `test_password_never_persisted`.)

---

## File Structure

```
wfmt/
  __init__.py
  __main__.py        # точка входа: запуск uvicorn + открытие браузера
  config.py          # константы (порт, хосты, интервалы, пути данных)
  http.py            # HttpClient: белый список, лимит, 429, UA
  db.py              # SQLite: схема и функции доступа
  catalog.py         # справочник предметов маркета
  prices.py          # цены по отслеживаемым предметам
  rivens.py          # аукционы модов разлома, фильтры, новые лоты
  game_memory.py     # поиск accountId/nonce в памяти процесса (ctypes)
  inventory.py       # загрузка и разбор inventory.php
  sell.py            # сопоставление инвентаря с маркетом
  dpapi.py           # шифрование токена (ctypes CryptProtectData)
  account.py         # вход на маркет, свои лоты
  alerts.py          # правила уведомлений, проверка
  notify.py          # тосты Windows
  scheduler.py       # фоновые задачи
  server.py          # FastAPI-маршруты
  static/            # index.html, app.css, app.js
tests/               # по файлу на модуль
build.ps1, wfmt.spec, requirements.txt, requirements-dev.txt
```

Данные: `%LOCALAPPDATA%\WFMarketTracker\data.sqlite3`.

---

### Task 1: Каркас проекта и HTTP-клиент

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `wfmt/__init__.py`, `wfmt/config.py`, `wfmt/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Produces:
  - `config.ALLOWED_HOSTS: frozenset[str]`, `config.PORT = 8777`, `config.USER_AGENT = "WFMarketTracker/1.0"`, `config.PRICE_INTERVAL_S = 300`, `config.RIVEN_INTERVAL_S = 10`, `config.MARKET_MAX_RPS = 2.0`, `config.INVENTORY_COOLDOWN_S = 120`, `config.data_dir() -> Path`
  - `class ForbiddenHost(Exception)`, `class MarketError(Exception)` (атрибут `status: int | None`)
  - `class HttpClient`: `async get_json(url, *, headers=None, params=None) -> dict`, `async post_json(url, json, *, headers=None) -> tuple[dict, httpx.Headers]`, `async patch_json(url, json, *, headers=None) -> dict`, `async delete(url, *, headers=None) -> None`, `async aclose()`. Лимит применяется только к хостам `*.warframe.market`.

- [ ] **Step 1:** `git init`, создать `requirements*.txt` (fastapi, uvicorn, httpx, windows-toasts; dev: pytest, pytest-asyncio, respx, pyinstaller), `python -m venv .venv`, установить.
- [ ] **Step 2: Тесты** в `tests/test_http.py`:
  - `test_forbidden_host_rejected`: `get_json("https://evil.example/x")` → `ForbiddenHost`, запрос не отправлен (respx без маршрутов).
  - `test_user_agent_is_neutral`: заголовок `User-Agent == "WFMarketTracker/1.0"`.
  - `test_rate_limit_spacing`: 5 запросов к `api.warframe.market` идут с интервалом ≥ 0.5 с (подменить часы/sleep через внедряемый `clock`).
  - `test_429_retries_then_succeeds`: 429 (Retry-After: 1), затем 200 → результат 200, 2 вызова.
  - `test_429_three_times_raises`: 4×429 → `MarketError(status=429)`.
- [ ] **Step 3:** `pytest tests/test_http.py -v` → FAIL (нет модуля).
- [ ] **Step 4:** Реализовать `config.py`, `http.py` (httpx.AsyncClient, asyncio.Lock + последний момент запроса для лимита).
- [ ] **Step 5:** `pytest tests/test_http.py -v` → PASS.
- [ ] **Step 6:** Commit `feat: http client with host allowlist and rate limit`.

### Task 2: Хранилище SQLite

**Files:**
- Create: `wfmt/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `class Db(path: Path)` с методами:
  - `watch_add(slug: str, rank: int | None) -> None`, `watch_remove(slug, rank)`, `watch_list() -> list[WatchEntry]` (`WatchEntry(slug, rank)`, dataclass)
  - `price_save(snap: PriceSnapshot)`, `price_latest(slug, rank) -> PriceSnapshot | None`, `price_history(slug, rank, since: datetime) -> list[PriceSnapshot]`
  - `riven_watch_add(w: RivenWatch) -> int`, `riven_watch_remove(id)`, `riven_watch_list() -> list[RivenWatch]`
  - `riven_seen_ids(watch_id) -> set[str]`, `riven_mark_seen(watch_id, ids: Iterable[str])`
  - `inventory_save(items: list[InvItem], rivens: list[InvRiven], fetched_at: datetime)`, `inventory_load() -> tuple[list[InvItem], list[InvRiven], datetime | None]`
  - `alert_add(a: Alert) -> int`, `alert_remove(id)`, `alert_list() -> list[Alert]`
  - `setting_get(key, default=None) -> str | None`, `setting_set(key, value: str)`, `secret_set(key, blob: bytes)`, `secret_get(key) -> bytes | None`, `secret_delete(key)`
  - Модели данных (dataclasses) в `wfmt/models.py`: `PriceSnapshot(slug, rank, sell_min, buy_max, median_48h, volume_48h, at: datetime)`, `RivenWatch(id, weapon_slug, positive: list[str], negative: str | None, max_price: int | None)`, `RivenLot(id, weapon_slug, name, price, attributes: list[RivenAttr], mastery, rerolls, polarity, seller, seller_status, url)`, `RivenAttr(url_name, value: float, positive: bool)`, `InvItem(game_ref, count, rank: int | None)`, `InvRiven(weapon_game_ref, buffs: list[tuple[str, float]], curses: list[tuple[str, float]], rerolls, mastery)`, `Alert(id, kind: Literal["price_below","price_above","riven"], slug: str | None, rank: int | None, threshold: int | None, riven_watch_id: int | None)`
- Create: `wfmt/models.py`

- [ ] **Step 1: Тесты:** `test_watch_roundtrip`, `test_price_history_since`, `test_inventory_roundtrip`, `test_riven_seen_ids`, `test_secret_stored_as_blob` (в БД лежат ровно переданные байты), на `tmp_path`.
- [ ] **Step 2:** Запуск → FAIL.
- [ ] **Step 3:** Реализовать `models.py`, `db.py` (sqlite3, `check_same_thread=False`, блокировка `threading.Lock`, схема создаётся при открытии).
- [ ] **Step 4:** Запуск → PASS.
- [ ] **Step 5:** Commit `feat: sqlite storage`.

### Task 3: Справочник предметов

**Files:**
- Create: `wfmt/catalog.py`
- Test: `tests/test_catalog.py`, фикстура `tests/fixtures/items_ru.json`, `items_en.json` (по 5 предметов, взять фрагмент реального ответа `/v2/items`)

**Interfaces:**
- Consumes: `HttpClient.get_json`, `Db.setting_get/set`
- Produces: `class Catalog`: `async load(force=False)` (кэш в файле `data_dir()/items.json`, обновление раз в 24 ч), `search(q: str, limit=20) -> list[CatalogItem]`, `by_slug(slug) -> CatalogItem | None`, `by_game_ref(ref) -> CatalogItem | None`, `riven_weapons() -> list[RivenWeapon]`, `riven_weapon_by_game_ref(ref) -> RivenWeapon | None`.
  `CatalogItem(id, slug, game_ref, name_ru, name_en, tags: list[str], max_rank: int | None, thumb: str | None)`; `RivenWeapon(slug, game_ref, name_ru, group, disposition)` — в `models.py`.
  Источники: `GET /v2/items` с `Language: ru` и `Language: en`; `GET /v2/riven/weapons` с `Language: ru`. Ответы декодировать как UTF-8 (в PowerShell видно кракозябры — проверить, что httpx отдаёт нормальный русский).

- [ ] **Step 1: Тесты:** `test_search_ru_case_insensitive` («аш прайм» находит Ash Prime по ru-имени), `test_search_en`, `test_search_yo_e` («ё» = «е»), `test_by_game_ref`, `test_cache_used_within_24h` (второй `load()` без HTTP).
- [ ] **Step 2:** FAIL → **Step 3:** реализовать → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: item catalog`.

### Task 4: Цены отслеживаемых предметов

**Files:**
- Create: `wfmt/prices.py`
- Test: `tests/test_prices.py` (фикстуры: реальные фрагменты `/v2/orders/item/{slug}/top` и `/v1/items/{slug}/statistics`)

**Interfaces:**
- Consumes: `HttpClient`, `Db.price_save/price_latest`, `PriceSnapshot`
- Produces: `async fetch_price(http, slug, rank: int | None) -> PriceSnapshot`; `async refresh_all(http, db) -> list[PriceSnapshot]`; `effective_price(snap: PriceSnapshot) -> int | None` (медиана 48 ч, иначе sell_min).
  `top`: учитывать только `user.status in {"ingame","online"}`; при `rank` — фильтр `order.rank == rank` (для `rank=None` — все). Статистика: `payload.statistics_closed["48hours"]`, фильтр по `mod_rank` при наличии; медиана — медиана поля `median` взвешенно по `volume` (простое решение: медиана списка цен, где каждая запись повторена `volume` раз); `volume_48h` — сумма `volume`.

- [ ] **Step 1: Тесты:** `test_sell_min_ignores_offline`, `test_rank_filter`, `test_median_weighted_by_volume`, `test_effective_price_fallback_to_sell_min`, `test_refresh_keeps_old_snapshot_on_error` (MarketError на одном предмете → остальные сохранены, у упавшего остаётся прошлый снимок).
- [ ] **Step 2:** FAIL → **Step 3:** реализовать → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: price fetching`.

### Task 5: Моды разлома

**Files:**
- Create: `wfmt/rivens.py`
- Test: `tests/test_rivens.py`

**Interfaces:**
- Consumes: `HttpClient`, `Db.riven_*`, `RivenWatch`, `RivenLot`
- Produces: `async search_lots(http, watch: RivenWatch) -> list[RivenLot]` (только buyout, продавец `ingame`/`online`, по цене возрастания, ≤ 30); `matches(lot, watch) -> bool`; `new_lots(db, watch, lots) -> list[RivenLot]`; `riven_interval(n_weapons: int) -> float`; `async weapon_median(http, weapon_slug) -> int | None` (медиана buyout текущих лотов — ориентир для Task 7); `RIVEN_ATTRS: dict[str, str]` (url_name → русское название, из `GET /v2/riven/attributes` или `/v1/riven/attributes` с `Language: ru`).

- [ ] **Step 1: Найти рабочий поиск.** `GET /v1/auctions/search?type=riven&weapon_url_name=…` сейчас возвращает `{"auctions": []}` даже для оружия с лотами. Открыть warframe.market в браузере, поиск модов разлома, посмотреть сетевые запросы (DevTools / встроенный браузер `read_network_requests`). Зафиксировать URL, параметры и заголовки в docstring `search_lots`, сохранить фрагмент ответа в `tests/fixtures/riven_search.json`. Если рабочего поиска нет — запасной путь из спецификации: опрашивать ленту `GET /v1/auctions` (раз в 10 с), копить в таблице `riven_feed` (добавить в `db.py`) и фильтровать локально по `item.weapon_url_name`.
- [ ] **Step 2: Тесты:** `test_matches_positive_attrs` (все из `watch.positive` есть среди positive), `test_matches_negative`, `test_matches_max_price`, `test_only_buyout_and_online`, `test_new_lots_only_unseen`, `test_interval_scales_with_weapon_count` (`riven_interval(1)==10`, `riven_interval(15)==10`, `riven_interval(30)==20`).
- [ ] **Step 3:** FAIL → **Step 4:** реализовать → **Step 5:** PASS.
- [ ] **Step 6:** Commit `feat: riven auctions`.

### Task 6: Инвентарь из игры

**Files:**
- Create: `wfmt/game_memory.py`, `wfmt/inventory.py`
- Test: `tests/test_game_memory.py`, `tests/test_inventory.py` (фикстура `tests/fixtures/inventory_sample.json` — выдуманный, но той же структуры)

**Interfaces:**
- Produces:
  - `class GameNotRunning(Exception)`, `class CredentialsNotFound(Exception)`, `class Cooldown(Exception)` (атрибут `retry_in: int`)
  - `find_pid(name="Warframe.x64.exe") -> int | None`
  - `find_credentials(pid) -> tuple[str, str]` (accountId, nonce)
  - `scan_buffer(buf: bytes) -> tuple[str, str] | None` — чистая функция поиска, regex `rb"accountId=([0-9a-f]{24})&nonce=(\d+)"`, берётся последнее совпадение.
  - `async fetch_inventory(http, db, *, now=time.monotonic) -> tuple[list[InvItem], list[InvRiven]]` — проверяет `settings.inventory_enabled`, кулдаун 120 с, pid, credentials; `GET https://api.warframe.com/api/inventory.php?accountId=…&nonce=…` (при 4xx/сетевой ошибке — повтор на `mobile.warframe.com`); сохраняет результат в `Db.inventory_save`; credentials — локальные переменные, не логируются.
  - `parse_inventory(data: dict) -> tuple[list[InvItem], list[InvRiven]]`: `MiscItems`, `Recipes`, `RawUpgrades` (ранг 0), `Upgrades` (ранг из `UpgradeFingerprint.lvl`; если `ItemType` содержит `/Randomized/` → `InvRiven` из `compat`, `buffs`, `curses`, `rerolls`), `FusionTreasures`, `Arcanes`… — суммировать `ItemCount` по `(game_ref, rank)`.
- `find_credentials`: `OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION)`, обход `VirtualQueryEx` по регионам `MEM_COMMIT` с защитой `PAGE_READWRITE`, чтение кусками по 4 МБ с перекрытием 64 байта, `scan_buffer`; `CloseHandle` в `finally`.

- [ ] **Step 1: Тесты:** `test_scan_buffer_finds_credentials`, `test_scan_buffer_last_match_wins`, `test_scan_buffer_none`, `test_no_process_returns_not_running` (подменить `find_pid` → None → `GameNotRunning`), `test_no_credentials_found`, `test_cooldown_enforced` (второй вызов через 30 с → `Cooldown(retry_in=90)`), `test_disabled_by_default` (без настройки → `PermissionError`), `test_parse_inventory_counts`, `test_parse_riven_fingerprint`, `test_open_process_access_mask` (константа доступа == `0x0010 | 0x1000`).
- [ ] **Step 2:** FAIL → **Step 3:** реализовать → **Step 4:** PASS.
- [ ] **Step 5: Ручная проверка на живой игре** (нужен пользователь: запустить Warframe и войти): `python -c "from wfmt.game_memory import *; print(find_credentials(find_pid()) is not None)"` → `True` (сами значения не печатать). Затем загрузить инвентарь через API и проверить, что `len(items) > 0`.
- [ ] **Step 6:** Commit `feat: read-only game inventory`.

### Task 7: «Что продать»

**Files:**
- Create: `wfmt/sell.py`
- Test: `tests/test_sell.py`

**Interfaces:**
- Consumes: `Catalog.by_game_ref`, `Catalog.riven_weapon_by_game_ref`, `fetch_price`, `effective_price`, `weapon_median`, `Db.inventory_load`, `Db.price_latest`
- Produces: `async build_sell_list(catalog, http, db) -> SellList`; `SellList(rows: list[SellRow], rivens: list[SellRiven], unmatched: int, inventory_at: datetime | None)`; `SellRow(slug, name, tags, count, rank, unit_price: int | None, total: int | None, price_at)`; `SellRiven(weapon_slug, weapon_name, buffs, curses, rerolls, reference_price: int | None)`.
  Ранги: инвентарный `rank == max_rank` → цена максимального ранга; иначе ранг 0 (для предметов без `max_rank` — `None`). Цены берутся из `price_latest`, если моложе 30 минут, иначе запрашиваются (через общий лимит). Сортировка по `total` убыв., `None` в конце. Предметы с `tradable=false` или без пары — в `unmatched`.
  Перевод значений buffs (0..1) в проценты — не делать: показывать название характеристики и знак; ориентир цены = `weapon_median`.

- [ ] **Step 1: Тесты:** `test_sorted_by_total`, `test_max_rank_mod_uses_max_rank_price`, `test_unmatched_items_counted_not_listed`, `test_cached_price_reused` (свежий снимок → без HTTP).
- [ ] **Step 2:** FAIL → **Step 3:** реализовать → **Step 4:** PASS.
- [ ] **Step 5: Сверка на живых данных:** для 5 случайных прайм-частей из реального инвентаря убедиться, что `by_game_ref` находит предмет. Если ссылки у деталей/чертежей не совпадают (например, маркет хранит `…Blueprint`, а инвентарь — `…Component`), добавить в `sell.py` таблицу нормализации и тест на неё.
- [ ] **Step 6:** Commit `feat: sell list`.

### Task 8: Аккаунт маркета и свои лоты

**Files:**
- Create: `wfmt/dpapi.py`, `wfmt/account.py`
- Test: `tests/test_dpapi.py`, `tests/test_account.py`

**Interfaces:**
- Produces:
  - `protect(data: bytes) -> bytes`, `unprotect(blob: bytes) -> bytes` (ctypes `crypt32.CryptProtectData/CryptUnprotectData`, `CRYPTPROTECT_UI_FORBIDDEN`)
  - `class AuthError(Exception)` (атрибут `captcha: bool`)
  - `class Account(http, db)`: `async signin(email, password) -> str` (возвращает ник), `set_token(token: str)`, `signout()`, `is_signed_in() -> bool`, `async my_orders() -> list[MyOrder]`, `async create_order(item_id, kind: Literal["sell","buy"], platinum: int, quantity: int, rank: int | None) -> MyOrder`, `async update_order(order_id, platinum=None, quantity=None, visible=None) -> MyOrder`, `async delete_order(order_id)`.
  - `MyOrder(id, item_id, slug, kind, platinum, quantity, rank, visible)` в `models.py`.
- [ ] **Step 1: Выяснить API входа и лотов.** Проверить актуальную документацию warframe.market (сейчас v2) и запросы сайта: эндпоинт входа (исторически `POST /v1/auth/signin`, тело `{"auth_type":"header","email","password"}`, токен в заголовке ответа `Authorization`), формат заголовка авторизации для v2, эндпоинты лотов (`GET /v2/orders/my`, `POST /v2/order`, `PATCH /v2/order/{id}`, `DELETE /v2/order/{id}` — подтвердить). Записать в docstring `account.py`. Если вход требует капчу — `AuthError(captcha=True)`, интерфейс предложит вставить токен.
- [ ] **Step 2: Тесты:** `test_protect_roundtrip` (только Windows), `test_signin_stores_encrypted_token` (в `secret_get("market_token")` не встречается открытый токен), `test_password_never_persisted` (после signin — успешного и неудачного — пароль не встречается в байтах файла БД и в выводе логов `caplog`), `test_signin_bad_password_raises_auth_error`, `test_create_order_sends_auth_header`, `test_signout_deletes_token`.
- [ ] **Step 3:** FAIL → **Step 4:** реализовать → **Step 5:** PASS.
- [ ] **Step 6: Ручная проверка** (нужен пользователь: он сам вводит логин/пароль в интерфейсе после Task 10): вход, создание невидимого (`visible=false`) лота на дешёвый предмет, удаление.
- [ ] **Step 7:** Commit `feat: market account and orders`.

### Task 9: Уведомления и фоновые задачи

**Files:**
- Create: `wfmt/alerts.py`, `wfmt/notify.py`, `wfmt/scheduler.py`
- Test: `tests/test_alerts.py`, `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `refresh_all`, `search_lots`, `new_lots`, `riven_interval`, `Db.alert_list`
- Produces:
  - `check_price_alerts(alerts, snaps: list[PriceSnapshot], fired: set[int]) -> list[Notice]`; срабатывает при пересечении порога и не повторяется, пока цена не вернётся за порог. `Notice(title: str, body: str, url: str | None)` в `models.py`.
  - `riven_notices(watch, new: list[RivenLot]) -> list[Notice]`.
  - `notify(notice: Notice) -> None` — `windows_toasts.WindowsToaster("WF Market Tracker")`; при ошибке — лог, без исключения.
  - `class Scheduler(http, db, catalog)`: `start()`, `stop()`, `status() -> dict` (`last_price_refresh`, `riven_interval_s`, `last_error`). Цикл цен — раз в 300 с; цикл модов разлома — по одному оружию за тик, тик = `riven_interval(n)/n`; при первом опросе нового `RivenWatch` уведомлений нет (только помечаются увиденными).
- [ ] **Step 1: Тесты:** `test_price_below_fires_once`, `test_price_alert_rearms`, `test_first_riven_poll_silent`, `test_scheduler_survives_exception` (исключение в одном тике → следующий выполняется, `last_error` заполнен).
- [ ] **Step 2:** FAIL → **Step 3:** реализовать → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: alerts and scheduler`.

### Task 10: Веб-API и интерфейс

**Files:**
- Create: `wfmt/server.py`, `wfmt/__main__.py`, `wfmt/static/index.html`, `wfmt/static/app.css`, `wfmt/static/app.js`
- Test: `tests/test_server.py` (FastAPI TestClient, зависимости подменены)

**Interfaces:**
- Consumes: всё выше.
- Produces — маршруты (JSON):
  - `GET /api/status`, `GET /api/search?q=`, `GET/POST/DELETE /api/watch`, `GET /api/prices` (последние снимки + предыдущий снимок `prev` для стрелок ↑/↓ + история 48 ч + флаг `stale`, если старше 15 мин), `POST /api/prices/refresh`
  - `GET/POST/DELETE /api/rivens/watch`, `GET /api/rivens/lots?watch_id=` (лоты + `new` флаги), `GET /api/rivens/attributes`
  - `POST /api/inventory/enable`, `POST /api/inventory/load` (ошибки → 409 с текстом на русском: «Warframe не запущен», «Войдите в аккаунт в игре», «Повторите через N с»), `GET /api/sell`
  - `POST /api/account/signin`, `POST /api/account/token`, `POST /api/account/signout`, `GET /api/account/orders`, `POST /api/account/orders`, `PATCH /api/account/orders/{id}`, `DELETE /api/account/orders/{id}`
  - `GET/POST/DELETE /api/alerts`
  - Все POST/PATCH/DELETE требуют заголовок `X-WFMT: 1` (защита от запросов с чужих сайтов в браузере); `Host` должен быть `127.0.0.1:8777` или `localhost:8777`.
- Интерфейс: вкладки «Отслеживание», «Моды разлома», «Инвентарь / Что продать», «Мои лоты», «Уведомления»; макет из `docs/design.md`. Мини-график — inline SVG. Опрос `/api/rivens/lots` каждые 10 с, `/api/prices` каждые 60 с. Кнопка «Выставить» в «что продать» открывает форму с подставленной `unit_price`. Предупреждение при включении инвентаря: текст про риск из спецификации. Тёмная тема.
- `__main__.py`: `uvicorn.run(app, host="127.0.0.1", port=8777)`, `webbrowser.open("http://127.0.0.1:8777")` после старта; если порт занят — открыть вкладку и выйти (программа уже запущена).

- [ ] **Step 1: Тесты:** `test_mutation_requires_header` (POST без `X-WFMT` → 403), `test_bad_host_rejected` (`Host: evil.com` → 400), `test_inventory_not_running_409_message`, `test_prices_stale_flag`, `test_bind_address_is_loopback` (проверить аргументы `uvicorn.run` в `__main__`).
- [ ] **Step 2:** FAIL → **Step 3:** реализовать сервер → **Step 4:** PASS.
- [ ] **Step 5:** Реализовать страницу. Запустить `python -m wfmt`, проверить во встроенном браузере: поиск и добавление предмета, цены появились; добавить оружие для модов разлома — список обновляется каждые 10 с; ширина 1280 и 800 px без горизонтальной прокрутки.
- [ ] **Step 6:** Commit `feat: web ui`.

### Task 11: Сборка `.exe` и проверка приватности

**Files:**
- Create: `wfmt.spec`, `build.ps1`, `README.md` (на русском: запуск, что делает программа, риски)
- Test: `tests/test_privacy.py`

**Interfaces:**
- Consumes: весь пакет.
- Produces: `dist\WFMarketTracker.exe`.

- [ ] **Step 1: Тесты:** `test_no_foreign_hosts_in_source` (во всех `wfmt/**/*.py|html|js|css` встречаются только URL с хостами из `ALLOWED_HOSTS`, `127.0.0.1`, `localhost`), `test_no_cdn_in_static` (нет `<script src="http`, `<link href="http`, `@import url(http`), `test_no_telemetry_imports` (нет `sentry`, `analytics`, `requests` и т.п.).
- [ ] **Step 2:** FAIL/PASS → исправить найденное.
- [ ] **Step 3:** `wfmt.spec`: onefile, `console=False`, `datas=[("wfmt/static","wfmt/static")]`, имя `WFMarketTracker`. `build.ps1`: venv → `pytest` → `pyinstaller wfmt.spec`.
- [ ] **Step 4:** `.\build.ps1` → `dist\WFMarketTracker.exe` существует. Запустить на этой машине из чистой папки: открылась вкладка, цены загрузились, `netstat -ano | findstr 8777` показывает только `127.0.0.1:8777`.
- [ ] **Step 5:** Commit `build: single exe and privacy checks`.
