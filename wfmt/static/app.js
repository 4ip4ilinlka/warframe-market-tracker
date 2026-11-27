"use strict";

const ASSETS = "https://warframe.market/static/assets/";
const MARKET = "https://warframe.market";
const SVGNS = "http://www.w3.org/2000/svg";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

// ---------- icons (24×24 stroke glyphs) ----------
const ICONS = {
  set: "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z",
  blueprint: "M7 3h7l4 4v14H7z M14 3v4h4 M10 12h5 M10 16h5",
  chassis: "M8 4h8l3 5-3 2v9H8v-9L5 9z M12 8v12",
  neuroptics: "M5 13a7 7 0 0 1 14 0v4l-3 3H8l-3-3z M8 13h8",
  systems: "M7 7h10v10H7z M10 3v4 M14 3v4 M10 17v4 M14 17v4 M3 10h4 M3 14h4 M17 10h4 M17 14h4",
  barrel: "M3 10h14v4H3z M17 11h4v2h-4",
  receiver: "M4 8h12v6H9l-1 4H5l1-4H4z M16 10h4",
  stock: "M3 9h9l9 6v3h-6l-6-5H3z",
  blade: "M5 19L17 7l3-3-1 4L7 21z M5 19l-2 2",
  handle: "M12 3v12 M8 15h8 M12 15v6",
  bow: "M7 3c8 4 8 14 0 18 M7 3v18",
  link: "M9 15l6-6 M7 11l-2 2a3 3 0 0 0 4 4l2-2 M13 7l2-2a3 3 0 0 1 4 4l-2 2",
  gear: "M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2",
  shop: "M4 10v10h16V10 M3 10l2-6h14l2 6 M3 10c0 1.5 1.5 2.5 3 2.5S9 11.5 9 10c0 1.5 1.5 2.5 3 2.5s3-1 3-2.5c0 1.5 1.5 2.5 3 2.5s3-1 3-2.5 M10 20v-5h4v5",
  eyeOff: "M3 3l18 18 M10.6 6.1A10 10 0 0 1 22 12s-1.2 2.1-3.4 3.9 M6.6 6.6C3.9 8.3 2 12 2 12s3.6 7 10 7c1.9 0 3.5-.6 4.9-1.4",
  external: "M14 4h6v6 M20 4l-9 9 M18 14v6H4V6h6",
  close: "M6 6l12 12 M18 6L6 18",
  box: "M3 7l9-4 9 4-9 4z M3 7v10l9 4 9-4V7 M12 11v10",
  coins: "M12 4c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3z M4 7v5c0 1.7 3.6 3 8 3s8-1.3 8-3V7 M4 12v5c0 1.7 3.6 3 8 3s8-1.3 8-3v-5",
  tag: "M3 12V4h8l10 10-8 8z M7.5 7.5h.01",
  mod: "M12 3l8 5v8l-8 5-8-5V8z",
  relic: "M12 3l7 4v6c0 4-3 7-7 8-4-1-7-4-7-8V7z",
  arcane: "M12 3l3 6 6 3-6 3-3 6-3-6-6-3 6-3z",
  riven: "M12 2l7 10-7 10-7-10z M12 7l3.5 5-3.5 5-3.5-5z",
  platinum: "M12 3l8 6-8 12-8-12z M4 9h16 M9 3l3 6 3-6",
  check: "M5 12l5 5 9-10",
  alert: "M12 8v5 M12 16.5v.5 M10.3 4.2L2.8 17.5A2 2 0 0 0 4.5 20.5h15a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z",
  bell: "M6 16V11a6 6 0 0 1 12 0v5l2 2H4z M10 20a2 2 0 0 0 4 0",
  search: "M11 4a7 7 0 1 0 0 14a7 7 0 0 0 0-14z M20 20l-4-4",
};
const TIER_RU = { lith: "Лит", meso: "Мезо", neo: "Нео", axi: "Акси", requiem: "Рекв" };
const PART_ICON = {
  set: "set", blueprint: "blueprint", chassis: "chassis", neuroptics: "neuroptics", systems: "systems",
  barrel: "barrel", receiver: "receiver", stock: "stock", blade: "blade",
  handle: "handle", hilt: "handle", grip: "handle", guard: "handle",
  string: "bow", limbs: "bow", upper_limb: "bow", lower_limb: "bow", link: "link", chain: "link",
};
const PART_LABELS = {
  set: "Комплект", blueprint: "Чертёж", chassis: "Каркас", neuroptics: "Нейрооптика", systems: "Системы",
  harness: "Упряжь", wings: "Крылья", carapace: "Панцирь", cerebrum: "Мозг", barrel: "Ствол",
  receiver: "Приёмник", stock: "Приклад", blade: "Клинок", handle: "Рукоять", hilt: "Эфес", grip: "Хват",
  string: "Тетива", limbs: "Плечи лука", upper_limb: "Верхнее плечо", lower_limb: "Нижнее плечо",
  link: "Связка", chain: "Цепь", head: "Навершие", guard: "Гарда", gauntlet: "Перчатка", pouch: "Подсумок",
  ornament: "Орнамент", disc: "Диск", stars: "Звёзды", boot: "Ботинок", motor: "Мотор",
};
const CAT_ICON = { mod: "mod", relic: "relic", arcane: "arcane", prime: "set", other: "box" };
const STATUS_RU = { ingame: "в игре", online: "онлайн", offline: "не в сети" };

function svg(name, cls) {
  const s = document.createElementNS(SVGNS, "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", "1.7");
  s.setAttribute("stroke-linecap", "round");
  s.setAttribute("stroke-linejoin", "round");
  s.setAttribute("aria-hidden", "true");
  if (cls) s.setAttribute("class", cls);
  const p = document.createElementNS(SVGNS, "path");
  p.setAttribute("d", ICONS[name] || ICONS.gear);
  s.append(p);
  return s;
}

// ---------- helpers ----------
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: { "X-WFMT": "1" } };
  if (opts.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  const r = await fetch(path, init);
  let data = null;
  try { data = await r.json(); } catch { /* empty */ }
  if (!r.ok) {
    const e = new Error((data && data.error) || `Ошибка ${r.status}`);
    e.status = r.status;
    e.data = data;
    throw e;
  }
  return data;
}

// Show a spinner on a button while an async action runs; flash on success.
async function busy(btn, fn) {
  if (!btn || btn.classList.contains("busy")) return;
  btn.classList.add("busy");
  btn.disabled = true;
  try {
    const r = await fn();
    btn.classList.add("done-flash");
    setTimeout(() => btn.classList.remove("done-flash"), 900);
    return r;
  } finally {
    btn.classList.remove("busy");
    btn.disabled = false;
  }
}

let toastTimer;
function toast(msg, isErr = false) {
  const t = $("#toast");
  t.classList.remove("show");
  void t.offsetWidth; // restart the timer animation
  t.replaceChildren(svg(isErr ? "alert" : "check"), h("span", {}, msg), h("span", { class: "timer" }));
  t.classList.toggle("err", isErr);
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3500);
}

function ago(iso) {
  if (!iso) return "никогда";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.round(s)} с назад`;
  if (s < 3600) return `${Math.round(s / 60)} мин назад`;
  if (s < 86400) return `${Math.round(s / 3600)} ч назад`;
  return `${Math.round(s / 86400)} дн назад`;
}
const isOld = iso => Date.now() - new Date(iso).getTime() > 30 * 60 * 1000;
const fmt = n => Math.round(n).toLocaleString("ru-RU");

function plat(n) {
  if (n == null) return h("span", { class: "dim" }, "—");
  return h("span", { class: "price", title: `${fmt(n)} платины` }, fmt(n), svg("platinum", "plat-ico"));
}

function itemIcon({ thumb, part, category, rarity, tier, riven }, size) {
  const cat = riven ? "other" : (category || "other");
  const cls = ["ico", `cat-${cat}`, rarity ? `rar-${rarity}` : "", thumb ? "has-img" : ""].join(" ");
  const box = h("div", { class: cls, style: size ? `width:${size}px;height:${size}px` : null });
  if (thumb) {
    const img = h("img", { src: ASSETS + thumb, alt: "", loading: "lazy", decoding: "async", referrerpolicy: "no-referrer" });
    img.addEventListener("load", () => img.classList.add("loaded"));
    img.addEventListener("error", () => { img.remove(); box.classList.remove("has-img"); });
    box.append(img);
  }
  box.append(h("span", { class: "fallback" }, svg(riven ? "riven" : CAT_ICON[cat])));
  if (tier) box.append(h("span", { class: `tier t-${tier}`, title: "Эра реликвии" }, TIER_RU[tier] || tier));
  if (riven) box.append(h("span", { class: "part riven", title: "Мод разлома" }, svg("riven")));
  else if (part) box.append(h("span", { class: "part", title: PART_LABELS[part] || part }, svg(PART_ICON[part] || "gear")));
  return box;
}

function partTag(part) {
  if (!part) return null;
  return h("span", { class: "tag part-tag" }, svg(PART_ICON[part] || "gear"), PART_LABELS[part] || part);
}

function rankTag(rank, maxRank) {
  if (rank == null || maxRank == null) return null;
  const max = rank >= maxRank;
  const n = Math.min(maxRank, 10);
  const on = Math.round((rank / maxRank) * n);
  const pips = Array.from({ length: n }, (_, i) => h("i", { class: i < on ? "on" : null }));
  return h("span", { class: `pips${max ? " max" : ""}`, title: `Ранг ${rank} из ${maxRank}` }, pips, h("b", {}, max ? "макс." : `${rank}/${maxRank}`));
}

function ducatTag(d) {
  return d ? h("span", { class: "tag ducats", title: "Дукаты у Баро Ки'Тира" }, h("i", { class: "dc" }), d) : null;
}
function vaultTag(v) {
  return v ? h("span", { class: "tag vaulted", title: "Больше не выпадает в игре — цена обычно растёт" }, "в хранилище") : null;
}

function saleTag(listed) {
  if (!listed) return null;
  const qty = listed.quantity > 1 ? ` ×${listed.quantity}` : "";
  return listed.visible
    ? h("span", { class: "tag sale", title: "Выставлено на warframe.market" }, svg("shop"), `на продаже · ${listed.platinum} пл${qty}`)
    : h("span", { class: "tag sale hidden-order", title: "Лот скрыт от покупателей" }, svg("eyeOff"), `скрыт · ${listed.platinum} пл${qty}`);
}

function sparkline(points, w = 120, hgt = 32) {
  const vals = points.map(p => p.sell_min).filter(v => v != null);
  const s = document.createElementNS(SVGNS, "svg");
  s.setAttribute("width", w); s.setAttribute("height", hgt); s.setAttribute("class", "spark");
  s.setAttribute("aria-hidden", "true");
  if (vals.length < 2) return s;
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const pts = vals.map((v, i) => [(i / (vals.length - 1)) * (w - 2) + 1, hgt - 3 - ((v - min) / span) * (hgt - 6)]);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  const area = document.createElementNS(SVGNS, "path");
  area.setAttribute("d", `${line}L${w - 1},${hgt}L1,${hgt}Z`);
  area.setAttribute("class", "area");
  const path = document.createElementNS(SVGNS, "path");
  path.setAttribute("d", line);
  path.setAttribute("class", "line");
  s.append(area, path);
  return s;
}

function sparkDefs() {
  const s = document.createElementNS(SVGNS, "svg");
  s.setAttribute("width", 0); s.setAttribute("height", 0); s.setAttribute("style", "position:absolute");
  const defs = document.createElementNS(SVGNS, "defs");
  const g = document.createElementNS(SVGNS, "linearGradient");
  g.setAttribute("id", "spark-grad"); g.setAttribute("x1", 0); g.setAttribute("y1", 0); g.setAttribute("x2", 0); g.setAttribute("y2", 1);
  for (const [off, op] of [["0", ".7"], ["1", "0"]]) {
    const st = document.createElementNS(SVGNS, "stop");
    st.setAttribute("offset", off); st.setAttribute("stop-color", "#d6e2f0"); st.setAttribute("stop-opacity", op);
    g.append(st);
  }
  defs.append(g);
  const g2 = document.createElementNS(SVGNS, "linearGradient");
  g2.setAttribute("id", "value-grad"); g2.setAttribute("x1", 0); g2.setAttribute("y1", 0); g2.setAttribute("x2", 0); g2.setAttribute("y2", 1);
  for (const [off, op] of [["0", ".35"], ["1", "0"]]) {
    const st = document.createElementNS(SVGNS, "stop");
    st.setAttribute("offset", off); st.setAttribute("stop-color", "#d6b26e"); st.setAttribute("stop-opacity", op);
    g2.append(st);
  }
  defs.append(g2); s.append(defs);
  document.body.prepend(s);
}

const ext = (href, title) => h("a", { class: "icon-btn", href, target: "_blank", rel: "noreferrer", title }, svg("external"));
const itemUrl = slug => `${MARKET}/items/${slug}`;

// ---------- tabs ----------
let currentTab = "inventory";
const tabInk = h("span", { class: "tab-ink", "aria-hidden": "true" });
$(".tabs").append(tabInk);
function moveInk() {
  const b = $(`.tabs button[aria-selected="true"]`);
  if (!b) return;
  tabInk.style.left = `${b.offsetLeft + 12}px`;
  tabInk.style.width = `${b.offsetWidth - 24}px`;
}
window.addEventListener("resize", moveInk);

function showTab(name) {
  currentTab = name;
  for (const b of $$(".tabs button")) b.setAttribute("aria-selected", b.dataset.tab === name ? "true" : "false");
  moveInk();
  for (const s of $$(".tab")) s.hidden = s.id !== `tab-${name}`;
  try { localStorage.setItem("tab", name); } catch { /* ignore */ }
  refreshTab();
}
$$(".tabs button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
function refreshTab() {
  ({ watch: loadPrices, rivens: loadRivens, inventory: loadSell, orders: loadOrders, alerts: loadAlerts, primes: loadPrimes, ephemeras: loadEphemeras })[currentTab]();
}

// ---------- status ----------
let status = {};
async function loadStatus() {
  try { status = await api("/api/status"); } catch { return; }
  $("#profile-name").textContent = status.active_profile || "Профиль";
  const el = $("#status");
  el.replaceChildren();
  const sch = status.scheduler || {};
  if (status.fill && status.fill.running) el.append(h("span", { class: "live-dot", title: "Идёт загрузка цен" }));
  el.append(`Цены обновлены ${ago(sch.last_price_refresh)}`);
  if (sch.last_error && sch.last_error_at && Date.now() - new Date(sch.last_error_at) < 10 * 60 * 1000) {
    el.append(" · ", h("span", { class: "err", title: sch.last_error }, "маркет отвечает с ошибками"));
  }
  if (!status.catalog_loaded) el.append(" · ", h("span", { class: "err" }, "справочник загружается"));
}

// ---------- order dialog ----------
const dlg = $("#order-dialog");
let orderItem = null;
function openOrder(r) {
  if (!status.signed_in) {
    toast("Сначала войдите на warframe.market во вкладке «Мои лоты»", true);
    showTab("orders");
    return;
  }
  orderItem = r;
  $("#order-head").replaceChildren(h("div", { class: "item" }, itemIcon(r),
    h("div", { class: "item-text" }, h("span", { class: "item-name" }, r.name),
      h("div", { class: "item-meta" }, partTag(r.part), rankTag(r.rank, r.max_rank), r.count ? `в инвентаре ×${r.count}` : null))));
  const bits = [];
  if (r.market_min != null) bits.push(`самый дешёвый лот сейчас ${r.market_min} пл`);
  if (r.unit_price != null) bits.push(`типичная цена ${r.unit_price} пл`);
  if (r.listed) bits.push(`у вас уже выставлено ${r.listed.quantity} шт. по ${r.listed.platinum} пл`);
  $("#order-market").textContent = bits.length ? bits.join(" · ") : "";
  $("#order-price").value = r.market_min ?? r.unit_price ?? "";
  $("#order-quick")?.remove();
  const quick = [["Как рынок", r.market_min], ["На 1 дешевле", r.market_min != null ? Math.max(1, r.market_min - 1) : null],
                 ["Типичная", r.unit_price]].filter(([, v]) => v != null);
  if (quick.length) {
    const box = h("div", { class: "quick-prices", id: "order-quick" }, quick.map(([label, v]) =>
      h("button", { type: "button", class: "chip", onclick: e => {
        $("#order-price").value = v;
        for (const c of box.children) c.setAttribute("aria-pressed", String(c === e.currentTarget));
      } }, label, h("b", {}, v))));
    $("#order-market").after(box);
  }
  $("#order-qty").value = r.count || 1;
  $("#order-rank-box").hidden = r.rank == null;
  $("#order-rank").value = r.rank ?? "";
  $("#order-error").hidden = true;
  dlg.showModal();
}
$("#order-cancel").addEventListener("click", () => dlg.close());
$("#order-form").addEventListener("submit", async e => {
  e.preventDefault();
  const btn = $("#order-submit");
  if (btn.disabled) return;
  const rank = $("#order-rank-box").hidden ? null : parseInt($("#order-rank").value, 10);
  try {
    await busy(btn, () => api("/api/account/orders", { method: "POST", body: {
      item_id: orderItem.item_id, kind: "sell",
      platinum: parseInt($("#order-price").value, 10), quantity: parseInt($("#order-qty").value, 10),
      rank: Number.isFinite(rank) ? rank : null, visible: $("#order-visible").checked,
    } }));
    dlg.close();
    toast("Лот выставлен");
    refreshTab();
  } catch (err) {
    $("#order-error").textContent = err.message;
    $("#order-error").hidden = false;
  }
});

function sellButton(r) {
  return h("button", { class: `small sell-btn${r.listed ? " more-lot" : ""}`, onclick: () => openOrder(r) },
    r.listed ? "Ещё лот" : "Выставить");
}

// ---------- inventory / sell ----------
const PAGE = 60;
let sellData = null, sellAutoRefreshed = false, sellShown = PAGE;
const sellFilter = { status: "", cat: "", sub: "", q: "", sort: "total", dir: "desc" };
const CAT_LABELS = { prime: "Прайм", mod: "Моды", arcane: "Мистификаторы", relic: "Реликвии", other: "Прочее" };
// Sort helpers: missing values always go last, whatever the direction.
function sorter(key, dir) {
  const m = dir === "asc" ? 1 : -1;
  return (a, b) => {
    const x = key(a), y = key(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return (typeof x === "string" ? x.localeCompare(y, "ru") : x - y) * m;
  };
}
const SELL_KEYS = {
  total: r => r.total, unit: r => r.unit_price, market: r => r.market_min,
  count: r => r.count, name: r => r.name,
  ducats: r => (r.ducats && r.unit_price ? r.ducats / r.unit_price : null),
};
const DEFAULT_DIR = { total: "desc", unit: "desc", market: "desc", count: "desc", name: "asc", ducats: "desc" };
function setSellSort(key, dir) {
  sellFilter.sort = key;
  sellFilter.dir = dir || DEFAULT_DIR[key];
  $("#inv-sort").value = `${sellFilter.sort}:${sellFilter.dir}`;
  sellShown = PAGE;
  viewChanged();
  renderSell();
}
function sortHead(label, key, cls = "") {
  const on = sellFilter.sort === key;
  const el = h("span", { class: `sort ${cls}${on ? " on" : ""}${on && sellFilter.dir === "asc" ? " asc" : ""}`,
    title: "Сортировать по этой колонке" }, label);
  el.addEventListener("click", () => setSellSort(key, on ? (sellFilter.dir === "asc" ? "desc" : "asc") : undefined));
  return el;
}

function setChips(groupSel, attr, value) {
  for (const c of $$(`${groupSel} .chip`)) c.setAttribute("aria-pressed", c.dataset[attr] === value ? "true" : "false");
}
$$("#inv-status-chips .chip").forEach(c => c.addEventListener("click", () => {
  sellFilter.status = c.dataset.status; setChips("#inv-status-chips", "status", c.dataset.status); sellShown = PAGE; viewChanged(); renderSell();
}));
$$("#inv-cat-chips .chip").forEach(c => c.addEventListener("click", () => {
  sellFilter.cat = c.dataset.cat; sellFilter.sub = ""; setChips("#inv-cat-chips", "cat", c.dataset.cat); sellShown = PAGE; viewChanged(); renderSell();
}));

function renderSubChips(d) {
  const box = $("#inv-sub-chips");
  const cat = sellFilter.cat;
  if (!cat) { box.hidden = true; return; }
  const counts = new Map();
  for (const r of d.rows) if (r.category === cat) counts.set(r.sub, { label: r.sub_label || "Другое", n: (counts.get(r.sub)?.n || 0) + 1 });
  const total = [...counts.values()].reduce((a, b) => a + b.n, 0);
  const chip = (key, label, n) => {
    const b = h("button", { class: "chip", "aria-pressed": String(sellFilter.sub === key) }, label, h("span", { class: "n" }, n));
    b.addEventListener("click", () => { sellFilter.sub = key; sellShown = PAGE; viewChanged(); renderSell(); });
    return b;
  };
  box.replaceChildren(chip("", "Все", total),
    ...[...counts.entries()].sort((a, b) => b[1].n - a[1].n).map(([k, v]) => chip(k, v.label, v.n)));
  box.hidden = counts.size < 1;
}

function renderCatCounts(d) {
  const counts = {};
  for (const r of d.rows) counts[r.category] = (counts[r.category] || 0) + 1;
  for (const c of $$("#inv-cat-chips .chip")) {
    const key = c.dataset.cat;
    const n = key ? (counts[key] || 0) : d.rows.length;
    let badge = c.querySelector(".n");
    if (!badge) { badge = h("span", { class: "n" }); c.append(badge); }
    badge.textContent = n;
  }
}
let invSearchTimer;
$("#inv-search").addEventListener("input", e => {
  clearTimeout(invSearchTimer);
  invSearchTimer = setTimeout(() => { sellFilter.q = e.target.value.trim().toLowerCase(); sellShown = PAGE; viewChanged(); renderSell(); }, 150);
});
$("#sell-more").addEventListener("click", () => { sellShown += PAGE; renderSell(); });
$("#inv-sort").addEventListener("change", e => { const [k, d] = e.target.value.split(":"); setSellSort(k, d); });

// One polling timer at most: re-rendering (filters, "show more") must never stack new timers.
let sellPoll = null;
function scheduleSellPoll(running) {
  clearTimeout(sellPoll);
  sellPoll = running ? setTimeout(() => { sellPoll = null; if (currentTab === "inventory") loadSell(); }, 3000) : null;
}

async function refreshSellPrices() {
  await api("/api/sell/prices", { method: "POST" });
  setTimeout(loadSell, 1500);
}

function showSkeleton() {
  if (sellData) return;
  $("#sell-list").replaceChildren(...Array.from({ length: 6 }, () => h("div", { class: "skeleton" })));
}

async function loadSell() {
  showSkeleton();
  await loadStatus();
  const on = status.inventory_enabled;
  $("#inv-disabled").hidden = on;
  $("#inv-enabled").hidden = !on;
  if (!on) return;
  sellData = await api("/api/sell");
  renderSell();
  loadSets();
  const needs = sellData.rows.some(r => !r.price_at || isOld(r.price_at)) || sellData.rivens.some(r => r.reference_price == null);
  if (needs && !sellData.fill.running && !sellAutoRefreshed && sellData.inventory_at) {
    sellAutoRefreshed = true;
    refreshSellPrices();
  }
}

function statTile(cls, icon, label, value, note) {
  return h("div", { class: `stat ${cls}` },
    h("div", { class: "label" }, svg(icon), label),
    h("div", { class: "value" }, value, svg("platinum", "plat-ico")),
    note ? h("div", { class: "note" }, note) : null);
}

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const lastShown = new Map();
function countUp(el, key, target) {
  const from = lastShown.get(key) ?? 0;
  lastShown.set(key, target);
  if (reduceMotion || from === target) { el.textContent = fmt(target); return; }
  const t0 = performance.now(), dur = 600;
  const step = now => {
    const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (target - from) * e);
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function valueSpark(v) {
  const pts = (v && v.history || []).map(([, t]) => t);
  if (pts.length < 2) return null;
  const W = 120, H = 34, min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1;
  const xy = pts.map((p, i) => [(i / (pts.length - 1)) * (W - 2) + 1, H - 3 - ((p - min) / span) * (H - 6)]);
  const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  const s = document.createElementNS(SVGNS, "svg");
  s.setAttribute("width", W); s.setAttribute("height", H); s.setAttribute("class", "value-spark");
  const t = document.createElementNS(SVGNS, "title"); t.textContent = "Стоимость инвентаря за 30 дней"; s.append(t);
  for (const [cls, d] of [["area", `${line}L${W - 1},${H}L1,${H}Z`], ["line", line]]) {
    const p = document.createElementNS(SVGNS, "path"); p.setAttribute("d", d); p.setAttribute("class", cls); s.append(p);
  }
  return s;
}
function valueTrend(v) {
  if (!v || v.delta_day == null) return null;
  const d = v.delta_day;
  return h("div", { class: "trend" }, h("span", { class: `delta-day ${d > 0 ? "up" : d < 0 ? "down" : "flat"}` },
    `${d > 0 ? "+" : d < 0 ? "−" : ""}${fmt(Math.abs(d))} пл за сутки`));
}

function heroTile(d, total) {
  const byCat = {};
  for (const r of d.rows) byCat[r.category] = (byCat[r.category] || 0) + (r.total || 0);
  const num = h("span", {});
  countUp(num, "total", total);
  const parts = CAT_ORDER.filter(c => byCat[c] > 0);
  return h("div", { class: "stat hero" },
    h("div", { class: "label" }, svg("box"), "В инвентаре", h("span", { class: "dim", style: "margin-left:auto" }, `${d.rows.length} видов`)),
    h("div", { class: "value" }, num, svg("platinum", "plat-ico"), valueSpark(d.value)),
    valueTrend(d.value),
    h("div", { class: "catbar", "aria-hidden": "true" }, parts.map(c =>
      h("span", { class: `c-${c}`, style: `width:${(byCat[c] / Math.max(total, 1)) * 100}%`, title: `${CAT_LABELS[c]}: ${fmt(byCat[c])}` }))),
    h("div", { class: "legend" }, parts.map(c => h("span", {}, h("i", { class: `c-${c}` }), CAT_LABELS[c], h("b", {}, fmt(byCat[c]))))));
}

function renderStats(d) {
  const total = d.rows.reduce((s, r) => s + (r.total || 0), 0);
  const listedSum = (d.listings_summary || {}).platinum || 0;
  const listedLots = (d.listings_summary || {}).lots || 0;
  const unlisted = d.rows.filter(r => !r.listed).reduce((s, r) => s + (r.total || 0), 0);
  $("#inv-stats").replaceChildren(
    heroTile(d, total),
    statTile("on-sale", "shop", "На продаже", fmt(listedSum), status.signed_in ? `${listedLots} лотов` : "войдите во вкладке «Мои лоты»"),
    statTile("", "tag", "Можно выставить", fmt(unlisted), "по типичной цене"));
}

let sellMaxTotal = 1;
let animateRows = false;
function viewChanged() { animateRows = true; }
function sellRow(r) {
  let hint = null;
  if (r.listed && r.market_min != null && r.listed.platinum !== r.market_min) {
    const diff = r.listed.platinum - r.market_min;
    hint = h("span", { class: diff > 0 ? "hint-up" : "hint-down" },
      diff > 0 ? `ваша цена выше рынка на ${diff}` : `ваша цена ниже рынка на ${-diff}`);
  }
  const key = selKey(r);
  const cb = h("input", { type: "checkbox", class: "sel", title: "Выбрать для массового выставления", checked: selected.has(key) });
  cb.addEventListener("click", e => e.stopPropagation());
  cb.addEventListener("change", () => toggleSelect(r, cb.checked, cb.closest(".row")));
  return h("div", { class: `row${r.listed ? " is-listed" : ""}${selected.has(key) ? " selected" : ""}` },
    clickableItem(h("div", { class: "item" }, cb, itemIcon(r),
      h("div", { class: "item-text" },
        h("span", { class: "item-name", title: r.name }, r.name),
        h("div", { class: "item-meta" }, h("span", {}, `×${fmt(r.count)}`), partTag(r.part), rankTag(r.rank, r.max_rank), ducatTag(r.ducats), vaultTag(r.vaulted), saleTag(r.listed), hint))), r.slug, r.price_rank, { count: r.count, rank: r.rank, unit_price: r.unit_price }),
    h("div", { class: "col-num hide-s" }, plat(r.market_min)),
    h("div", { class: "col-num" }, plat(r.unit_price),
      r.price_at
        ? h("span", { class: `col-sub${isOld(r.price_at) ? " old" : ""}`, title: isOld(r.price_at) ? "Цена устарела, обновится сама" : "Когда обновлялась цена" }, ago(r.price_at))
        : h("span", { class: "col-sub" }, sellData.fill.running ? "загружается…" : "нет данных")),
    h("div", { class: "col-num hide-s total-cell" }, r.total != null ? h("b", {}, fmt(r.total)) : h("span", { class: "dim" }, "—"),
      r.total ? h("span", { class: "mini", title: "Доля в стоимости инвентаря" },
        h("i", { style: `width:${Math.max(4, Math.round((r.total / sellMaxTotal) * 100))}%` })) : null),
    h("div", { class: "actions" }, sellButton(r), ext(itemUrl(r.slug), "Открыть на маркете")));
}

function rivenRow(r) {
  const basis = r.reference_basis === "similar" ? `по ${r.reference_count} похожим лотам`
    : r.reference_basis === "weapon" ? "по всем лотам оружия" : (sellData.fill.running ? "считаю…" : "");
  return h("div", { class: "lot inv" },
    h("div", { class: "item" }, itemIcon({ thumb: r.weapon_thumb, riven: true }),
      h("div", { class: "item-text" }, h("span", { class: "item-name" }, r.weapon_name),
        h("div", { class: "item-meta" }, `перекатов: ${r.rerolls ?? "—"}`, r.mastery ? ` · MR ${r.mastery}` : null))),
    h("div", {}, h("div", { class: "stat-chips" },
      r.buffs.map(([n]) => h("span", { class: "stat-chip" }, "+" + n)),
      r.curses.map(([n]) => h("span", { class: `stat-chip ${r.curse_harmless ? "harmless" : "neg"}` }, "−" + n)))),
    h("div", { class: "col-num hide-s" }, r.reference_price == null && sellData.fill.running ? h("span", { class: "dim" }, "…") : plat(r.reference_price),
      h("span", { class: "basis", title: "Медиана цен выкупа похожих модов разлома на маркете" }, basis)),
    h("div", { class: "meta hide-s" }, r.reference_basis === "weapon" ? "похожих мало" : ""),
    h("div", { class: "actions" }, r.weapon_slug
      ? ext(`${MARKET}/auctions/search?type=riven&weapon_url_name=${r.weapon_slug}&sort_by=price_asc`, "Похожие лоты") : null));
}

function renderSell() {
  const d = sellData;
  if (!d) return;
  renderStats(d);
  renderCatCounts(d);
  renderSubChips(d);
  const f = sellFilter;
  const rows = d.rows.filter(r =>
    (!f.status || (f.status === "listed" ? !!r.listed : !r.listed)) &&
    (!f.cat || r.category === f.cat) &&
    (!f.sub || r.sub === f.sub) &&
    (!f.q || r.name.toLowerCase().includes(f.q) || r.slug.includes(f.q))).sort(sorter(SELL_KEYS[f.sort] || SELL_KEYS.total, f.dir));
  $("#inv-info").textContent = d.inventory_at ? `Инвентарь загружен ${ago(d.inventory_at)}` : "";
  const fill = d.fill || {};
  $("#inv-fill").hidden = !fill.running;
  if (fill.running) {
    const pct = fill.total ? Math.round((fill.done / fill.total) * 100) : 0;
    $("#inv-fill .bar span").style.width = (fill.total ? Math.max(pct, 2) : 4) + "%";
    const unpriced = d.rows.filter(r => r.unit_price == null).length;
    $("#inv-fill .fill-title").textContent = fill.total ? `Загружаю цены · ${pct}%` : "Оцениваю моды разлома по похожим лотам";
    const left = fill.total ? Math.max(0, fill.total - fill.done) : 0;
    const secs = Math.round(left / 2.5);
    $("#inv-fill .fill-eta").textContent = fill.total ? `осталось ≈ ${secs < 90 ? `${secs} с` : `${Math.round(secs / 60)} мин`}` : "";
    $("#inv-fill .fill-sub").textContent = unpriced
      ? `Без цены ещё ${unpriced} предметов — они загружаются первыми, уже оценённые не трогаются.`
      : "Все предметы оценены, уточняю медианы сделок.";
  }
  sellMaxTotal = Math.max(1, ...d.rows.map(r => r.total || 0));
  const list = $("#sell-list");
  list.replaceChildren(
    rows.length ? h("div", { class: "list-head" }, h("span", { class: "head-sel" }, selectAllBox(rows), sortHead("Предмет", "name")), sortHead("Рынок", "market", "hide-s"),
      sortHead("Цена", "unit"), sortHead("Итого", "total", "hide-s"), h("span", {}, "")) : "",
    ...rows.slice(0, sellShown).map((r, i) => {
      const el = sellRow(r);
      if (animateRows && i < 24) { el.classList.add("enter"); el.style.setProperty("--i", i); }
      return el;
    }));
  animateRows = false;
  const remaining = rows.length - Math.min(sellShown, rows.length);
  $("#sell-more").hidden = remaining <= 0;
  $("#sell-more").textContent = `Показать ещё ${Math.min(PAGE, remaining)} из ${remaining}`;
  $("#sell-empty").hidden = d.rows.length > 0;
  const groups = Object.entries(d.unmatched_groups || {}).sort((a, b) => b[1] - a[1]);
  $("#inv-unmatched").hidden = !d.unmatched;
  $("#inv-unmatched summary").textContent = `Ещё ${d.unmatched} позиций нельзя продать на маркете`;
  $("#inv-unmatched .groups").replaceChildren(...groups.map(([k, v]) => h("span", { class: "tag" }, `${k}: ${v}`)));
  $("#inv-rivens-title").hidden = !d.rivens.length;
  $("#inv-rivens").replaceChildren(...d.rivens.map(rivenRow));
  scheduleSellPoll(fill.running);
}

$("#inv-enable").addEventListener("click", async () => {
  await api("/api/inventory/enable", { method: "POST", body: { enabled: true } });
  loadSell();
});
$("#inv-disable").addEventListener("click", async () => {
  await api("/api/inventory/enable", { method: "POST", body: { enabled: false } });
  loadSell();
});
$("#inv-load").addEventListener("click", e => busy(e.currentTarget, async () => {
  try {
    const r = await api("/api/inventory/load", { method: "POST" });
    toast(`Загружено: ${r.items} позиций, модов разлома: ${r.rivens}`);
    loadSell();
  } catch (err) { toast(err.message, true); throw err; }
}).catch(() => {}));
const refreshDlg = $("#refresh-dialog");
const CAT_ORDER = ["prime", "mod", "arcane", "relic", "other"];

function refreshEstimate() {
  const subs = $$("#refresh-tree .subs input:checked").map(i => i.value);
  const n = sellData ? sellData.rows.filter(r => subs.includes(r.sub)).length : 0;
  const secs = Math.round(n * 0.5);
  $("#refresh-estimate").textContent = n
    ? `Выбрано ${n} предметов — примерно ${secs < 90 ? `${secs} с` : `${Math.round(secs / 60)} мин`} (если обновлять все заново).`
    : "Ничего не выбрано.";
  $("#refresh-go").disabled = !n;
}

function openRefresh() {
  if (!sellData) return;
  const groups = {};
  for (const r of sellData.rows) {
    const g = groups[r.category] ||= new Map();
    g.set(r.sub, { label: r.sub_label || "Другое", n: (g.get(r.sub)?.n || 0) + 1 });
  }
  const tree = $("#refresh-tree");
  tree.replaceChildren(...CAT_ORDER.filter(c => groups[c]).map(cat => {
    const all = h("input", { type: "checkbox", checked: true });
    const subs = [...groups[cat].entries()].sort((a, b) => b[1].n - a[1].n).map(([key, v]) => {
      const cb = h("input", { type: "checkbox", value: key, checked: true });
      cb.addEventListener("change", () => {
        const boxes = $$("input", subsBox);
        all.checked = boxes.every(b => b.checked);
        all.indeterminate = !all.checked && boxes.some(b => b.checked);
        refreshEstimate();
      });
      return h("label", {}, cb, v.label, h("span", { class: "n" }, v.n));
    });
    const subsBox = h("div", { class: "subs" }, subs);
    all.addEventListener("change", () => { for (const b of $$("input", subsBox)) b.checked = all.checked; all.indeterminate = false; refreshEstimate(); });
    const n = [...groups[cat].values()].reduce((a, b) => a + b.n, 0);
    return h("div", { class: "group" }, h("label", {}, all, svg(CAT_ICON[cat]), CAT_LABELS[cat], h("span", { class: "n" }, n)), subsBox);
  }));
  refreshEstimate();
  refreshDlg.showModal();
}

$("#sell-refresh").addEventListener("click", openRefresh);
$("#refresh-cancel").addEventListener("click", () => refreshDlg.close());
$("#refresh-all").addEventListener("click", () => {
  for (const b of $$("#refresh-tree input")) { b.checked = true; b.indeterminate = false; }
  refreshEstimate();
});
$("#refresh-form").addEventListener("submit", async e => {
  e.preventDefault();
  const subs = $$("#refresh-tree .subs input:checked").map(i => i.value);
  const force = $("#refresh-form").elements.mode.value === "force";
  try {
    const r = await busy($("#refresh-go"), () => api("/api/sell/prices", { method: "POST", body: { subs, force } }));
    refreshDlg.close();
    if (r.items) toast(`Обновляю цены: ${r.items} предметов`);
    else toast(force ? "Нечего обновлять" : "Цены выбранного уже свежие (моложе 30 минут)");
    setTimeout(loadSell, 1500);
  } catch (err) { toast(err.message, true); }
});

// ---------- orders / account ----------
function signinError(msg) {
  $("#signin-error").textContent = msg;
  $("#signin-error").hidden = !msg;
}

async function loadOrders() {
  await loadStatus();
  const signed = status.signed_in;
  $("#signin").hidden = signed;
  $("#orders-box").hidden = !signed;
  if (!signed) return;
  try {
    const me = await api("/api/account/me");
    $("#account-name").textContent = me.name ? `Вы вошли как ${me.name}` : "";
    ordersData = await api("/api/account/orders");
    renderOrders();
  } catch (e) {
    if (e.status === 401) { toast("Сессия маркета истекла, войдите снова", true); loadOrders(); }
    else toast(e.message, true);
  }
}

let ordersData = [];
const ORDER_KEYS = {
  name: o => o.name, price: o => o.platinum, total: o => o.platinum * o.quantity,
  diff: o => (o.market_min != null ? o.platinum - o.market_min : null),
};
function renderOrders() {
  const [k, d] = $("#orders-sort").value.split(":");
  const list = [...ordersData].sort(sorter(ORDER_KEYS[k], d));
  $("#orders-empty").hidden = list.length > 0;
  $("#orders-list").replaceChildren(...list.map(orderCard));
}
$("#orders-sort").addEventListener("change", renderOrders);

function orderCard(o) {
  const price = h("input", { type: "number", min: 1, value: o.platinum });
  const qty = h("input", { type: "number", min: 1, value: o.quantity });
  const vis = h("input", { type: "checkbox", checked: o.visible });
  const card = h("div", { class: `card${o.visible ? "" : " is-hidden"}` });
  const save = async (body, msg) => {
    try { await api(`/api/account/orders/${o.id}`, { method: "PATCH", body }); toast(msg); }
    catch (e) { toast(e.message, true); }
  };
  price.addEventListener("change", () => save({ platinum: parseInt(price.value, 10) }, "Цена изменена"));
  qty.addEventListener("change", () => save({ quantity: parseInt(qty.value, 10) }, "Количество изменено"));
  vis.addEventListener("change", () => {
    card.classList.toggle("is-hidden", !vis.checked);
    save({ visible: vis.checked }, vis.checked ? "Лот виден покупателям" : "Лот скрыт");
  });
  let market = h("span", { class: "dim", style: "font-size:12px" }, "цена рынка ещё не загружена");
  if (o.market_min != null) {
    const diff = o.platinum - o.market_min;
    market = h("span", { class: `pill ${diff > 0 ? "up" : diff < 0 ? "down" : "even"}`, title: `Самый дешёвый другой продавец: ${o.market_min} пл` },
      diff > 0 ? `дороже рынка на ${diff}` : diff < 0 ? `дешевле рынка на ${-diff}` : "вы самый дешёвый");
  }
  const lotTotal = h("span", { class: "lot-total" }, "сумма ", h("b", {}, fmt(o.platinum * o.quantity)), " пл");
  const matchBtn = o.market_min != null && o.platinum > o.market_min
    ? h("button", { class: "ghost match-btn", title: `Поставить ${o.market_min} пл — как самый дешёвый продавец`, onclick: e => busy(e.currentTarget, async () => {
        await api(`/api/account/orders/${o.id}`, { method: "PATCH", body: { platinum: o.market_min } });
        toast(`Цена «${o.name}» → ${o.market_min} пл`); loadOrders();
      }).catch(err => toast(err.message, true)) }, "под рынок")
    : null;
  const updTotal = () => { lotTotal.replaceChildren("сумма ", h("b", {}, fmt((parseInt(price.value, 10) || 0) * (parseInt(qty.value, 10) || 0))), " пл"); };
  price.addEventListener("input", updTotal);
  qty.addEventListener("input", updTotal);
  card.append(
    clickableItem(h("div", { class: "item" }, itemIcon(o),
      h("div", { class: "item-text" }, h("span", { class: "item-name", title: o.name }, o.name),
        h("div", { class: "item-meta" },
          o.kind === "sell" ? h("span", { class: "tag sale" }, svg("shop"), "продажа") : h("span", { class: "tag" }, "покупка"),
          partTag(o.part), rankTag(o.rank, o.max_rank)))), o.slug, o.rank, { count: o.quantity }),
    h("div", { class: "fields" },
      h("label", {}, "Цена, пл", price), h("label", {}, "Количество", qty),
      h("label", { class: "switch" }, vis, "Виден")),
    h("div", { class: "foot" }, market, matchBtn, lotTotal),
    h("div", { class: "card-acts" },
      o.slug ? ext(itemUrl(o.slug), "Открыть на маркете") : null,
      h("button", { class: "icon-btn", title: "Снять лот", onclick: async () => {
        if (!confirm(`Снять лот «${o.name}»?`)) return;
        try { await api(`/api/account/orders/${o.id}`, { method: "DELETE" }); toast("Лот снят"); loadOrders(); }
        catch (e) { toast(e.message, true); }
      } }, svg("close"))));
  return card;
}

$("#signin-form").addEventListener("submit", async e => {
  e.preventDefault();
  signinError("");
  const pw = $("#signin-password");
  try {
    await busy($("#signin-form button[type=submit]"), () => api("/api/account/signin", { method: "POST", body: { email: $("#signin-email").value.trim(), password: pw.value } }));
    pw.value = "";
    toast("Вход выполнен");
    loadOrders();
  } catch (err) {
    pw.value = "";
    if (err.data && err.data.captcha) {
      signinError("Маркет не разрешает вход по паролю из сторонних программ. Войдите токеном из браузера — инструкция ниже.");
      $("#token-box").open = true;
    } else {
      signinError(err.status === 401 ? (err.message.includes("сети") ? err.message : "Неверная почта или пароль.") : err.message);
    }
  }
});
$("#token-form").addEventListener("submit", async e => {
  e.preventDefault();
  signinError("");
  try {
    await busy($("#token-form button[type=submit]"), () => api("/api/account/token", { method: "POST", body: { token: $("#token").value } }));
    $("#token").value = "";
    toast("Вход выполнен");
    loadOrders();
  } catch { signinError("Маркет не принял токен. Проверьте, что скопировано значение JWT целиком."); }
});
$("#signout").addEventListener("click", async () => { await api("/api/account/signout", { method: "POST" }); loadOrders(); });
$("#orders-refresh").addEventListener("click", e => busy(e.currentTarget, loadOrders));

// ---------- watch list ----------
let searchTimer, searchItems = [], searchActive = -1;
const searchInput = $("#search"), searchList = $("#search-results");

searchInput.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 180); });
searchInput.addEventListener("keydown", e => {
  if (searchList.hidden) return;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    searchActive = Math.max(0, Math.min(searchItems.length - 1, searchActive + (e.key === "ArrowDown" ? 1 : -1)));
    $$("li", searchList).forEach((li, i) => li.classList.toggle("active", i === searchActive));
  } else if (e.key === "Enter" && searchItems[searchActive]) {
    e.preventDefault();
    const it = searchItems[searchActive];
    addWatch(it.slug, it.max_rank ? 0 : null);
  } else if (e.key === "Escape") {
    searchList.hidden = true;
  }
});
document.addEventListener("click", e => { if (!e.target.closest(".search")) searchList.hidden = true; });

function searchCategory(tags) {
  if (tags.includes("mod")) return "mod";
  if (tags.includes("arcane_enhancement")) return "arcane";
  if (tags.includes("relic")) return "relic";
  if (tags.includes("prime")) return "prime";
  return "other";
}
function slugPart(slug) {
  if (slug.endsWith("_set")) return "set";
  const base = slug.endsWith("_blueprint") ? slug.slice(0, -10) : slug;
  const keys = Object.keys(PART_LABELS).filter(k => k !== "set" && k !== "blueprint").sort((a, b) => b.length - a.length);
  for (const k of keys) if (base.endsWith("_" + k)) return k;
  return slug.endsWith("_blueprint") ? "blueprint" : null;
}

async function runSearch() {
  const q = searchInput.value.trim();
  if (q.length < 2) { searchList.hidden = true; return; }
  searchItems = await api(`/api/search?q=${encodeURIComponent(q)}`);
  searchActive = -1;
  searchList.replaceChildren(...searchItems.map(it => {
    const pick = it.max_rank
      ? h("span", { class: "pick" },
          h("button", { class: "ghost small", onclick: ev => { ev.stopPropagation(); addWatch(it.slug, 0); } }, "Ранг 0"),
          h("button", { class: "ghost small", onclick: ev => { ev.stopPropagation(); addWatch(it.slug, it.max_rank); } }, `Ранг ${it.max_rank}`))
      : null;
    return h("li", { onclick: () => addWatch(it.slug, it.max_rank ? 0 : null) },
      itemIcon({ thumb: it.thumb, part: slugPart(it.slug), category: searchCategory(it.tags),
        rarity: ["common", "uncommon", "rare", "legendary"].find(t => it.tags.includes(t)),
        tier: it.slug.endsWith("_relic") ? (TIER_RU[it.slug.split("_")[0]] ? it.slug.split("_")[0] : null) : null }),
      h("span", {}, it.name, " ", h("span", { class: "en" }, it.name_en)), pick);
  }));
  if (!searchItems.length) searchList.append(h("li", { class: "dim" }, "Ничего не найдено"));
  searchList.hidden = false;
}

async function addWatch(slug, rank) {
  searchList.hidden = true;
  searchInput.value = "";
  try {
    await api("/api/watch", { method: "POST", body: { slug, rank } });
    toast("Предмет добавлен, цена загружается");
    loadPrices();
    setTimeout(loadPrices, 3000);
  } catch (e) { toast(e.message, true); }
}

function deltaEl(cur, prev) {
  if (cur == null || prev == null || cur === prev) return null;
  const down = cur < prev;
  return h("span", { class: `delta ${down ? "down" : "up"}`, title: `было ${prev}` }, down ? "▼" : "▲", Math.abs(cur - prev));
}

let watchRows = [];
const WATCH_KEYS = {
  added: (r, i) => i, name: r => r.name, price: r => (r.latest || {}).sell_min,
  change: r => (r.latest && r.prev && r.latest.sell_min != null && r.prev.sell_min != null ? r.latest.sell_min - r.prev.sell_min : null),
};
$("#watch-sort").addEventListener("change", () => loadPrices());
async function loadPrices() {
  watchRows = await api("/api/prices");
  const [wk, wd] = $("#watch-sort").value.split(":");
  const order = watchRows.map((r, i) => ({ r, i }));
  const keyFn = WATCH_KEYS[wk];
  order.sort(sorter(x => keyFn(x.r, x.i), wd));
  const shownRows = order.map(x => x.r);
  $("#watch-list").replaceChildren(
    watchRows.length ? h("div", { class: "list-head" }, h("span", {}, "Предмет"), h("span", { class: "hide-s" }, "48 часов"),
      h("span", {}, "Продажа"), h("span", { class: "hide-s" }, "Медиана"), h("span", {}, "")) : "",
    ...shownRows.map(r => {
      const l = r.latest || {};
      return h("div", { class: `row${r.listed ? " is-listed" : ""}` },
        clickableItem(h("div", { class: "item" }, itemIcon(r),
          h("div", { class: "item-text" }, h("span", { class: "item-name" }, r.name),
            h("div", { class: "item-meta" }, partTag(r.part), rankTag(r.rank, r.max_rank), saleTag(r.listed),
              l.buy_max != null ? h("span", {}, `покупают за ${l.buy_max}`) : null,
              r.stale ? h("span", { class: "dim" }, r.latest ? `данные ${ago(l.at)}` : "загружается…") : null))), r.slug, r.rank, { count: 1 }),
        h("div", { class: "col-num hide-s" }, sparkline(r.history, 110, 30)),
        h("div", { class: "col-num" }, plat(l.sell_min), deltaEl(l.sell_min, r.prev && r.prev.sell_min),
          h("span", { class: "col-sub" }, "мин. на рынке")),
        h("div", { class: "col-num hide-s" }, l.median_48h != null ? fmt(l.median_48h) : "—",
          h("span", { class: "col-sub" }, l.volume_48h ? `${l.volume_48h} сделок` : "нет сделок")),
        h("div", { class: "actions" },
          sellButton({ ...r, count: 1, market_min: l.sell_min, unit_price: l.median_48h != null ? Math.round(l.median_48h) : l.sell_min }),
          ext(itemUrl(r.slug), "Открыть на маркете"),
          h("button", { class: "icon-btn", title: "Убрать из списка", onclick: () => removeWatch(r) }, svg("close"))));
    }));
  $("#watch-empty").hidden = watchRows.length > 0;
}

async function removeWatch(r) {
  await api(`/api/watch?slug=${encodeURIComponent(r.slug)}${r.rank != null ? `&rank=${r.rank}` : ""}`, { method: "DELETE" });
  loadPrices();
}
$("#refresh-prices").addEventListener("click", async () => {
  await api("/api/prices/refresh", { method: "POST" });
  toast("Обновляю цены");
  setTimeout(loadPrices, 3000);
});

// ---------- rivens ----------
let weapons = [], attrs = [], attrName = {};
async function loadRivenRefs() {
  if (weapons.length) return;
  [weapons, attrs] = await Promise.all([api("/api/rivens/weapons"), api("/api/rivens/attributes")]);
  attrName = Object.fromEntries(attrs.map(a => [a.slug, a.name_ru]));
  $("#riven-weapons").replaceChildren(...weapons.map(w => h("option", { value: w.name })));
  const opts = list => [h("option", { value: "" }, "—"), ...list.map(a => h("option", { value: a.slug }, a.name_ru))];
  $$(".riven-pos").forEach(s => s.replaceChildren(...opts(attrs.filter(a => !a.negative_only))));
  $("#riven-neg").replaceChildren(h("option", { value: "" }, "любой"), ...opts(attrs.filter(a => !a.positive_only)).slice(1));
}

$("#riven-form").addEventListener("submit", async e => {
  e.preventDefault();
  const name = $("#riven-weapon").value.trim().toLowerCase();
  const w = weapons.find(x => x.name.toLowerCase() === name) || weapons.find(x => x.slug === name);
  if (!w) { toast("Выберите оружие из списка", true); return; }
  const positive = [...new Set($$(".riven-pos").map(s => s.value).filter(Boolean))];
  const max = parseInt($("#riven-max").value, 10);
  try {
    await api("/api/rivens/watch", { method: "POST", body: {
      weapon_slug: w.slug, positive, negative: $("#riven-neg").value || null,
      max_price: Number.isFinite(max) ? max : null, notify: $("#riven-notify").checked,
    } });
    $("#riven-weapon").value = "";
    toast("Добавлено. Первые лоты появятся через несколько секунд");
    loadRivens();
  } catch (err) { toast(err.message, true); }
});

const POLARITY = { madurai: "V", vazarin: "D", naramon: "—", zenurik: "=", unairu: "R", penjaga: "Y", umbra: "U" };

function lotRow(l) {
  return h("div", { class: `lot${l.new ? " new" : ""}` },
    h("div", {}, plat(l.price), l.new ? h("span", { class: "col-sub", style: "color:var(--gold)" }, "новый") : null),
    h("div", {}, h("span", { class: "riven-name" }, l.name),
      h("div", { class: "stat-chips" }, l.attributes.map(a =>
        h("span", { class: `stat-chip${a.positive ? "" : " neg"}` },
          `${a.value > 0 ? "+" : ""}${a.value}% ${attrName[a.url_name] || a.url_name}`)))),
    h("div", { class: "meta" },
      h("span", {}, l.polarity ? h("span", { class: "polarity", title: l.polarity }, POLARITY[l.polarity] || "?") : null,
        ` MR ${l.mastery ?? "—"} · перекатов ${l.rerolls ?? "—"}`),
      h("span", { class: "seller" }, h("span", { class: `dot ${l.seller_status}` }), l.seller, h("span", { class: "dim" }, STATUS_RU[l.seller_status] || ""))),
    h("div", { class: "actions" }, ext(l.url, "Открыть лот")));
}

async function loadRivens() {
  await loadRivenRefs();
  const data = await api("/api/rivens/watch");
  $("#riven-interval").textContent = data.watches.length
    ? `Самые дешёвые лоты с выкупом от игроков в сети. Каждое оружие проверяется раз в ${Math.round(data.interval_s)} с.` + (data.interval_s > 10 ? " Интервал увеличен, чтобы не превысить лимит запросов маркета." : "")
    : "Самые дешёвые лоты с выкупом от игроков в сети.";
  $("#riven-empty").hidden = data.watches.length > 0;
  $("#riven-watches").replaceChildren(...data.watches.map(w => {
    const filters = [
      ...w.positive.map(p => h("span", { class: "stat-chip" }, "+" + (attrName[p] || p))),
      w.negative ? h("span", { class: "stat-chip neg" }, "−" + (attrName[w.negative] || w.negative)) : null,
      w.max_price ? h("span", { class: "tag" }, `до ${w.max_price} пл`) : null,
      w.notify ? h("span", { class: "tag sale" }, "уведомления") : null,
    ];
    return h("div", { class: "watch" },
      h("div", { class: "watch-head" },
        itemIcon({ thumb: w.weapon_thumb, riven: true }),
        h("h3", {}, w.weapon_name), h("div", { class: "filters" }, filters),
        h("span", { class: "when" }, w.updated_at ? `обновлено ${ago(w.updated_at)}` : "ожидает проверки"),
        h("button", { class: "icon-btn", title: "Перестать следить", onclick: async () => {
          await api(`/api/rivens/watch/${w.id}`, { method: "DELETE" }); loadRivens();
        } }, svg("close"))),
      w.lots.length ? h("div", {}, w.lots.map(lotRow))
        : h("p", { class: "empty" }, w.updated_at ? "Сейчас нет подходящих лотов от продавцов в сети." : "Проверяю…"));
  }));
}

// ---------- alerts ----------
const KIND_RU = { price_below: "мин. цена не выше", price_above: "мин. цена не ниже", median_below: "медиана не выше", median_above: "медиана не ниже" };
async function loadAlerts() {
  if (!watchRows.length) watchRows = await api("/api/prices");
  $("#alert-item").replaceChildren(...watchRows.map((r, i) =>
    h("option", { value: i }, r.name + (r.rank != null ? ` (ранг ${r.rank})` : ""))));
  if (!watchRows.length) $("#alert-item").append(h("option", { value: "" }, "Сначала добавьте предмет в отслеживание"));
  const list = await api("/api/alerts");
  $("#alerts-empty").hidden = list.length > 0;
  $("#alerts-list").replaceChildren(...list.map(a => h("div", { class: "row", style: "grid-template-columns:minmax(0,1fr) auto auto auto" },
    h("div", { class: "item" }, itemIcon(a), h("span", { class: "item-name" }, svg("bell", "plat-ico"), " ", a.name,
      a.rank != null ? h("span", { class: "dim" }, ` · ранг ${a.rank}`) : null)),
    h("span", { class: "dim" }, KIND_RU[a.kind] || a.kind),
    plat(a.threshold),
    h("button", { class: "icon-btn", title: "Удалить правило", onclick: async () => {
      await api(`/api/alerts/${a.id}`, { method: "DELETE" }); loadAlerts();
    } }, svg("close")))));
}
$("#alert-form").addEventListener("submit", async e => {
  e.preventDefault();
  const r = watchRows[parseInt($("#alert-item").value, 10)];
  if (!r) return;
  try {
    await api("/api/alerts", { method: "POST", body: {
      kind: $("#alert-kind").value, slug: r.slug, rank: r.rank, threshold: parseInt($("#alert-threshold").value, 10),
    } });
    $("#alert-threshold").value = "";
    toast("Правило добавлено");
    loadAlerts();
  } catch (err) { toast(err.message, true); }
});


// ---------- item drawer ----------
const drawer = $("#item-drawer");
let drawerRange = "h48";
drawer.addEventListener("click", e => { if (e.target === drawer) drawer.close(); });

function clickableItem(el, slug, rank, extra) {
  el.classList.add("clickable");
  el.title = "Открыть карточку предмета";
  el.addEventListener("click", () => openItem(slug, rank, extra));
  return el;
}

function chartSvg(points, onHover) {
  const W = 540, H = 210, P = { l: 34, r: 8, t: 10, b: 46 }, VB = 30;
  const s = document.createElementNS(SVGNS, "svg");
  s.setAttribute("viewBox", `0 0 ${W} ${H}`);
  s.setAttribute("class", "chart");
  const pts = points.filter(p => p.median != null);
  if (pts.length < 2) {
    const t = document.createElementNS(SVGNS, "text");
    t.setAttribute("x", W / 2); t.setAttribute("y", H / 2); t.setAttribute("text-anchor", "middle"); t.setAttribute("class", "axis");
    t.textContent = "Мало сделок для графика";
    s.append(t);
    return s;
  }
  const lo = Math.min(...pts.map(p => p.min ?? p.median)), hi = Math.max(...pts.map(p => p.max ?? p.median));
  const span = hi - lo || 1, vmax = Math.max(...pts.map(p => p.volume || 0), 1);
  const iw = W - P.l - P.r, ih = H - P.t - P.b - VB;
  const x = i => P.l + (i / (pts.length - 1)) * iw;
  const y = v => P.t + ih - ((v - lo) / span) * ih;
  const el = (tag, attrs) => { const n = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  for (const v of [lo, lo + span / 2, hi]) {
    s.append(el("line", { x1: P.l, x2: W - P.r, y1: y(v), y2: y(v), class: "grid" }));
    const t = el("text", { x: P.l - 6, y: y(v) + 3, "text-anchor": "end", class: "axis" }); t.textContent = Math.round(v); s.append(t);
  }
  const top = pts.map((p, i) => `${x(i)},${y(p.max ?? p.median)}`), bot = pts.map((p, i) => `${x(i)},${y(p.min ?? p.median)}`).reverse();
  s.append(el("polygon", { points: [...top, ...bot].join(" "), class: "band" }));
  s.append(el("path", { d: pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.median).toFixed(1)}`).join(""), class: "med draw", pathLength: 1 }));
  const bw = Math.max(1.5, iw / pts.length - 2), vb0 = H - P.b + 14;
  pts.forEach((p, i) => {
    const hgt = ((p.volume || 0) / vmax) * VB;
    s.append(el("rect", { x: x(i) - bw / 2, y: vb0 + VB - hgt - 14, width: bw, height: Math.max(hgt, 1), class: "vol" }));
  });
  const fmtT = t => new Date(t).toLocaleDateString("ru-RU", { day: "numeric", month: "short", ...(drawerRange === "h48" ? { hour: "2-digit", minute: "2-digit" } : {}) });
  for (const [i, anchor] of [[0, "start"], [pts.length - 1, "end"]]) {
    const t = el("text", { x: x(i), y: H - 4, "text-anchor": anchor, class: "axis" }); t.textContent = fmtT(pts[i].t); s.append(t);
  }
  const cursor = el("line", { y1: P.t, y2: H - P.b + 14 + VB - 14, class: "cursor", visibility: "hidden" });
  const dot = el("circle", { r: 4, class: "dot", visibility: "hidden" });
  s.append(cursor, dot);
  const hit = el("rect", { x: P.l, y: 0, width: iw, height: H, fill: "transparent" });
  hit.addEventListener("mousemove", ev => {
    const r = s.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(pts.length - 1, Math.round(((px - P.l) / iw) * (pts.length - 1))));
    for (const n of [cursor, dot]) n.setAttribute("visibility", "visible");
    cursor.setAttribute("x1", x(i)); cursor.setAttribute("x2", x(i));
    dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(pts[i].median));
    onHover(pts[i], fmtT(pts[i].t));
  });
  hit.addEventListener("mouseleave", () => { for (const n of [cursor, dot]) n.setAttribute("visibility", "hidden"); onHover(null); });
  s.append(hit);
  return s;
}

function recentMedian(d90, days = 7) {
  const cut = Date.now() - days * 86400000;
  const vals = [];
  for (const p of d90) if (p.median != null && new Date(p.t).getTime() >= cut) for (let i = 0; i < Math.max(1, p.volume); i++) vals.push(p.median);
  if (!vals.length) return null;
  vals.sort((a, b) => a - b);
  const m = vals.length >> 1;
  return vals.length % 2 ? vals[m] : (vals[m - 1] + vals[m]) / 2;
}

function whisper(kind, name, item, price) {
  const verb = kind === "buy" ? "buy" : "sell";
  return `/w ${name} Hi! I want to ${verb}: "${item}" for ${price} platinum. (warframe.market)`;
}

function traderRow(t, kind, d) {
  const total = t.unit * t.per_trade;
  const copy = h("button", { class: "ghost small", title: "Скопировать сообщение для игрового чата", onclick: async () => {
    const text = whisper(kind === "sell" ? "buy" : "sell", t.name, d.name_en, total);
    try {
      await navigator.clipboard.writeText(text);
      const label = copy.textContent;
      copy.textContent = "Скопировано ✓";
      copy.classList.add("copied");
      setTimeout(() => { copy.textContent = label; copy.classList.remove("copied"); }, 1600);
      toast("Сообщение скопировано — вставьте его в чат игры");
    } catch { toast(text); }
  } }, kind === "sell" ? "Купить" : "Продать");
  return h("div", { class: "trader" },
    h("div", { class: "who" }, h("span", { class: `dot ${t.status}` }), h("span", { class: "n" }, t.name),
      t.reputation != null ? h("span", { class: "rep", title: "Репутация" }, `★${t.reputation}`) : null),
    h("div", { class: "col-num" }, plat(t.unit), t.per_trade > 1 ? h("span", { class: "bulk" }, `${total} за ${t.per_trade} шт.`) : null),
    h("div", { class: "qty" }, `${t.quantity} шт.`),
    copy);
}

async function openItem(slug, rank, extra = {}) {
  const body = $("#drawer-body");
  body.replaceChildren(h("p", { class: "hint" }, "Загружаю данные маркета…"));
  if (!drawer.open) drawer.showModal();
  let d;
  try {
    d = await api(`/api/item/${encodeURIComponent(slug)}${rank != null ? `?rank=${rank}` : ""}`);
  } catch (e) { body.replaceChildren(h("p", { class: "error" }, e.message)); return; }
  const now = d.sellers.length ? d.sellers[0].unit : null;
  const med48 = (() => { const v = []; for (const p of d.h48) if (p.median != null) for (let i = 0; i < Math.max(1, p.volume); i++) v.push(p.median); v.sort((a, b) => a - b); return v.length ? (v.length % 2 ? v[v.length >> 1] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2) : null; })();
  const med7 = recentMedian(d.d90);
  // No trades in 48 h: open the 90-day view right away.
  if (drawerRange === "h48" && d.h48.filter(p => p.median != null).length < 2) drawerRange = "d90";
  const tip = h("div", { class: "chart-tip" }, "Наведите на график, чтобы увидеть цену в точке");
  const chartBox = h("div");
  const drawChart = () => {
    chartBox.replaceChildren(chartSvg(drawerRange === "h48" ? d.h48 : d.d90, (p, when) => {
      tip.replaceChildren(p ? h("span", {}, `${when}: медиана `, h("b", {}, p.median), ` · от ${p.min ?? "—"} до ${p.max ?? "—"} · сделок `, h("b", {}, p.volume))
        : "Наведите на график, чтобы увидеть цену в точке");
    }));
  };
  const rangeChips = h("div", { class: "chips" },
    ...[["h48", "48 часов"], ["d90", "90 дней"]].map(([k, label]) => {
      const b = h("button", { class: "chip", "aria-pressed": String(drawerRange === k), onclick: () => {
        drawerRange = k; for (const c of rangeChips.children) c.setAttribute("aria-pressed", String(c === b)); drawChart();
      } }, label);
      return b;
    }));
  drawChart();
  const row = { ...extra, slug, rank, item_id: d.item_id, name: d.name, thumb: d.thumb, part: d.part, category: d.category,
    rarity: d.rarity, tier: d.tier, max_rank: d.max_rank, listed: d.listed, market_min: now,
    unit_price: extra.unit_price ?? (med48 != null ? Math.min(Math.round(med48), now ?? Infinity) : now) };
  body.replaceChildren(
    h("div", { class: "drawer-head" }, itemIcon(d),
      h("div", {}, h("h2", {}, d.name), h("div", { class: "en" }, d.name_en),
        h("div", { class: "item-meta" }, partTag(d.part), rankTag(rank, d.max_rank), ducatTag(d.ducats), vaultTag(d.vaulted), saleTag(d.listed),
          d.subtype ? h("span", { class: "tag" }, d.subtype === "intact" ? "целая" : d.subtype) : null)),
      h("button", { class: "icon-btn close", title: "Закрыть", onclick: () => drawer.close() }, svg("close"))),
    h("div", { class: "kpis" },
      h("div", { class: "kpi" }, h("div", { class: "label" }, "Сейчас от (онлайн)"), plat(now)),
      h("div", { class: "kpi" }, h("div", { class: "label" }, "Медиана 48 ч"), plat(med48)),
      h("div", { class: "kpi" }, h("div", { class: "label" }, "Медиана 7 дней"), plat(med7))),
    h("div", { class: "drawer-actions" },
      h("button", { class: "primary", onclick: () => { drawer.close(); openOrder(row); } }, d.listed ? "Выставить ещё" : "Выставить на продажу"),
      h("button", { class: "ghost", onclick: async () => {
        try { await api("/api/watch", { method: "POST", body: { slug, rank } }); toast("Добавлено в отслеживание"); } catch (e) { toast(e.message, true); }
      } }, "Отслеживать"),
      h("a", { class: "ghost", href: itemUrl(slug), target: "_blank", rel: "noreferrer", style: "display:inline-flex;align-items:center;gap:6px;padding:0 14px;border-radius:6px;text-decoration:none;color:inherit;min-height:34px" }, svg("external", "plat-ico"), "На маркете")),
    h("div", { class: "chart-card" }, h("div", { class: "chart-top" }, h("h3", {}, "Цена сделок"), rangeChips), chartBox, tip),
    h("div", { class: "traders" }, h("h3", {}, `Продают сейчас (${d.sellers.length})`),
      d.sellers.length ? d.sellers.slice(0, 8).map(t => traderRow(t, "sell", d)) : h("p", { class: "hint" }, "Нет продавцов онлайн.")),
    h("div", { class: "traders" }, h("h3", {}, `Покупают сейчас (${d.buyers.length})`),
      d.buyers.length ? d.buyers.slice(0, 8).map(t => traderRow(t, "buy", d)) : h("p", { class: "hint" }, "Нет покупателей онлайн.")));
}


// ---------- selection & bulk listing ----------
const selected = new Map();
const selKey = r => `${r.slug}|${r.rank ?? ""}`;

function updateSelectBar() {
  const bar = $("#select-bar");
  const n = selected.size;
  bar.hidden = n === 0;
  document.body.classList.toggle("has-selection", n > 0);
  if (!n) return;
  const sum = [...selected.values()].reduce((s, r) => s + (r.total || 0), 0);
  $("#sel-count").replaceChildren(`Выбрано ${n}`, h("small", {}, `≈ ${fmt(sum)} пл по типичной цене`));
}

function toggleSelect(r, on, rowEl) {
  const key = selKey(r);
  if (on) selected.set(key, r); else selected.delete(key);
  rowEl?.classList.toggle("selected", on);
  updateSelectBar();
  const all = $("#sell-list .list-head .sel");
  if (all) syncSelectAll(all, currentRows);
}

let currentRows = [];
function syncSelectAll(box, rows) {
  const n = rows.filter(r => selected.has(selKey(r))).length;
  box.checked = rows.length > 0 && n === rows.length;
  box.indeterminate = n > 0 && n < rows.length;
}

function selectAllBox(rows) {
  currentRows = rows;
  const box = h("input", { type: "checkbox", class: "sel", title: "Выбрать все в списке" });
  syncSelectAll(box, rows);
  box.addEventListener("change", () => {
    for (const r of rows) { if (box.checked) selected.set(selKey(r), r); else selected.delete(selKey(r)); }
    renderSell();
    updateSelectBar();
  });
  return box;
}

$("#sel-clear").addEventListener("click", () => { selected.clear(); updateSelectBar(); renderSell(); });

const bulkDlg = $("#bulk-dialog");
let bulkStrategy = "market";
function strategyPrice(r) {
  if (bulkStrategy === "under" && r.market_min != null) return Math.max(1, r.market_min - 1);
  if (bulkStrategy === "median" && r.unit_price != null) return r.unit_price;
  return r.market_min ?? r.unit_price ?? null;
}

function bulkSum() {
  let sum = 0, n = 0;
  for (const row of $$("#bulk-list .bulk-row")) {
    const p = parseInt(row.querySelector(".b-price").value, 10), q = parseInt(row.querySelector(".b-qty").value, 10);
    if (p > 0 && q > 0) { sum += p * q; n++; }
  }
  $("#bulk-sum").replaceChildren(`${n} лотов на `, h("b", {}, fmt(sum)), " пл");
  $("#bulk-go").disabled = n === 0;
}

function openBulk() {
  if (!status.signed_in) { toast("Сначала войдите на warframe.market во вкладке «Мои лоты»", true); showTab("orders"); return; }
  const items = [...selected.values()];
  $("#bulk-title").textContent = `Выставить выбранные (${items.length})`;
  const list = $("#bulk-list");
  list.replaceChildren(h("div", { class: "bulk-head" }, h("span", {}, "Предмет"), h("span", {}, "Кол-во"), h("span", {}, "Цена, пл"), h("span", {})),
    ...items.map(r => {
      const qty = h("input", { type: "number", min: 1, max: r.count, value: r.count, class: "b-qty" });
      const price = h("input", { type: "number", min: 1, value: strategyPrice(r) ?? "", class: "b-price" });
      qty.addEventListener("input", bulkSum); price.addEventListener("input", bulkSum);
      const row = h("div", { class: "bulk-row" },
        h("div", { class: "item" }, itemIcon(r), h("div", { class: "item-text" }, h("span", { class: "item-name" }, r.name),
          h("span", { class: "bulk-hint" }, [r.market_min != null ? `рынок ${r.market_min}` : null, r.unit_price != null ? `типичная ${r.unit_price}` : null,
            r.rank != null ? `ранг ${r.rank}` : null].filter(Boolean).join(" · ")))),
        qty, price,
        h("button", { type: "button", class: "icon-btn", title: "Убрать из списка", onclick: () => { row.remove(); bulkSum(); } }, svg("close")));
      row._item = r;
      return row;
    }));
  bulkSum();
  bulkDlg.showModal();
}
$("#sel-list").addEventListener("click", openBulk);
$("#bulk-close").addEventListener("click", () => bulkDlg.close());
$("#bulk-cancel").addEventListener("click", () => bulkDlg.close());
$$("#bulk-strategy .chip").forEach(c => c.addEventListener("click", () => {
  bulkStrategy = c.dataset.s;
  for (const x of $$("#bulk-strategy .chip")) x.setAttribute("aria-pressed", String(x === c));
  for (const row of $$("#bulk-list .bulk-row")) { const v = strategyPrice(row._item); if (v != null) row.querySelector(".b-price").value = v; }
  bulkSum();
}));
$("#bulk-form").addEventListener("submit", async e => {
  e.preventDefault();
  const rows = $$("#bulk-list .bulk-row");
  const items = rows.map(row => ({ row, item_id: row._item.item_id, rank: row._item.rank,
    platinum: parseInt(row.querySelector(".b-price").value, 10), quantity: parseInt(row.querySelector(".b-qty").value, 10) }))
    .filter(x => x.platinum > 0 && x.quantity > 0);
  if (!items.length) return;
  try {
    const r = await busy($("#bulk-go"), () => api("/api/account/orders/bulk", { method: "POST", body: {
      visible: $("#bulk-visible").checked, items: items.map(({ item_id, rank, platinum, quantity }) => ({ item_id, rank, platinum, quantity })) } }));
    r.results.forEach((res, i) => {
      const row = items[i].row;
      row.classList.add(res.ok ? "done" : "fail");
      if (res.ok) selected.delete(selKey(row._item));
      else row.querySelector(".bulk-hint").textContent = res.error;
    });
    updateSelectBar();
    const failed = r.results.length - r.ok;
    toast(failed ? `Выставлено ${r.ok}, не удалось ${failed} — причины в списке` : `Выставлено лотов: ${r.ok}`, failed > 0);
    if (!failed) setTimeout(() => bulkDlg.close(), 700);
    loadSell();
  } catch (err) { toast(err.message, true); }
});

// ---------- match my lots to the market ----------
const matchDlg = $("#match-dialog");
function matchCandidates() {
  return ordersData.filter(o => o.kind === "sell" && o.market_min != null && o.platinum > o.market_min);
}
function matchPrice(o) { return $("#match-under").checked ? Math.max(1, o.market_min - 1) : o.market_min; }
function renderMatch() {
  const list = matchCandidates();
  $("#match-list").replaceChildren(...(list.length ? list.map(o => {
    const row = h("div", { class: "bulk-row match-row" },
      h("div", { class: "item" }, itemIcon(o), h("span", { class: "item-name" }, o.name)),
      h("span", { class: "old" }, o.platinum), h("span", { class: "arrow" }, "→"), h("span", { class: "new" }, matchPrice(o)));
    row._order = o;
    return row;
  }) : [h("p", { class: "profile-empty" }, "Все ваши лоты уже не дороже рынка 👍")]));
  $("#match-go").disabled = !list.length;
}
$("#orders-match").addEventListener("click", () => { renderMatch(); matchDlg.showModal(); });
$("#match-under").addEventListener("change", renderMatch);
$("#match-close").addEventListener("click", () => matchDlg.close());
$("#match-cancel").addEventListener("click", () => matchDlg.close());
$("#match-form").addEventListener("submit", async e => {
  e.preventDefault();
  const rows = $$("#match-list .match-row");
  await busy($("#match-go"), async () => {
    let ok = 0;
    for (const row of rows) {
      try { await api(`/api/account/orders/${row._order.id}`, { method: "PATCH", body: { platinum: matchPrice(row._order) } }); row.classList.add("done"); ok++; }
      catch { row.classList.add("fail"); }
    }
    toast(`Цены обновлены: ${ok} из ${rows.length}`, ok < rows.length);
  });
  setTimeout(() => { matchDlg.close(); loadOrders(); }, 600);
});

// ---------- profiles ----------
const profDlg = $("#profiles-dialog");
function uiState() {
  return { tab: currentTab, sell: { ...sellFilter }, watchSort: $("#watch-sort").value, ordersSort: $("#orders-sort").value };
}
function applyUi(ui) {
  if (!ui) return;
  if (ui.sell) {
    Object.assign(sellFilter, ui.sell);
    setChips("#inv-status-chips", "status", sellFilter.status || "");
    setChips("#inv-cat-chips", "cat", sellFilter.cat || "");
    $("#inv-search").value = sellFilter.q || "";
    $("#inv-sort").value = `${sellFilter.sort}:${sellFilter.dir}`;
  }
  if (ui.watchSort) $("#watch-sort").value = ui.watchSort;
  if (ui.ordersSort) $("#orders-sort").value = ui.ordersSort;
  showTab(ui.tab && $(`.tabs button[data-tab="${ui.tab}"]`) ? ui.tab : currentTab);
}
const fmtDate = iso => new Date(iso).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

async function renderProfiles() {
  const { profiles, active } = await api("/api/profiles");
  const list = $("#profile-list");
  if (!profiles.length) { list.replaceChildren(h("p", { class: "profile-empty" }, "Профилей пока нет. Настройте всё как удобно и сохраните — потом вернётесь к этому одним кликом.")); return; }
  list.replaceChildren(...profiles.map(p => h("div", { class: `profile-card${p.name === active ? " active" : ""}` },
    h("span", { class: "avatar" }),
    h("div", {}, h("div", { class: "pname" }, p.name, p.name === active ? h("span", { class: "badge" }, "активен") : null),
      h("div", { class: "pmeta" }, `сохранён ${fmtDate(p.saved_at)} · отслеживание ${p.watch} · моды разлома ${p.rivens} · уведомления ${p.alerts}` + (p.inventory ? " · с инвентарём" : ""))),
    h("div", { class: "pacts" },
      h("button", { class: "primary small", onclick: e => busy(e.currentTarget, async () => {
        const r = await api(`/api/profiles/${encodeURIComponent(p.name)}/load`, { method: "POST" });
        profDlg.close();
        sellData = null;
        applyUi(r.ui);
        loadStatus();
        toast(`Загружен профиль «${p.name}»`);
      }).catch(err => toast(err.message, true)) }, "Загрузить"),
      h("button", { class: "ghost small", title: "Сохранить текущие настройки в этот профиль", onclick: e => busy(e.currentTarget, async () => {
        await api("/api/profiles", { method: "POST", body: { name: p.name, ui: uiState(), include_inventory: p.inventory } });
        toast(`Профиль «${p.name}» обновлён`); renderProfiles(); loadStatus();
      }) }, "Перезаписать"),
      h("button", { class: "icon-btn", title: "Сохранить в файл", onclick: async () => {
        const r = await fetch(`/api/profiles/${encodeURIComponent(p.name)}/export`, { headers: { "X-WFMT": "1" } });
        const url = URL.createObjectURL(await r.blob());
        const a = h("a", { href: url, download: `${p.name}.wfmt-profile.json` }); document.body.append(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
      } }, svg("external")),
      h("button", { class: "icon-btn", title: "Удалить профиль", onclick: async () => {
        if (!confirm(`Удалить профиль «${p.name}»?`)) return;
        await api(`/api/profiles/${encodeURIComponent(p.name)}`, { method: "DELETE" }); renderProfiles(); loadStatus();
      } }, svg("close"))))));
}
$("#profile-btn").addEventListener("click", () => { renderProfiles(); profDlg.showModal(); });
$("#profiles-close").addEventListener("click", () => profDlg.close());
profDlg.addEventListener("click", e => { if (e.target === profDlg) profDlg.close(); });
$("#profile-form").addEventListener("submit", e => {
  e.preventDefault();
  busy($("#profile-save-btn"), async () => {
    const name = $("#profile-new-name").value;
    const r = await api("/api/profiles", { method: "POST", body: { name, ui: uiState(), include_inventory: $("#profile-with-inv").checked } });
    $("#profile-new-name").value = "";
    toast(`Профиль «${r.name}» сохранён`); renderProfiles(); loadStatus();
  }).catch(err => toast(err.message, true));
});
$("#profile-import-btn").addEventListener("click", () => $("#profile-file").click());
$("#profile-file").addEventListener("change", async e => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    const name = file.name.replace(/\.wfmt-profile\.json$|\.json$/i, "").slice(0, 40) || "Импорт";
    const r = await api("/api/profiles/import", { method: "POST", body: { name, data } });
    toast(`Профиль «${r.name}» добавлен — нажмите «Загрузить», чтобы применить`); renderProfiles();
  } catch (err) { toast(err instanceof SyntaxError ? "Это не файл профиля" : err.message, true); }
});

// ---------- keyboard ----------
document.addEventListener("keydown", e => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
  if (e.key === "/" && !typing && !document.querySelector("dialog[open]")) {
    const target = currentTab === "inventory" ? $("#inv-search") : currentTab === "watch" ? $("#search") : null;
    if (target) { e.preventDefault(); target.focus(); target.select(); }
  }
  if (e.key === "Escape" && !document.querySelector("dialog[open]") && selected.size) {
    selected.clear(); updateSelectBar(); renderSell();
  }
});


// ---------- sets you can build ----------
let setsCollapsed = false, setsShowAll = false;
const SETS_PREVIEW = 6;
try { setsCollapsed = localStorage.getItem("setsCollapsed") === "1"; } catch { /* ignore */ }
$("#sets-toggle").addEventListener("click", () => {
  setsCollapsed = !setsCollapsed;
  try { localStorage.setItem("setsCollapsed", setsCollapsed ? "1" : "0"); } catch { /* ignore */ }
  $("#sets-panel").classList.toggle("collapsed", setsCollapsed);
  $("#sets-toggle").setAttribute("aria-expanded", String(!setsCollapsed));
});

async function loadSets() {
  let data;
  try { data = await api("/api/sets"); } catch { return; }
  const panel = $("#sets-panel");
  const list = data.sets;
  panel.hidden = !list.length;
  if (!list.length) return;
  panel.classList.toggle("collapsed", setsCollapsed);
  $("#sets-toggle").setAttribute("aria-expanded", String(!setsCollapsed));
  const better = list.filter(x => x.better === "set");
  const extra = better.reduce((s, x) => s + x.gain * x.count, 0);
  $("#sets-panel .sets-title").textContent = `Можно собрать комплекты: ${list.length}`;
  $("#sets-panel .sets-sub").textContent = better.length
    ? `комплектом выгоднее для ${better.length} — это ещё ≈ ${fmt(extra)} пл сверху`
    : "по частям сейчас выгоднее или цены ещё загружаются";
  const cards = list.map(x => {
    const best = x.better;
    const opt = (kind, label, price) => h("div", { class: `opt${best === kind ? " best" : ""}` },
      h("div", { class: "label" }, label, best === kind && x.gain != null ? h("b", {}, `+${fmt(Math.abs(x.gain))}`) : null),
      plat(price));
    return h("div", { class: "set-card" },
      clickableItem(h("div", { class: "item" }, itemIcon({ thumb: x.thumb, part: "set", category: "prime" }),
        h("div", { class: "item-text" }, h("span", { class: "item-name" }, x.name),
          h("div", { class: "item-meta" }, h("span", {}, `можно собрать ×${x.count}`), ducatTag(x.ducats)))), x.slug, null, { count: x.count }),
      h("div", { class: "compare" }, opt("set", "Комплектом", x.set_price), opt("parts", "По частям", x.parts_price)),
      h("div", { class: "parts" }, x.parts.map(p => {
        const part = slugPart(p.slug);
        return h("span", { class: "tag", title: p.name }, part ? svg(PART_ICON[part] || "gear") : null,
          `${PART_LABELS[part] || p.name} `, h("b", { style: "color:var(--text);font-weight:500" }, p.owned), `/${p.qty}`);
      })),
      h("div", { class: "foot" },
        h("span", { class: "hint" }, best === "set" ? "Соберите в игре и продайте комплектом" : best === "parts" ? "Выгоднее продавать детали" : "Цены загружаются…"),
        h("span", { class: "spacer" }),
        best === "set" ? h("button", { class: "small sell-btn", onclick: () => openOrder({ slug: x.slug, item_id: x.item_id, name: x.name, thumb: x.thumb,
          part: "set", category: "prime", count: x.count, rank: null, market_min: x.set_price, unit_price: x.set_price }) }, "Выставить") : null));
  });
  const shown = setsShowAll ? cards : cards.slice(0, SETS_PREVIEW);
  const more = cards.length > SETS_PREVIEW
    ? h("button", { class: "ghost small sets-more", onclick: () => { setsShowAll = !setsShowAll; loadSets(); } },
        setsShowAll ? "Свернуть" : `Показать все ${cards.length}`)
    : null;
  $("#sets-list").replaceChildren(...shown, ...(more ? [h("div", { class: "sets-more-row" }, more)] : []));
}

// ---------- command palette (Ctrl+K) ----------
const palette = $("#palette");
let palItems = [], palActive = 0, palTimer;
function openPalette() {
  if (document.querySelector("dialog[open]") && !palette.open) return;
  $("#palette-input").value = "";
  $("#palette-list").replaceChildren(h("li", { class: "dim" }, "Начните вводить название — по-русски или по-английски"));
  palItems = [];
  palette.showModal();
  $("#palette-input").focus();
}
function renderPalette() {
  $("#palette-list").replaceChildren(...(palItems.length ? palItems.map((it, i) => {
    const li = h("li", { class: i === palActive ? "active" : null, onclick: () => pick(i) },
      itemIcon({ thumb: it.thumb, part: slugPart(it.slug), category: searchCategory(it.tags) }),
      h("span", {}, it.name, h("span", { class: "en" }, it.name_en)), h("span", { class: "go" }, "открыть ↵"));
    li.addEventListener("mousemove", () => { if (palActive !== i) { palActive = i; renderPalette(); } });
    return li;
  }) : [h("li", { class: "dim" }, "Ничего не найдено")]));
  $("#palette-list li.active")?.scrollIntoView({ block: "nearest" });
}
function pick(i) {
  const it = palItems[i];
  if (!it) return;
  palette.close();
  openItem(it.slug, it.max_rank ? 0 : null, { count: 1 });
}
$("#palette-input").addEventListener("input", () => {
  clearTimeout(palTimer);
  palTimer = setTimeout(async () => {
    const q = $("#palette-input").value.trim();
    if (q.length < 2) return;
    palItems = await api(`/api/search?q=${encodeURIComponent(q)}`);
    palActive = 0;
    renderPalette();
  }, 140);
});
$("#palette-input").addEventListener("keydown", e => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    if (!palItems.length) return;
    palActive = (palActive + (e.key === "ArrowDown" ? 1 : -1) + palItems.length) % palItems.length;
    renderPalette();
  } else if (e.key === "Enter") { e.preventDefault(); pick(palActive); }
});
palette.addEventListener("click", e => { if (e.target === palette) palette.close(); });
$("#palette-btn").addEventListener("click", openPalette);
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K" || e.key === "л" || e.key === "Л")) { e.preventDefault(); openPalette(); }
});


// ---------- primes: active pool, vault, Varzia ----------
const primeFilter = { status: "", kind: "warframe", q: "", mine: false };
let primesData = null, primesAnimate = true, countdownTimer = null;
const PRIME_STATUS_RU = { active: "Выпадает", varzia: "У Варзии", vaulted: "В хранилище" };
const STATUS_HINT = {
  active: "Детали выпадают из реликвий, которые сейчас в игре",
  varzia: "Сейчас продаётся у Варзии на Марсе (Возрождение Прайм)",
  vaulted: "Убран в хранилище: реликвии больше не выпадают",
};
const relicLabel = slug => slug.replace(/_relic$/, "").split("_").map((w, i) => i === 0 ? w[0].toUpperCase() + w.slice(1) : w.toUpperCase()).join(" ");

function bindSeg(sel, key, after) {
  $$(`${sel} .chip`).forEach(c => c.addEventListener("click", () => {
    primeFilter[key] = c.dataset.v;
    for (const x of $$(`${sel} .chip`)) x.setAttribute("aria-pressed", String(x === c));
    primesAnimate = true;
    after();
  }));
}
bindSeg("#primes-status", "status", renderPrimes);
bindSeg("#primes-kind", "kind", renderPrimes);
let primeSearchTimer;
$("#primes-search").addEventListener("input", e => {
  clearTimeout(primeSearchTimer);
  primeSearchTimer = setTimeout(() => { primeFilter.q = e.target.value.trim().toLowerCase(); primesAnimate = true; renderPrimes(); }, 150);
});
$("#primes-mine").addEventListener("change", e => { primeFilter.mine = e.target.checked; primesAnimate = true; renderPrimes(); });
$("#primes-refresh").addEventListener("click", e => busy(e.currentTarget, async () => {
  await api("/api/primes/refresh", { method: "POST" });
  await loadPrimes();
  toast("Данные о праймах обновлены");
}).catch(err => toast(err.message, true)));

function leftText(iso) {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "ротация сменилась";
  const m = Math.floor(ms / 60000), d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mm = m % 60;
  return d ? `${d} д ${h} ч` : h ? `${h} ч ${mm} мин` : `${mm} мин`;
}

function renderVarzia(v, primes) {
  const box = $("#varzia");
  clearInterval(countdownTimer);
  if (!v || !(v.sets || []).length) { box.hidden = true; return; }
  box.hidden = false;
  const bySlug = Object.fromEntries(primes.map(p => [p.slug, p]));
  const sets = v.sets.map(s => bySlug[s]).filter(Boolean).sort((a, b) => (a.kind === "warframe" ? 0 : 1) - (b.kind === "warframe" ? 0 : 1));
  const cd = h("span", { class: "countdown" });
  const tick = () => {
    if (!v.expiry) { cd.replaceChildren("бессрочно"); return; }
    const left = new Date(v.expiry).getTime() - Date.now();
    cd.classList.toggle("soon", left < 6 * 3600000);
    cd.replaceChildren("осталось ", h("b", {}, leftText(v.expiry)));
  };
  tick();
  countdownTimer = setInterval(tick, 30000);
  const until = v.expiry ? new Date(v.expiry).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }) : null;
  box.replaceChildren(
    h("div", { class: "varzia-head" },
      h("div", {}, h("h2", {}, "Сейчас у Варзии"), h("div", { class: "where" }, `Марс, Базар Мару — Возрождение Прайм${until ? ` · до ${until}` : ""}`)),
      cd),
    h("div", { class: "varzia-items" }, sets.map(p => h("div", { class: "vz-card", onclick: () => openItem(p.slug, null, { count: 1 }) },
      itemIcon({ thumb: p.thumb, part: "set", category: "prime" }),
      h("div", {}, h("div", { class: "nm" }, p.name.replace(/: Комплект$/, "")), h("div", { class: "sub" }, p.kind === "warframe" ? "варфрейм" : "оружие"))))),
    h("div", { class: "varzia-foot" },
      (v.relics || []).length ? h("span", {}, "Реликвии за Аю: ") : null,
      (v.relics || []).map(r => h("span", { class: "tag" }, relicLabel(r))),
      v.next && v.next.names.length ? h("span", { class: "next-up" }, "Далее: ", h("b", {}, (v.next.names_ru || v.next.names).join(" и ")), " Прайм") : null));
}

function primeCard(p, i) {
  const full = p.total_parts > 0 && p.owned_parts === p.total_parts;
  const card = h("div", { class: `prime-card st-${p.status}${primesAnimate && i < 30 ? " enter" : ""}`, title: STATUS_HINT[p.status],
    onclick: () => openItem(p.slug, null, { count: 1 }) },
    h("div", { class: "top-row" }, itemIcon({ thumb: p.thumb, part: "set", category: "prime" }),
      h("div", {}, h("div", { class: "nm" }, p.name.replace(/: Комплект$/, "")), h("div", { class: "en" }, p.name_en.replace(/ Set$/, "")))),
    h("div", { class: "meta-row" },
      h("span", { class: `status-badge ${p.status}` }, h("i"), PRIME_STATUS_RU[p.status]),
      p.evergreen ? h("span", { class: "tag", title: "Всегда есть в постоянном ассортименте Варзии" }, "у Варзии всегда") : null),
    p.total_parts ? h("div", { class: `own${full ? " full" : ""}`, title: "Сколько разных деталей этого комплекта есть в инвентаре" },
      h("span", {}, full ? "все детали есть" : `деталей: ${p.owned_parts}/${p.total_parts}`),
      h("span", { class: "bar" }, h("i", { style: `width:${Math.round((p.owned_parts / p.total_parts) * 100)}%` }))) : null,
    p.status === "active" && p.relics.length ? h("div", { class: "relic-chips", title: "Реликвии, из которых выпадают детали" },
      p.relics.slice(0, 4).map(r => h("span", { class: "tag" }, relicLabel(r))),
      p.relics.length > 4 ? h("span", { class: "tag" }, `+${p.relics.length - 4}`) : null) : null,
    h("div", { class: "price-row" }, h("span", { class: "lbl" }, "комплект на рынке"), plat(p.set_price)));
  if (primesAnimate && i < 30) card.style.setProperty("--i", i);
  return card;
}

function renderPrimes() {
  const d = primesData;
  if (!d) return;
  const f = primeFilter;
  const list = d.primes.filter(p =>
    (!f.status || p.status === f.status) && (!f.kind || p.kind === f.kind) &&
    (!f.mine || p.owned_parts > 0) &&
    (!f.q || p.name.toLowerCase().includes(f.q) || p.name_en.toLowerCase().includes(f.q)));
  $("#prime-grid").replaceChildren(...list.map(primeCard));
  primesAnimate = false;
  $("#primes-empty").hidden = d.primes.length > 0 && list.length > 0;
  $("#primes-empty").textContent = d.primes.length ? "Под фильтр ничего не подошло." : "Данные о праймах загружаются — это занимает пару секунд после запуска.";
  const counts = { active: 0, varzia: 0, vaulted: 0 };
  for (const p of d.primes) if (!f.kind || p.kind === f.kind) counts[p.status]++;
  for (const c of $$("#primes-status .chip")) {
    let n = c.querySelector(".n"); if (!n) { n = h("span", { class: "n" }); c.append(n); }
    n.textContent = c.dataset.v ? counts[c.dataset.v] : counts.active + counts.varzia + counts.vaulted;
  }
}

async function loadPrimes() {
  let d;
  try { d = await api("/api/primes"); } catch (e) { toast(e.message, true); return; }
  primesData = d;
  $("#primes-sub").textContent = "Что сейчас выпадает из реликвий, что в хранилище и что продаёт Варзия на Марсе. Данные Digital Extremes"
    + (d.updated_at ? `, обновлены ${ago(d.updated_at)}.` : ".") + (d.error ? " Последнее обновление не удалось — показаны сохранённые данные." : "");
  renderVarzia(d.varzia, d.primes);
  renderPrimes();
  if (!d.primes.length) setTimeout(() => currentTab === "primes" && loadPrimes(), 3000);
}


// ---------- ephemeras: Kuva Lich / Sister of Parvos lots ----------
const ELEMENT_RU = { electricity: "Электричество", impact: "Удар", radiation: "Радиация", magnetic: "Магнетизм",
  cold: "Холод", toxin: "Токсин", heat: "Огонь" };
const EPH_KIND_RU = { lich: "Лич Кувы", sister: "Сестра Парвос" };
const ephState = { kind: "lich", element: null, online: false, data: null, animate: true, weaponsFor: null };
const ephKey = (kind, element) => `${kind}:${element}`;

$$("#eph-kind .chip").forEach(c => c.addEventListener("click", () => {
  ephState.kind = c.dataset.v; ephState.element = null; ephState.animate = true;
  for (const x of $$("#eph-kind .chip")) x.setAttribute("aria-pressed", String(x === c));
  renderEph(); fillEphForm();
}));
$("#eph-online").addEventListener("change", e => { ephState.online = e.target.checked; renderEphLots(); });
$("#eph-clear").addEventListener("click", () => { ephState.element = null; renderEph(); });

function ephIcon(e, size) {
  const box = h("div", { class: `ico eph-ico el-${e.element}${e.thumb ? " has-img" : ""}`, style: size ? `width:${size}px;height:${size}px` : null });
  if (e.thumb) {
    const img = h("img", { src: ASSETS + e.thumb, alt: "", loading: "lazy", decoding: "async", referrerpolicy: "no-referrer" });
    img.addEventListener("load", () => img.classList.add("loaded"));
    img.addEventListener("error", () => { img.remove(); box.classList.remove("has-img"); });
    box.append(img);
  }
  box.append(h("span", { class: "fallback" }, svg("arcane")));
  return box;
}

function ephCard(e, i) {
  const selected = ephState.element === e.element;
  const card = h("button", { type: "button",
    class: `eph-card el-${e.element}${selected ? " selected" : ""}${e.count ? "" : " none"}${ephState.animate ? " enter" : ""}`,
    title: e.name_en, onclick: () => { ephState.element = selected ? null : e.element; renderEph(); } },
    h("div", { class: "eph-art" }, ephIcon(e, 64),
      e.animation ? h("img", { class: "eph-anim", src: ASSETS + e.animation, alt: "", loading: "lazy", referrerpolicy: "no-referrer" }) : null),
    h("div", { class: "eph-name" }, e.name),
    h("div", { class: "eph-el" }, h("i"), ELEMENT_RU[e.element] || e.element),
    h("div", { class: "eph-stat" },
      e.count ? [h("span", { class: "dim" }, `лотов: ${e.count} · от`), plat(e.min_price)] : h("span", { class: "dim" }, "лотов пока нет")),
    e.watched ? h("span", { class: "eph-bell", title: "Вы следите за этой эфемерой" }, svg("bell")) : null);
  if (ephState.animate) card.style.setProperty("--i", i);
  return card;
}

function ephLotRow(l) {
  const fresh = Date.now() - l.seen_at * 1000 < 60000 && l.created && Date.now() - new Date(l.created).getTime() < 30 * 60000;
  return h("div", { class: `lot eph-lot${fresh ? " new" : ""}` },
    h("div", {}, plat(l.price), fresh ? h("span", { class: "col-sub", style: "color:var(--gold)" }, "новый") : null),
    h("div", { class: "eph-lot-main" }, ephIcon({ element: l.element, thumb: l.thumb }, 36),
      h("div", {}, h("div", { class: "eph-lot-name" }, l.ephemera),
        h("div", { class: "dim" }, `${l.weapon_name}${l.damage != null ? ` · +${l.damage}% урона` : ""}`))),
    h("div", { class: "meta" },
      h("span", {}, l.created ? `выставлен ${ago(l.created)}` : `замечен ${ago(new Date(l.seen_at * 1000).toISOString())}`),
      h("span", { class: "seller" }, h("span", { class: `dot ${l.seller_status}` }), l.seller, h("span", { class: "dim" }, STATUS_RU[l.seller_status] || ""))),
    h("div", { class: "actions" }, ext(l.url, "Открыть лот на маркете")));
}

function renderEphLots() {
  const d = ephState.data;
  if (!d) return;
  const f = ephState;
  const sel = f.element ? d.summary.find(e => e.kind === f.kind && e.element === f.element) : null;
  const lots = d.lots.filter(l => l.kind === f.kind && (!f.element || l.element === f.element) && (!f.online || l.seller_status === "ingame"));
  $("#eph-lots-title").textContent = sel ? `Лоты: ${sel.name}` : `Лоты: все ${f.kind === "lich" ? "личи" : "сёстры"} с эфемерой`;
  $("#eph-clear").hidden = !sel;
  $("#eph-lots").replaceChildren(...lots.slice(0, 80).map(ephLotRow));
  $("#eph-empty").hidden = lots.length > 0;
  $("#eph-empty").textContent = d.updated_at
    ? "Подходящих лотов пока не видно. Новые появятся здесь, как только их выставят."
    : "Собираю лоты с маркета — первые появятся через несколько секунд.";
}

function renderEphWatches() {
  const d = ephState.data;
  $("#eph-watches").replaceChildren(...d.watches.map(w => h("div", { class: "eph-watch" },
    ephIcon({ element: w.element, thumb: w.thumb }, 32),
    h("div", { class: "eph-watch-text" },
      h("div", {}, h("b", {}, w.name), h("span", { class: "dim" }, ` · ${EPH_KIND_RU[w.kind]}`)),
      h("div", { class: "dim" }, [w.weapon_name || "любое оружие", w.max_price ? `до ${w.max_price} пл` : "любая цена",
        `сейчас лотов: ${w.matches}`].join(" · "))),
    w.notify ? h("span", { class: "tag sale", title: "Придёт уведомление о новом лоте" }, svg("bell"), "уведомления") : null,
    h("button", { class: "icon-btn", title: "Перестать следить", onclick: async () => {
      await api(`/api/ephemeras/watch/${w.id}`, { method: "DELETE" }); loadEphemeras();
    } }, svg("close")))));
  if (!d.watches.length) $("#eph-watches").append(h("p", { class: "dim eph-hint" },
    "Выберите эфемеру — программа пришлёт уведомление, как только кто-то выставит лича или сестру с ней."));
}

function renderEph() {
  const d = ephState.data;
  if (!d) return;
  const list = d.summary.filter(e => e.kind === ephState.kind);
  $("#eph-grid").replaceChildren(...list.map(ephCard));
  ephState.animate = false;
  renderEphLots();
  if (ephState.element) $("#eph-pick").value = ephKey(ephState.kind, ephState.element);
}

async function fillEphWeapons(kind) {
  if (ephState.weaponsFor === kind) return;
  ephState.weaponsFor = kind;
  let list = [];
  try { list = await api(`/api/ephemeras/weapons?kind=${kind}`); } catch { /* keep "любое" */ }
  $("#eph-weapon").replaceChildren(h("option", { value: "" }, "любое"), ...list.map(w => h("option", { value: w.slug }, w.name)));
}

function fillEphForm() {
  const d = ephState.data;
  if (!d) return;
  const cur = $("#eph-pick").value;
  const list = d.summary.filter(e => e.kind === ephState.kind);
  $("#eph-pick").replaceChildren(...list.map(e => h("option", { value: ephKey(e.kind, e.element) }, `${e.name} (${ELEMENT_RU[e.element] || e.element})`)));
  if (list.some(e => ephKey(e.kind, e.element) === cur)) $("#eph-pick").value = cur;
  fillEphWeapons(ephState.kind);
}

$("#eph-form").addEventListener("submit", async e => {
  e.preventDefault();
  const [kind, element] = ($("#eph-pick").value || "").split(":");
  if (!kind) return;
  const max = parseInt($("#eph-max").value, 10);
  try {
    await api("/api/ephemeras/watch", { method: "POST", body: {
      kind, element, weapon: $("#eph-weapon").value || null, max_price: Number.isFinite(max) ? max : null,
      notify: $("#eph-notify").checked } });
    $("#eph-max").value = "";
    toast("Слежу за эфемерой");
    loadEphemeras();
  } catch (err) { toast(err.message, true); }
});

async function loadEphemeras() {
  let d;
  try { d = await api("/api/ephemeras"); } catch (e) { toast(e.message, true); return; }
  const first = !ephState.data;
  ephState.data = d;
  $("#eph-sub").textContent = "Личи Кувы и Сёстры Парвос с эфемерой на warframe.market. Новые лоты ловятся из ленты маркета каждые 20 с и хранятся двое суток"
    + (d.updated_at ? `, последняя проверка ${ago(d.updated_at)}.` : ".") + (d.error ? " Последняя проверка не удалась — маркет недоступен." : "");
  renderEph();
  renderEphWatches();
  if (first || !$("#eph-pick").options.length) fillEphForm();
  if (!d.summary.length) setTimeout(() => currentTab === "ephemeras" && loadEphemeras(), 3000);
}

// ---------- quit ----------
$("#quit").addEventListener("click", async () => {
  if (!confirm("Закрыть программу? Отслеживание и уведомления остановятся.")) return;
  try { await api("/api/quit", { method: "POST" }); } catch { /* already stopping */ }
  document.body.replaceChildren(h("main", {}, h("p", { class: "empty" }, "Программа закрыта. Эту вкладку можно закрыть.")));
});

// ---------- polling / start ----------
sparkDefs();
for (const [id, icon] of [["sell-empty", "box"], ["orders-empty", "shop"], ["watch-empty", "search"],
                          ["riven-empty", "riven"], ["alerts-empty", "bell"]]) {
  const el = document.getElementById(id);
  if (el) el.prepend(svg(icon, "big"));
}
setInterval(loadStatus, 15000);
setInterval(() => currentTab === "watch" && !document.hidden && loadPrices(), 60000);
setInterval(() => currentTab === "rivens" && !document.hidden && loadRivens(), 10000);
setInterval(() => currentTab === "ephemeras" && !document.hidden && loadEphemeras(), 20000);

let startTab = "inventory";
try { startTab = localStorage.getItem("tab") || "inventory"; } catch { /* ignore */ }
loadStatus().then(() => showTab($(`.tabs button[data-tab="${startTab}"]`) ? startTab : "inventory"));
