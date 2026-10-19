// GROZ catalogue website: DOM layer. Data comes from data/catalogue.json (built from output_v2 by
// build_site_data.py); all catalogue logic lives in core.mjs. Quotations are prepared locally only.
import * as core from "./core.mjs";
import { art } from "./art.mjs";
import { icon } from "./icons.mjs";
import * as fx from "./motion.mjs";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// ---------------------------------------------------------------- persistence (per-browser convenience only)
const store = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable: keep in memory */ } },
};

const state = {
  data: null, products: [], byId: new Map(), index: new Map(), artByCategory: new Map(),
  filters: core.emptyFilters(), sort: "catalogue", view: store.get("groz.view", "grid") === "table" ? "table" : "grid",
  results: [], shown: core.PAGE_SIZE, rendered: 0, expandedFacets: new Set(),
  saved: new Set(store.get("groz.saved", [])), compare: new Set(),
  quote: new Map(store.get("groz.quote", [])), contact: { name: "", company: "", email: "", phone: "", location: "", notes: "" },
  detailId: null, unbox: null, quoteHold: 0, fxReady: false, groups: [],
};

const root = document.documentElement;
const grid = $("#productGrid");
const toastEl = $("#toast");
const backdrop = $("#backdrop");
const modal = $("#modal");
const filtersEl = $("#filters");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const sheetQuery = matchMedia("(max-width: 860px)");

// ---------------------------------------------------------------- theme (per-browser convenience only)
// The head script sets data-theme before the first paint; this keeps the buttons and the device
// setting in step. A choice is remembered only while it differs from the device setting.
const darkQuery = matchMedia("(prefers-color-scheme: dark)");
const deviceTheme = () => (darkQuery.matches ? "dark" : "light");
function applyTheme(theme) {
  root.dataset.theme = theme;
  const dark = theme === "dark";
  $('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0d0d0f" : "#f5f5f7");
  for (const b of [$("#themeBtn"), $("#themeRow")]) b?.setAttribute("aria-pressed", String(dark));
}
function toggleTheme(e) {
  const next = root.dataset.theme === "dark" ? "light" : "dark";
  if (next === deviceTheme()) { try { localStorage.removeItem("groz.theme"); } catch { /* storage unavailable */ } }
  else store.set("groz.theme", next);
  // Glass reveal: the new theme grows from the button as a soft-edged circle while the old view
  // frosts over (View Transitions API). Instant where unsupported, on low-end devices, or when
  // the visitor asks for reduced motion.
  if (!document.startViewTransition || reducedMotion.matches || root.classList.contains("lite")) { applyTheme(next); return; }
  const r = e?.currentTarget?.getBoundingClientRect?.();
  const x = r && r.width ? r.left + r.width / 2 : innerWidth - 60, y = r && r.height ? r.top + r.height / 2 : 40;
  root.style.setProperty("--vt-x", `${Math.round(x)}px`);
  root.style.setProperty("--vt-y", `${Math.round(y)}px`);
  root.style.setProperty("--vt-r", `${Math.ceil(Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)))}px`);
  root.classList.add("theme-switching");
  const t = document.startViewTransition(() => applyTheme(next));
  t.finished.finally(() => root.classList.remove("theme-switching"));
}

applyTheme(root.dataset.theme === "dark" ? "dark" : "light");

// The results bar (count, filters, sort, active filters) sticks under the header; it shows a
// hairline only while it is stuck.
(function watchResultsBar() {
  const bar = $("#resultsBar"), head = $(".top");
  if (!bar || !head || !("IntersectionObserver" in window)) return;
  let io, h = -1;
  const watch = () => {
    const nh = Math.round(head.getBoundingClientRect().height);
    if (nh === h) return;
    h = nh;
    io?.disconnect();
    io = new IntersectionObserver(([en]) => bar.classList.toggle("stuck", en.intersectionRatio < 1 && en.boundingClientRect.top <= h + 2),
      { rootMargin: `-${h + 1}px 0px 0px 0px`, threshold: [1] });
    io.observe(bar);
  };
  watch();
  addEventListener("resize", () => { clearTimeout(watch.t); watch.t = setTimeout(watch, 150); }, { passive: true });
})();
$("#themeBtn")?.addEventListener("click", toggleTheme);
$("#themeRow")?.addEventListener("click", toggleTheme);
darkQuery.addEventListener("change", () => { if (store.get("groz.theme", null) == null) applyTheme(deviceTheme()); });

function notify(message) {
  toastEl.textContent = message;
  toastEl.classList.add("show");
  clearTimeout(notify.t);
  notify.t = setTimeout(() => toastEl.classList.remove("show"), 2600);
}

function persist() {
  store.set("groz.saved", [...state.saved]);
  store.set("groz.quote", [...state.quote]);
}

function scrollToEl(el, block = "start") {
  el?.scrollIntoView({ behavior: reducedMotion.matches ? "auto" : "smooth", block });
}

// ---------------------------------------------------------------- effects budget
// Decorative effects (hero motion, blur, hover zoom) are switched off on devices that ask for less
// data, report very little memory or CPU, or measurably cannot keep up; all functions stay the same.
function enableLite(reason) {
  if (root.classList.contains("lite")) return;
  root.classList.add("lite");
  root.dataset.lite = reason;
}
(function detectLowEnd() {
  const nav = navigator;
  if (nav.connection?.saveData) enableLite("save-data");
  else if ((nav.deviceMemory && nav.deviceMemory <= 2) || (nav.hardwareConcurrency && nav.hardwareConcurrency <= 2)) enableLite("hardware");
})();

/** Measures real frame intervals for about a second (requestAnimationFrame timestamps, so 60, 90,
 *  120 and 144 Hz displays all report their own rate). Slow frames switch decorative effects off. */
function probeFrames(attempt = 1) {
  if (root.classList.contains("lite") || reducedMotion.matches || root.dataset.frameMs) return;
  const gaps = [];
  let start = 0, last = 0, done = false;
  // A hidden or throttled page produces no frames: no conclusion, try again later (a few times).
  const retry = () => { if (!done) { done = true; if (attempt < 5) setTimeout(() => probeFrames(attempt + 1), 4000); } };
  const watchdog = setTimeout(retry, 2500);
  const step = (t) => {
    if (done) return;
    if (start) gaps.push(t - last); else start = t;
    last = t;
    if (t - start < 1000 && document.visibilityState === "visible") { requestAnimationFrame(step); return; }
    clearTimeout(watchdog);
    if (gaps.length < 20) { retry(); return; }
    done = true;
    gaps.sort((a, b) => a - b);
    const median = gaps[gaps.length >> 1];
    root.dataset.frameMs = median.toFixed(2);
    if (median > 34) enableLite("slow-frames");
  };
  requestAnimationFrame(step);
}

// ---------------------------------------------------------------- loading
function renderLoading() {
  grid.className = "products";
  grid.setAttribute("aria-busy", "true");
  grid.innerHTML = Array.from({ length: 6 }, () => '<div class="skeleton" aria-hidden="true"><i></i><i></i><i></i></div>').join("");
  setCount("Loading products…");
}

function renderError(err) {
  grid.setAttribute("aria-busy", "false");
  grid.className = "products";
  const fileProtocol = location.protocol === "file:";
  grid.innerHTML = `<div class="state" role="alert">${icon("alert", "state-icon")}<strong>The catalogue could not be loaded.</strong>
    <p>${fileProtocol ? "This page must be opened through the local server, not as a file." : esc(err?.message || "Unknown error")}</p>
    <p>From the project folder run <code>.venv/Scripts/python.exe build_site_data.py</code> and <code>python serve_site.py</code>, then open the address it prints.</p>
    <button class="btn soft" id="retryLoad" type="button">Try again</button></div>`;
  setCount("No products loaded");
  $("#moreWrap").innerHTML = "";
  $("#retryLoad")?.addEventListener("click", load);
}

async function load() {
  renderLoading();
  try {
    const res = await fetch("data/catalogue.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`The data file returned HTTP ${res.status}.`);
    const data = await res.json();
    if (!data || !Array.isArray(data.products)) throw new Error("The data file is not in the expected format.");
    init(data);
  } catch (err) {
    console.error(err);
    renderError(err);
  }
}

function init(data) {
  state.data = data;
  state.products = data.products;
  state.byId = new Map(data.products.map((p) => [p.id, p]));
  state.index = core.buildIndex(data.products);
  state.artByCategory = new Map((data.categories || []).map((c) => [c.name, c.art]));
  state.groups = core.siteGroups(data.categories || []);
  // Drop saved/quoted ids that are no longer in the dataset (e.g. after a data rebuild).
  for (const id of [...state.saved]) if (!state.byId.has(id)) state.saved.delete(id);
  for (const id of [...state.quote.keys()]) if (!state.byId.has(id)) state.quote.delete(id);
  persist();
  renderHero();
  renderCategories();
  renderGroupMenus();
  renderCatalogues();
  renderDataNote();
  setView(state.view, false);
  renderFilters();
  renderProducts();
  updateBadges();
  state.fxReady = true;
  if ("requestIdleCallback" in window) requestIdleCallback(() => probeFrames(), { timeout: 2000 });
  else setTimeout(() => probeFrames(), 500);
}

// ---------------------------------------------------------------- static sections
function renderHero() {
  const m = state.data.meta || {};
  $("#heroStats").innerHTML = `<span><b>${state.products.length}</b> products</span><span><b>${(state.data.catalogues || []).length}</b> source catalogues</span><span><b>${m.with_confirmed_image ?? 0}</b> with catalogue images</span>`;
}

/** "Mechanic's Tools › Tool Storage": GROZ's category, then this site's when the names differ. */
function groupLabel(category) {
  const g = core.groupOf(category);
  return g && g.name !== category ? `${g.name} › ${category}` : category;
}

/** GROZ's categories as tiles, in GROZ's order; those not in this preview yet say "Coming soon". */
function renderCategories() {
  const f = state.filters.categories;
  $("#categoryGrid").innerHTML = state.groups.map((g) => {
    const on = !g.soon && g.categories.every((c) => f.has(c));
    return `
    <button class="cat${g.soon ? " soon" : ""}${on ? " active" : ""}" type="button" data-group="${esc(g.name)}" ${g.soon ? 'aria-disabled="true"' : `aria-pressed="${on}"`}>
      <span class="cat-art">${art(g.art)}</span><span class="cat-name">${esc(g.name)}</span><span class="cat-blurb">${esc(g.blurb)}</span><span class="cat-count">${g.soon ? "Coming soon" : plural(g.records, "product")}</span>
    </button>`;
  }).join("");
}

/** The same categories in the header's Categories menu and in the phone menu, like GROZ's own site. */
function renderGroupMenus() {
  const html = state.groups.map((g) => `<button class="group-link${g.soon ? " soon" : ""}" type="button" data-group="${esc(g.name)}"${g.soon ? ' aria-disabled="true"' : ""}>
    <span>${esc(g.name)}</span><small>${g.soon ? "Coming soon" : `${g.records}<span class="sr-only"> products</span>`}</small></button>`).join("");
  $("#catMenu").innerHTML = html;
  $("#mobileCats").innerHTML = html;
}

function renderCatalogues() {
  const list = state.data.catalogues || [];
  $("#catalogueList").innerHTML = list.map((c) => `
    <div class="catalogue-row"><div class="catalogue-info"><div class="pdf-icon">${icon("file")}</div><div><strong>${esc(c.title)}</strong>
      <small>${esc(groupLabel(c.category))} · ${plural(c.records, "product")} · ${esc(c.pdf)}</small></div></div>
      <div class="row-actions"><button class="btn soft" type="button" data-show-cat="${esc(c.category)}">Show products</button><a class="btn outline" href="${esc(c.href)}" target="_blank" rel="noopener">Open catalogue PDF ${icon("external")}<span class="sr-only">(opens in a new tab)</span></a></div></div>`).join("")
    + `<div class="catalogue-row pending"><div class="catalogue-info"><div class="pdf-icon">${icon("file")}</div><div><strong>More GROZ catalogues</strong>
      <small>Hand Tools and Fluid Handling are not in this preview yet. Their products will appear once they have been extracted and reviewed.</small></div></div></div>`;
}

function renderDataNote() {
  // Only the sentence with the counts is dynamic; the legend is static HTML (no layout shift on load).
  const m = state.data.meta || {};
  const verified = m.verified ?? state.products.filter((p) => p.status === "verified").length;
  const review = m.fields_under_review ?? 0;
  $("#dataNoteText").innerHTML = `Details are taken from the original GROZ catalogues. Check the catalogue page before ordering.${verified
    ? ` <b>${verified}</b> of ${state.products.length} products have been checked by a person and show <b>Verified</b>.` : ""}${review
    ? ` ${review} values awaiting a corrected reading are shown as <b>Under review</b>.` : ""}`;
}

// ---------------------------------------------------------------- filters
function categoryScope() {
  const f = state.filters;
  return state.products.filter((p) => !f.categories.size || f.categories.has(p.category));
}

const STATUS_LABEL = { verified: "Verified", unverified: "Not yet verified", needs_review: "Needs review" };

function renderFilters() {
  const f = state.filters;
  const soon = state.groups.filter((g) => g.soon).map((g) => g.name);
  // Specification filters are offered per category: across all categories they would be a long,
  // mixed list (beam angles next to drawer capacities).
  const groups = f.categories.size ? core.facetGroups(categoryScope()) : [];
  for (const [key, values] of [...f.facets]) {
    if (!groups.some((g) => g.key === key) && values.size) f.facets.delete(key);
  }
  const count = (pred) => state.products.filter(pred).length;
  const statusCounts = core.STATUS_ORDER.map((s) => [s, count((p) => p.status === s)]).filter(([, n]) => n > 0);
  const option = (attrs, checked, label, n) =>
    `<label class="filter-option"><input type="checkbox" ${attrs} ${checked ? "checked" : ""}/><span>${esc(label)}</span><span class="n">${n}</span></label>`;
  const facetHtml = groups.map((g) => {
    const selected = f.facets.get(g.key) || new Set();
    const expanded = state.expandedFacets.has(g.key);
    const values = expanded ? g.values : g.values.slice(0, 6);
    return `<fieldset class="filter-group"><legend>${esc(g.label)}</legend>${values.map((v) =>
      option(`data-facet="${esc(g.key)}" value="${esc(v.value)}"`, selected.has(v.value), v.value, v.count)).join("")}
      ${g.values.length > 6 ? `<button class="filter-more" type="button" data-expand="${esc(g.key)}" aria-expanded="${expanded}">${expanded ? "Show fewer" : `Show all ${g.values.length}`}</button>` : ""}</fieldset>`;
  }).join("");
  $("#filterBody").innerHTML = `
    <fieldset class="filter-group"><legend>Category</legend>${state.groups.filter((g) => !g.soon).map((g) =>
      option(`data-filter="group" value="${esc(g.name)}"`, g.categories.every((c) => f.categories.has(c)), g.name, g.records)).join("")}
      ${soon.length ? `<p class="filter-hint soon-hint">Coming soon: ${esc(soon.join(", "))}.</p>` : ""}</fieldset>
    ${facetHtml || (f.categories.size ? "" : `<div class="filter-group"><p class="filter-hint">Choose a category to filter by its specifications.</p></div>`)}
    <fieldset class="filter-group"><legend>Images</legend>${option('data-filter="image"', f.withImage, "Only with a catalogue image", count((p) => !!p.image))}</fieldset>
    <fieldset class="filter-group"><legend>Review status</legend>${statusCounts.map(([s, n]) =>
      option(`data-filter="status" value="${s}"`, f.statuses.has(s), STATUS_LABEL[s], n)).join("")}
      ${option('data-filter="notes"', f.withNotes, "Has a catalogue review note", count((p) => p.notes.length > 0))}</fieldset>`;
}

function renderChips() {
  const f = state.filters;
  const chips = [];
  if (f.query.trim()) chips.push(["query", "", `Search: “${f.query.trim()}”`]);
  for (const c of f.categories) {
    const g = state.groups.find((x) => x.categories.includes(c));
    chips.push(["category", c, g?.categories.length === 1 ? g.name : groupLabel(c)]);
  }
  for (const [key, values] of f.facets) {
    const label = state.products.find((p) => p.specs.some((s) => s.key === key))?.specs.find((s) => s.key === key)?.label || key;
    for (const v of values) chips.push([`facet:${key}`, v, `${label}: ${v}`]);
  }
  if (f.withImage) chips.push(["image", "", "With catalogue image"]);
  for (const s of f.statuses) chips.push(["status", s, STATUS_LABEL[s]]);
  if (f.withNotes) chips.push(["notes", "", "Has review note"]);
  $("#activeChips").innerHTML = chips.map(([type, value, label]) =>
    `<button class="chip" type="button" data-chip="${esc(type)}" data-value="${esc(value)}" aria-label="Remove filter: ${esc(label)}"><span>${esc(label)}</span>${icon("x")}</button>`).join("")
    + (chips.length > 1 ? '<button class="chip clear" type="button" data-chip="all">Clear all</button>' : "");
  const n = core.activeFilterCount(f);
  $("#filterBadge").textContent = n ? String(n) : "";
  $("#filterBadge").hidden = !n;
}

function resetFilters() {
  state.filters = core.emptyFilters();
  $("#navSearch").value = "";
  $("#mainSearch").value = "";
  state.shown = core.PAGE_SIZE;
  renderCategories();
  renderFilters();
  renderProducts();
}

// ---------------------------------------------------------------- products
function imageHtml(p) {
  const st = core.imageState(p);
  if (p.image) {
    const tag = st.kind === "family" ? `<span class="img-tag">${st.label}</span>` : "";
    return `<img src="${esc(p.image.src)}" alt="Catalogue image for ${esc(p.cat_nr)}${st.kind === "family" ? " (product family)" : ""}" loading="lazy" decoding="async" width="200" height="150"/>${tag}`;
  }
  return `${art(state.artByCategory.get(p.category))}<span class="img-tag muted">${st.label}</span>`;
}

function placeholderFor(img) {
  // The record has a picture, so a failed load (server stopped, connection lost) is not "Image
  // unavailable": try once more, then say the picture did not load.
  if (!img.dataset.retried) {
    img.dataset.retried = "1";
    const src = img.getAttribute("src");
    setTimeout(() => { if (img.isConnected) img.src = `${src}${src.includes("?") ? "&" : "?"}retry=${Date.now()}`; }, 1500);
    return;
  }
  const host = img.closest("[data-id]");
  const p = host && state.byId.get(host.dataset.id);
  const holder = img.parentElement;
  img.remove();
  holder.querySelector(".img-tag")?.remove();
  holder.insertAdjacentHTML("beforeend", `${art(p ? state.artByCategory.get(p.category) : "tool")}<span class="img-tag muted">Picture didn't load</span>`);
}

/** Status badges. Quiet (cards, table rows): no badge for products nobody has checked yet; the
 *  catalogue note says so once, and the product details always show the status. */
function statusHtml(p, { quiet = false } = {}) {
  const n = p.under_review.length;
  return (quiet && p.status === "unverified" ? "" : `<span class="status status-${esc(p.status)}">${esc(p.status_label)}</span>`)
    + (n ? `<span class="flag flag-review" title="A corrected reading is awaiting approval">${plural(n, "value")} under review</span>` : "")
    + (p.notes.length ? `<span class="flag flag-note" title="This product has a catalogue review note">Review note</span>` : "");
}

function skuHtml(p) {
  // The source is its own span so narrow cards can put it on its own line (site.css).
  return `ORD NR <b>${p.ord_nr ? esc(p.ord_nr) : "not printed"}</b><span class="sku-sep"> · </span><span class="sku-src">${esc(p.catalogue.title)}, p.&nbsp;${esc(p.printed_page ?? p.page)}</span>`;
}

function titleHtml(p, cls = "ptitle") {
  const t = core.displayTitle(p);
  return t ? `<p class="${cls}">${esc(t)}</p>` : `<p class="${cls} muted">${esc(p.category)}</p>`;
}

function compareHtml(p) {
  return `<label class="compare-check"><input type="checkbox" data-compare ${state.compare.has(p.id) ? "checked" : ""}/><span>Compare</span></label>`;
}

function quoteBtnHtml(p) {
  const inQ = state.quote.has(p.id);
  return `<button class="btn ${inQ ? "in-quote" : "primary"}" type="button" data-quote>${inQ ? `${icon("check")} In quote` : "Add to quote"}</button>`;
}

function cardHtml(p) {
  const saved = state.saved.has(p.id);
  const specs = core.summarySpecs(p, 2);
  const label = [p.cat_nr, core.displayTitle(p)].filter(Boolean).join(", ");
  const badges = statusHtml(p, { quiet: true });
  return `<article class="product" data-id="${esc(p.id)}">
    <button class="product-image" type="button" data-detail aria-label="View details for ${esc(label)}">${imageHtml(p)}</button>
    <button class="heart${saved ? " saved" : ""}" type="button" data-save aria-pressed="${saved}" aria-label="Save ${esc(p.cat_nr)}">${icon("heart")}</button>
    ${badges ? `<div class="card-badges">${badges}</div>` : ""}
    ${titleHtml(p)}
    <h3><button class="title-btn" type="button" data-detail>${esc(p.cat_nr || "No catalogue number")}</button></h3>
    <div class="sku">${skuHtml(p)}</div>
    <dl class="spec">${specs.length ? specs.map((s) => `<div><dt>${esc(s.label)}</dt><dd>${esc(s.value)}</dd></div>`).join("") : '<div><dt>Specifications</dt><dd class="v-missing">See details</dd></div>'}</dl>
    <div class="product-actions">${quoteBtnHtml(p)}${compareHtml(p)}</div>
  </article>`;
}

function rowHtml(p) {
  return `<tr data-id="${esc(p.id)}">
      <td><button class="thumb" type="button" data-detail aria-label="View details for ${esc(p.cat_nr)}">${p.image ? `<img src="${esc(p.image.src)}" alt="" loading="lazy" decoding="async" width="54" height="44"/>` : art(state.artByCategory.get(p.category))}</button></td>
      <td><button class="title-btn code" type="button" data-detail>${esc(p.cat_nr)}</button>${titleHtml(p, "ptitle row")}</td>
      <td>${p.ord_nr ? esc(p.ord_nr) : '<span class="muted">Not printed</span>'}</td>
      <td class="hide-sm">${core.summarySpecs(p, 2).map((s) => `${esc(s.label)}: <b>${esc(s.value)}</b>`).join("<br/>") || '<span class="muted">See details</span>'}</td>
      <td class="hide-sm">${esc(p.catalogue.title)}<br/><span class="muted">printed p. ${esc(p.printed_page ?? "—")}</span></td>
      <td class="hide-md">${statusHtml(p, { quiet: true })}</td>
      <td class="actions">${quoteBtnHtml(p)}${compareHtml(p)}</td>
    </tr>`;
}

function tableHtml(list) {
  return `<div class="ptable-wrap" tabindex="0" aria-label="Products table"><table class="ptable"><thead><tr><th scope="col"><span class="sr-only">Image</span></th><th scope="col">Product</th><th scope="col">ORD NR</th>
    <th scope="col" class="hide-sm">Key specifications</th><th scope="col" class="hide-sm">Source</th><th scope="col" class="hide-md">Status</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
    <tbody id="ptableBody">${list.map(rowHtml).join("")}</tbody></table></div>`;
}

function emptyHtml() {
  const q = state.filters.query.trim();
  const nq = core.norm(q);
  const soon = nq.length > 2 && state.groups.find((g) => g.soon && (core.norm(g.name).includes(nq) || nq.includes(core.norm(g.name))));
  return `<div class="empty">${icon("search", "state-icon")}<strong>No matches${q ? ` for “${esc(q)}”` : ""}.</strong>
    ${soon ? `<p><b>${esc(soon.name)}</b> is coming soon: its products are not in this preview yet.</p>` : ""}
    <p>Try a catalogue number such as <b>LED/621</b>, an order number such as <b>55044</b>, or a word such as <b>micrometer</b>${core.activeFilterCount(state.filters) > (q ? 1 : 0) ? ", or remove a filter" : ""}.</p>
    <button class="btn soft" type="button" data-reset>Reset search and filters</button></div>`;
}

/** The results count. Screen readers get the plain sentence (a polite live region); the visible copy,
 *  hidden from them, counts its number up or down to the new total (motion.mjs). */
function setCount(text, n = null, total = 0) {
  $("#countLive").textContent = text;
  const shown = $("#countShown");
  const num = $(".n", shown);
  if (n == null) { shown.textContent = text; delete shown.dataset.total; return; }
  if (num && shown.dataset.total === String(total)) { fx.countTo(num, n); return; }
  shown.innerHTML = `<strong class="n">${n}</strong> of ${total} products`;
  shown.dataset.total = String(total);
}

/** Renders the current results. `append` adds only the next page (Show more) instead of rebuilding.
 *  New cards come in with motion: `typing` makes that a short fade, `quiet` (a rebuild that only
 *  refreshes buttons) shows them at once. */
function renderProducts({ append = false, typing = false, quiet = false } = {}) {
  if (!state.data) return;
  if (!append) state.results = core.sortProducts(core.filterProducts(state.products, state.index, state.filters), state.sort);
  const list = state.results;
  grid.setAttribute("aria-busy", "false");
  setCount(`${list.length} of ${state.products.length} products`, list.length, state.products.length);
  if (!append) renderChips();
  if (!state.products.length || !list.length) {
    grid.className = "products";
    grid.innerHTML = state.products.length ? emptyHtml()
      : '<div class="state"><strong>No products in this catalogue yet.</strong><p>The data file loaded, but it contains no products.</p></div>';
    state.rendered = 0;
    $("#moreWrap").innerHTML = "";
    fx.cascade([]);
    return;
  }
  const from = append ? state.rendered : 0;
  const page = list.slice(from, state.shown);
  if (state.view === "table") {
    const body = append && $("#ptableBody", grid);
    if (body) body.insertAdjacentHTML("beforeend", page.map(rowHtml).join(""));
    else { grid.className = "products-table"; grid.innerHTML = tableHtml(page); }
  } else if (append && grid.className === "products") {
    grid.insertAdjacentHTML("beforeend", page.map(cardHtml).join(""));
  } else {
    grid.className = "products";
    grid.innerHTML = page.map(cardHtml).join("");
  }
  state.rendered = from + page.length;
  const remaining = list.length - state.rendered;
  $("#moreWrap").innerHTML = remaining > 0
    ? `<button class="btn outline" type="button" id="showMore">Show ${Math.min(remaining, core.PAGE_SIZE)} more <span class="muted-on">· ${remaining} remaining</span></button>` : "";
  fx.cascade(state.view === "grid" && !quiet ? $$(".product", grid).slice(from) : [], { fresh: !append, quick: typing });
}

function setView(view, rerender = true) {
  state.view = view;
  store.set("groz.view", view);
  for (const [id, v] of [["#gridView", "grid"], ["#tableView", "table"]]) {
    $(id).classList.toggle("active", view === v);
    $(id).setAttribute("aria-pressed", String(view === v));
  }
  if (rerender) renderProducts();
}

function refresh({ resetPaging = true, typing = false } = {}) {
  if (resetPaging) state.shown = core.PAGE_SIZE;
  renderProducts({ typing });
}

function setQuery(value, { scroll = false, typing = false } = {}) {
  state.filters.query = value;
  if ($("#navSearch").value !== value) $("#navSearch").value = value;
  if ($("#mainSearch").value !== value) $("#mainSearch").value = value;
  refresh({ typing });
  if (scroll) scrollToEl($("#products"));
}

function updateBadges() {
  setBadge($("#savedCount"), state.saved.size);
  $("#savedBtn").setAttribute("aria-label", `Saved products, ${state.saved.size} saved`);
  // While a picture is flying into the Quote button, its count changes as it lands.
  if (!state.quoteHold) for (const el of $$("[data-quote-count]")) setBadge(el, state.quote.size);
  $("#mobileQuoteBtn").setAttribute("aria-label", `Quote, ${plural(state.quote.size, "product")}`);
  $("#compareCount").textContent = `${state.compare.size} of ${core.MAX_COMPARE} selected to compare`;
  $("#compareBtn").disabled = state.compare.size < 2;
  const dock = state.compare.size > 0;
  $("#compareDock").classList.toggle("show", dock);
  document.body.classList.toggle("has-dock", dock);
}

/** Sets a count badge; after the first render, a new number rolls in and the badge pops. */
function setBadge(el, n) {
  const old = Number(el.textContent);
  if (el.textContent === String(n)) return;
  el.textContent = String(n);
  if (state.fxReady) { fx.roll(el, n > old); fx.pop(el, 1.25); }
}

// ---------------------------------------------------------------- product actions
/** Tosses the product picture into the visible Quote button; the quote count changes as it lands. */
function tossToQuote(src) {
  const target = [$("#navQuote"), $("#mobileQuoteBtn")].find((b) => b?.getClientRects().length);
  state.quoteHold += 1;
  fx.flyTo(src, target, () => { state.quoteHold -= 1; updateBadges(); });
}

function toggleSaved(id) {
  if (state.saved.has(id)) { state.saved.delete(id); notify("Removed from saved"); }
  else { state.saved.add(id); notify("Saved for later"); }
  persist();
  updateBadges();
}

function toggleCompare(id, on) {
  if (on && !state.compare.has(id) && state.compare.size >= core.MAX_COMPARE) {
    notify(`You can compare up to ${core.MAX_COMPARE} products at a time.`);
    return false;
  }
  on ? state.compare.add(id) : state.compare.delete(id);
  updateBadges();
  return true;
}

function addToQuote(id) {
  const p = state.byId.get(id);
  if (!p) return;
  if (state.quote.has(id)) { notify(`${p.cat_nr} is already in your quote — set the quantity there.`); return; }
  state.quote.set(id, 1);
  persist();
  updateBadges();
  notify(`${p.cat_nr} added to your quote`);
}

function addManyToQuote(ids) {
  let added = 0;
  for (const id of ids) if (state.byId.has(id) && !state.quote.has(id)) { state.quote.set(id, 1); added += 1; }
  persist();
  updateBadges();
  renderProducts({ quiet: true });
  return added;
}

/** Updates one product's buttons in place (no list rebuild). */
function syncProductButtons(id) {
  const p = state.byId.get(id);
  for (const el of $$(`[data-id="${CSS.escape(id)}"]`, grid)) {
    const q = el.querySelector("[data-quote]");
    if (q && p) q.outerHTML = quoteBtnHtml(p);
    const h = el.querySelector("[data-save]");
    if (h) { const sv = state.saved.has(id); h.classList.toggle("saved", sv); h.setAttribute("aria-pressed", String(sv)); }
    const c = el.querySelector("[data-compare]");
    if (c) c.checked = state.compare.has(id);
  }
}

// ---------------------------------------------------------------- modal
let lastFocus = null;
let lastClicked = null; // fallback when a click does not move focus (e.g. some browsers, scripted clicks)
document.addEventListener("click", (e) => { const b = e.target.closest("button,a"); if (b && !modal.contains(b)) lastClicked = b; }, true);

function openModal(title, html, { wide = false, kind = "", tools = "" } = {}) {
  stopUnbox();
  if (!backdrop.classList.contains("open")) {
    lastFocus = document.activeElement && document.activeElement !== document.body ? document.activeElement : lastClicked;
    // Locking the page hides its scrollbar (Windows); keep that space so the page does not reflow.
    const bar = innerWidth - root.clientWidth;
    if (bar > 0) document.body.style.paddingRight = `${bar}px`;
  }
  state.detailId = null;
  modal.dataset.kind = kind;
  $("#modalTitle").textContent = title;
  $("#modalTools").innerHTML = tools;
  $("#modalBody").innerHTML = html;
  modal.classList.toggle("wide", wide);
  backdrop.classList.add("open");
  document.body.classList.add("modal-open");
  modal.scrollTop = 0;
  ($("[data-autofocus]", modal) || $("#modalClose")).focus({ preventScroll: true });
}

function closeModal() {
  if (!backdrop.classList.contains("open")) return;
  stopUnbox();
  backdrop.classList.remove("open");
  document.body.classList.remove("modal-open");
  document.body.style.paddingRight = "";
  state.detailId = null;
  if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
}

function focusTrapContainer() {
  if (backdrop.classList.contains("open")) return modal;
  if (filtersEl.classList.contains("open") && sheetQuery.matches) return filtersEl;
  return null;
}

function trapFocus(e) {
  const box = e.key === "Tab" && focusTrapContainer();
  if (!box) return;
  const items = $$('button,a[href],input,select,textarea,summary,[tabindex]:not([tabindex="-1"])', box)
    .filter((el) => !el.disabled && el.getClientRects().length);
  if (!items.length) return;
  const first = items[0], last = items[items.length - 1];
  if (e.shiftKey && (document.activeElement === first || !box.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && (document.activeElement === last || !box.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
}

function valueCell(r) {
  if (r.state === "missing") return `<span class="v-missing">Not specified</span>`;
  if (r.state === "review") return `<span class="v-review" title="A corrected reading of this value is awaiting approval">Under review</span>`;
  return esc(r.text);
}

/** Who checked this product against its page, if anyone (from the verification tool's ledger). */
function reviewLine(p) {
  const v = p.verification;
  const when = v ? String(v.at || "").slice(0, 10) : "";
  if (v?.state === "verified") return `Review status: <b>Verified</b> — checked against the catalogue page by ${esc(v.reviewer)} on ${esc(when)}.`;
  if (v?.state === "flagged") return `Review status: <b>Needs review</b> — flagged by ${esc(v.reviewer)} on ${esc(when)} (see the review note above).`;
  return `Review status: <b>${esc(p.status_label)}</b>. Values were extracted automatically; check the catalogue page before ordering.`;
}

const RELATION_NOTE = {
  cleaned: "The extracted heading also contains description text printed next to the title.",
  expanded: "The extracted heading misses part of the printed title.",
  different: "The extracted heading names another product or section of the page (awaiting an extraction fix, decision F).",
  added: "No heading was extracted for this product.",
};

// ---------------------------------------------------------------- unboxing
// Opening a product from its card plays one continuous 3D unboxing: the picture tile becomes a GROZ
// carton that tilts toward the viewer and opens its flaps, the product rises out and flies to its
// place in the details, and the key specifications fly out of the box into their rows.
// The details are built and measured before the first frame, and every movement runs on the one
// Web Animations timeline (transform and opacity only), so nothing is laid out, swapped in late or
// replayed while it moves. Skipped for reduced motion, on low-end devices, in Table view, for cards
// off screen, and while the dialog is open (Previous/Next, Save, Compare).
const UNBOX = { lift: 480, rise: 280, out: 660, fly: 460, specs: 720, step: 35, spec: 440, settle: 150, max: 8 };
const EASE_OUT = "cubic-bezier(.2,.8,.2,1)";

function unboxThenShow(card, id) {
  const tile = card.querySelector(".product-image");
  const r = tile?.getBoundingClientRect();
  const still = !tile || !r || !tile.animate || reducedMotion.matches || root.classList.contains("lite")
    || backdrop.classList.contains("open") || r.bottom < 0 || r.top > innerHeight;
  showDetails(id);
  if (still || state.detailId !== id) return;
  try { playUnbox(tile, r); } catch { stopUnbox(); }
}

function playUnbox(tile, r) {
  const stage = $(".pd-stage", modal);
  if (!stage) return;
  // This replaces the dialog's own entrance (pop or sheet, fade-ins). A cancelled CSS animation stays
  // cancelled until the dialog next opens, so nothing replays when the unboxing ends.
  cancelEntrance();
  modal.classList.add("unboxing");
  const T = UNBOX;
  const sr = stage.getBoundingClientRect(), mr = modal.getBoundingClientRect();
  // A carton's proportions, centred on the picture tile (wide tiles would make a flat slab).
  const h = r.height, w = Math.min(r.width, Math.round(h * 1.25)), d = Math.round(Math.min(w, h) * 0.55);
  const left = r.left + (r.width - w) / 2;
  const mouth = { x: left + w / 2, y: r.top + h * 0.25 }; // where things come out of the box
  const layer = document.createElement("div");
  layer.className = "unbox";
  layer.setAttribute("aria-hidden", "true");
  layer.innerHTML = `<div class="ub-stage" style="left:${left}px;top:${r.top}px;width:${w}px;height:${h}px;--d:${d}px;--h:${h}px">
      <div class="ub-box"><div class="ub-face ub-back"></div><div class="ub-face ub-left"></div><div class="ub-face ub-right"></div>
      <div class="ub-glow"></div><div class="ub-face ub-front"><span class="brand-mark">G</span><span>GROZ</span></div>
      <div class="ub-flap ub-flap-f"></div><div class="ub-flap ub-flap-b"></div></div></div>`;
  const boxStage = layer.firstElementChild, box = boxStage.firstElementChild;
  const u = { layer, tile, anims: [], tileAnim: null };
  state.unbox = u;

  // The product in the box and the product that flies to the details are copies of the details
  // picture itself, so the hand-overs between them, and to the real picture, cannot be seen.
  const copy = (cls) => {
    const el = stage.cloneNode(true);
    el.classList.add(cls);
    el.style.width = `${sr.width}px`;
    el.style.height = `${sr.height}px`;
    $$("img", el).forEach((img) => { img.alt = ""; img.removeAttribute("loading"); });
    return el;
  };
  const item = copy("ub-item");
  const k = Math.min((w * 0.72) / sr.width, (h * 0.8) / sr.height);
  item.style.left = `${(w - sr.width) / 2}px`;
  item.style.top = `${(h - sr.height) / 2}px`;
  box.insertBefore(item, $(".ub-front", box));
  const fly = copy("ub-fly");
  fly.style.left = `${sr.left}px`;
  fly.style.top = `${sr.top}px`;
  layer.appendChild(fly);
  document.body.appendChild(layer);

  const turn = "rotateY(18deg) rotateX(-24deg)"; // undoes the box's tilt: the product faces the viewer
  const boxStart = "translateY(0px) translateZ(0px) rotateX(0deg) rotateY(0deg) scale(.94)";
  const boxEnd = `translateY(${h * 0.12}px) translateZ(10px) rotateX(24deg) rotateY(-18deg) scale(.86)`;
  const itemStart = `translateZ(${-d / 2}px) translateY(${h * 0.2}px) ${turn} scale(${k * 0.85})`;
  const itemEnd = `translateZ(${d * 0.3}px) translateY(${-(h * 0.5 + sr.height * k * 0.6)}px) ${turn} scale(${k})`;
  // Where the product is when it has left the box: measured once, before anything is drawn.
  box.style.transform = boxEnd;
  item.style.transform = itemEnd;
  const ir = item.getBoundingClientRect();
  box.style.transform = item.style.transform = "";

  const run = (el, frames, opts) => {
    const a = el.animate(frames, { fill: "backwards", ...opts });
    u.anims.push(a);
    return a;
  };
  u.tileAnim = tile.animate({ opacity: [1, 0] }, { duration: 160, fill: "forwards" });
  // 1. The carton lifts and tilts, the flaps open, light comes from inside. Opacity is only ever
  //    animated on the carton's holder: on the carton itself it would flatten the 3D faces.
  run(boxStage, { opacity: [0, 1] }, { duration: 150 });
  run(box, { transform: [boxStart, boxEnd] }, { duration: T.lift, easing: EASE_OUT, fill: "both" });
  run($(".ub-flap-f", box), { transform: ["rotateX(-90deg)", "rotateX(-300deg)"] },
    { delay: 140, duration: 400, easing: "cubic-bezier(.3,.7,.2,1.1)", fill: "both" });
  run($(".ub-flap-b", box), { transform: [`translateZ(${-d}px) rotateX(90deg)`, `translateZ(${-d}px) rotateX(212deg)`] },
    { delay: 190, duration: 400, easing: "cubic-bezier(.3,.7,.2,1.1)", fill: "both" });
  run($(".ub-glow", box), { opacity: [0, 1] }, { delay: 200, duration: 300, fill: "both" });
  // 2. The product rises out of the box...
  run(item, [{ opacity: 0, transform: itemStart }, { opacity: 1, offset: 0.25 }, { opacity: 1, transform: itemEnd }],
    { delay: T.rise, duration: T.out - T.rise, easing: "cubic-bezier(.2,.7,.3,1)", fill: "both" });
  run(item, { opacity: [0, 0] }, { delay: T.out, duration: 1, fill: "forwards" });
  // 3. ...and its copy flies from there to the picture in the details, while the box sinks away and
  //    the details grow from it. The real picture shows the moment the copy lands on it.
  const land = T.out + T.fly;
  run(fly, { opacity: [0, 0] }, { duration: T.out });
  run(fly, { transform: [`translate(${ir.left - sr.left}px, ${ir.top - sr.top}px) scale(${ir.width / sr.width})`, "translate(0px, 0px) scale(1)"] },
    { delay: T.out, duration: T.fly, easing: "cubic-bezier(.45,0,.2,1)" });
  run(fly, { opacity: [0, 0] }, { delay: land, duration: 1, fill: "forwards" });
  run(stage, { opacity: [0, 0] }, { duration: land });
  run(boxStage, { opacity: [1, 0], transform: ["translateY(0px) scale(1)", "translateY(16px) scale(.94)"] },
    { delay: T.out + 40, duration: 260, easing: "cubic-bezier(.4,0,1,1)", fill: "forwards" });

  // 4. The key specifications fly out of the box, one after another, and settle into their rows.
  //    Each is a copy of its row; the row's own text appears under it as it lands.
  const seen = (el) => { const b = el.getBoundingClientRect(); return b.bottom > mr.top + 8 && b.top < mr.bottom - 8; };
  const cells = [...$$(".pd-facts > div", modal), ...$$(".pd-specs > div", modal)].filter(seen).slice(0, T.max);
  const arc = CSS.supports?.("translate", "1px 1px");
  cells.forEach((cell, i) => {
    const cr = cell.getBoundingClientRect();
    const group = document.createElement("dl");
    group.className = `${cell.parentElement.className} ub-ghosts`;
    const ghost = cell.cloneNode(true);
    ghost.style.cssText = `left:${cr.left}px;top:${cr.top}px;width:${cr.width}px;height:${cr.height}px`;
    group.appendChild(ghost);
    layer.appendChild(group);
    const dx = mouth.x - (cr.left + cr.width / 2), dy = mouth.y - (cr.top + cr.height / 2);
    const at = T.specs + i * T.step, lands = at + T.spec;
    if (arc) {
      // Sideways and vertical motion follow different curves, so each spec leaves the box in an arc.
      run(ghost, { translate: [`${dx}px 0px`, "0px 0px"] }, { delay: at, duration: T.spec, easing: "cubic-bezier(.5,0,.3,1)" });
      run(ghost, { opacity: [0, 1, 1], transform: [`translateY(${dy}px) scale(.2)`, "translateY(0px) scale(1)"] },
        { delay: at, duration: T.spec, easing: "cubic-bezier(.2,.75,.3,1)" });
    } else {
      run(ghost, { opacity: [0, 1, 1], transform: [`translate(${dx}px, ${dy}px) scale(.2)`, "translate(0px, 0px) scale(1)"] },
        { delay: at, duration: T.spec, easing: EASE_OUT });
    }
    run(ghost, { opacity: [1, 0] }, { delay: lands, duration: T.settle, fill: "forwards" });
    [...cell.children].forEach((c) => run(c, { opacity: [0, 0] }, { duration: lands }));
  });
  // The details grow from the box. Started last: its starting scale would shrink every rect measured.
  modal.style.transformOrigin = `${mouth.x - mr.left}px ${mouth.y - mr.top}px`;
  run(modal, { opacity: [0, 1], transform: ["scale(.94)", "scale(1)"] }, { delay: T.out - 60, duration: 420, easing: EASE_OUT });
  Promise.all(u.anims.map((a) => a.finished)).then(() => { if (state.unbox === u) endUnbox(u, true); }, () => {});
  // Safety net: a page that stops drawing frames (a hidden tab) still ends up showing the details.
  const total = Math.max(...u.anims.map((a) => a.effect.getComputedTiming().endTime));
  u.timer = setTimeout(() => { if (state.unbox === u) endUnbox(u, true); }, total + 1000);
}

/** Removes the unboxing layer; the dialog is left exactly as it looks without it. */
function endUnbox(u, settled) {
  state.unbox = null;
  clearTimeout(u.timer);
  u.anims.forEach((a) => a.cancel());
  u.layer.remove();
  u.tileAnim?.cancel();
  if (settled && u.tile.isConnected) u.tile.animate({ opacity: [0, 1] }, { duration: 220 });
  modal.classList.remove("unboxing");
  modal.style.transformOrigin = "";
}

function stopUnbox() {
  if (state.unbox) endUnbox(state.unbox, false);
}

/** Cancels the dialog's CSS entrance (pop or sheet, the details' fade-up and picture fade). */
function cancelEntrance() {
  if (typeof CSSAnimation !== "function") return;
  modal.getAnimations({ subtree: true }).forEach((a) => { if (a instanceof CSSAnimation) a.cancel(); });
}

function showDetails(id, { focusNav = "", dir = 0, still = false } = {}) {
  const p = state.byId.get(id);
  if (!p) return;
  // Previous/Next: keep the old picture, so it can swing out while the new one swings in.
  const oldPic = dir && state.detailId ? $(".pd-stage > img, .pd-stage > svg", modal) : null;
  const rows = core.detailRows(p);
  const facts = core.summarySpecs(p, 4);
  const inQ = state.quote.has(p.id), saved = state.saved.has(p.id), cmp = state.compare.has(p.id);
  const st = core.imageState(p);
  const title = core.displayTitle(p);
  const image = p.image ? `<img src="${esc(p.image.src)}" alt="Catalogue image for ${esc(p.cat_nr)}"/>` : art(state.artByCategory.get(p.category));
  const evidence = p.image
    ? `<b>${esc(p.image.evidence_label)}.</b>${p.image.evidence_detail ? ` Why this image: ${esc(p.image.evidence_detail)}.` : ""}`
    : st.kind === "unconfirmed"
      ? "<b>Image not confirmed.</b> The catalogue page has a picture near this product, but nothing links it to this product specifically, so it is not shown. The illustration is a category icon."
      : "<b>Image unavailable.</b> No product picture was found for this product. The illustration is a category icon.";
  const nav = core.neighbours(state.results, p.id);
  const tools = nav.index >= 0 && nav.total > 1 ? `<div class="pd-nav" role="group" aria-label="Browse results">
      <button class="round-btn" type="button" data-detail-nav="${esc(nav.prev ?? "")}" ${nav.prev ? "" : "disabled"} aria-label="Previous product">${icon("left")}</button>
      <span class="detail-pos" aria-live="polite">${nav.index + 1} of ${nav.total}</span>
      <button class="round-btn" type="button" data-detail-nav="${esc(nav.next ?? "")}" ${nav.next ? "" : "disabled"} aria-label="Next product">${icon("right")}</button></div>` : "";
  const notes = p.notes.length ? `<div class="review-notes"><h4>Catalogue review note${p.notes.length > 1 ? "s" : ""}</h4>${p.notes.map((n) => `
      <p><b>${esc(n.field)}</b> — printed value: <code>${esc(n.published_value)}</code> (${esc(n.status)})<br/>${esc(n.issue)}</p>`).join("")}</div>` : "";
  const reviewList = p.under_review.length
    ? `<p class="pd-callout"><b>Under review:</b> ${p.under_review.map((u) => esc(u.label)).join(", ")} — a corrected reading of ${p.under_review.length > 1 ? "these values is" : "this value is"} awaiting approval, so ${p.under_review.length > 1 ? "they are" : "it is"} not shown.</p>` : "";
  const headingNote = p.heading && p.heading_relation !== "same"
    ? `<p><b>Heading as extracted</b>: “${esc(p.heading)}”. ${esc(RELATION_NOTE[p.heading_relation] || "")}</p>`
    : !p.heading && title ? `<p>${esc(RELATION_NOTE.added)}</p>` : "";
  const tag = st.kind === "family" ? '<span class="img-tag">Family image</span>' : "";
  openModal("Product details", `
    <article class="pd">
      <div class="pd-hero">
        <figure class="pd-media">
          <div class="pd-stage">${image}${tag}</div>
          <figcaption class="pd-caption">${icon("info")}<span>${evidence}</span></figcaption>
        </figure>
        <div class="pd-copy">
          <p class="pd-eyebrow">${esc(groupLabel(p.category))}${p.brand ? ` · ${esc(p.brand)}` : ""}</p>
          <h2 class="pd-code" id="detailCode">${esc(p.cat_nr || "No catalogue number")}</h2>
          ${title ? `<p class="pd-title">${esc(title)}</p>` : ""}
          <p class="pd-meta">${skuHtml(p)}</p>
          <div class="pd-status">${statusHtml(p)}</div>
          ${facts.length ? `<dl class="pd-facts">${facts.map((f) => `<div><dt>${esc(f.label)}</dt><dd>${esc(f.value)}</dd></div>`).join("")}</dl>` : ""}
          <div class="pd-actions">
            <button class="btn ${inQ ? "in-quote" : "primary"} pd-primary" type="button" data-modal-quote="${esc(p.id)}" data-autofocus>${inQ ? `${icon("check")} In quote — view quote` : "Add to quote"}</button>
            <div class="pd-secondary">
              <button class="btn soft" type="button" data-modal-save="${esc(p.id)}" aria-pressed="${saved}">${icon("heart", saved ? "filled" : "")}${saved ? "Saved" : "Save"}</button>
              <button class="btn soft" type="button" data-modal-compare="${esc(p.id)}" aria-pressed="${cmp}">${icon(cmp ? "check" : "compare")}${cmp ? "Comparing" : "Compare"}</button>
            </div>
            <a class="pd-link" href="${esc(p.catalogue.href)}" target="_blank" rel="noopener">View the catalogue page ${icon("external")}<span class="sr-only">(opens the PDF in a new tab)</span></a>
          </div>
        </div>
      </div>
      ${reviewList}${notes}
      <section class="pd-section" aria-labelledby="pdSpecsTitle">
        <h3 id="pdSpecsTitle">Specifications</h3>
        <dl class="pd-specs">${rows.map((r) => `<div><dt>${esc(r.label)}</dt><dd>${valueCell(r)}</dd></div>`).join("")}</dl>
      </section>
      <section class="pd-section" aria-labelledby="pdSourceTitle">
        <h3 id="pdSourceTitle">From the catalogue</h3>
        <div class="pd-source">
          <p><b>Source</b>: ${esc(p.catalogue.title)} — printed page ${esc(p.printed_page ?? "not printed")} (PDF page ${p.page}), file <code>${esc(p.catalogue.pdf)}</code>.</p>
          ${title && p.title_source ? `<p><b>Printed title</b>: ${esc(p.title_source.evidence)}</p>` : ""}${headingNote}
          ${p.source_row_text ? `<p><b>Catalogue table row</b> (text as extracted):</p><pre>${esc(p.source_row_text)}</pre>` : ""}
          <p class="source-foot">${reviewLine(p)}</p>
        </div>
      </section>
    </article>`, { wide: true, kind: "detail", tools });
  state.detailId = p.id;
  // Shown again in place (Save, Compare, Add to quote) or stepped to: the opening fade does not replay.
  if (dir || still) cancelEntrance();
  if (dir) fx.carousel($(".pd-stage", modal), oldPic, dir, [$(".pd-copy", modal), $(".pd-caption", modal)]);
  if (focusNav) $(`[data-detail-nav][aria-label="${focusNav}"]`, modal)?.focus({ preventScroll: true });
}

function showCompare() {
  const list = [...state.compare].map((id) => state.byId.get(id)).filter(Boolean);
  if (list.length < 2) { notify("Choose at least two products to compare."); return; }
  const rows = core.compareRows(list);
  openModal("Compare your shortlist", `
    <div class="table-scroll" tabindex="0" aria-label="Comparison table, scrolls sideways"><table class="compare-table"><thead><tr><th scope="col">Specification</th>${list.map((p) => `
      <th scope="col"><div class="compare-head"><span class="code">${esc(p.cat_nr)}</span><span class="sku">${esc(core.displayTitle(p) || p.category)}</span>
      <button class="remove" type="button" data-uncompare="${esc(p.id)}" aria-label="Remove ${esc(p.cat_nr)} from comparison">${icon("x")}Remove</button></div></th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr><th scope="row">${esc(r.label)}</th>${r.cells.map((c) => `<td>${valueCell(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    <p class="evidence">“Not specified” means the catalogue table for that product does not print the value. “Under review” values await a corrected reading.</p>
    <div class="detail-actions"><button class="btn primary" type="button" data-quote-all data-autofocus>Add all to quote</button><button class="btn soft" type="button" data-clear-compare>Clear comparison</button></div>`, { wide: true, kind: "compare" });
}

function showSaved() {
  const list = [...state.saved].map((id) => state.byId.get(id)).filter(Boolean);
  const entering = !backdrop.classList.contains("open") || modal.dataset.kind !== "saved";
  openModal("Saved for later", list.length ? `<div class="saved-list">${list.map((p) => `
    <div class="saved-item" data-id="${esc(p.id)}"><div class="thumb">${p.image ? `<img src="${esc(p.image.src)}" alt="" width="54" height="44"/>` : art(state.artByCategory.get(p.category))}</div>
      <div class="grow"><strong>${esc(p.cat_nr)}</strong>${titleHtml(p, "ptitle row")}<div class="sku">${skuHtml(p)}</div></div>
      <div class="acts"><button class="btn soft sm" type="button" data-saved-view="${esc(p.id)}">View</button><button class="btn ${state.quote.has(p.id) ? "in-quote" : "primary"} sm" type="button" data-saved-quote="${esc(p.id)}">${state.quote.has(p.id) ? "In quote" : "Add to quote"}</button><button class="btn danger sm" type="button" data-saved-remove="${esc(p.id)}" aria-label="Remove ${esc(p.cat_nr)} from saved">Remove</button></div></div>`).join("")}</div>
    <div class="detail-actions"><button class="btn primary" type="button" data-saved-quote-all>Add all to quote</button></div>`
    : `<div class="empty plain">${icon("heart", "state-icon")}<strong>Nothing saved yet.</strong><p>Tap the heart on a product and it will be waiting here, even after you close the page.</p></div>`, { kind: "saved" });
  if (entering) fx.stagger($$(".saved-item", modal));
}

// ---------------------------------------------------------------- quotation (local preparation only)
function quoteItems() {
  return [...state.quote].map(([id, qty]) => ({ id, qty })).filter((i) => state.byId.has(i.id));
}

/** Quantities as typed (a half-typed value is reported as invalid, never silently replaced). */
function typedQuoteItems() {
  return quoteItems().map((i) => ({ id: i.id, qty: $(`[data-qty="${CSS.escape(i.id)}"]`, modal)?.value ?? i.qty }));
}

function quoteItemsHtml() {
  const items = quoteItems();
  if (!items.length) return `<div class="empty plain"><strong>Your quote is empty.</strong><p>Use “Add to quote” on any product, or add your saved or compared products.</p>
    <div class="detail-actions center">${state.saved.size ? '<button class="btn soft" type="button" data-quote-saved>Add saved products</button>' : ""}${state.compare.size ? '<button class="btn soft" type="button" data-quote-compared>Add compared products</button>' : ""}</div></div>`;
  return `<table class="quote-table"><thead><tr><th scope="col">Product</th><th scope="col">ORD NR</th><th scope="col">Quantity</th><th scope="col"><span class="sr-only">Remove</span></th></tr></thead><tbody>
    ${items.map(({ id, qty }) => { const p = state.byId.get(id); return `<tr data-qid="${esc(id)}">
      <td class="q-product"><button class="title-btn" type="button" data-quote-view="${esc(id)}"><b>${esc(p.cat_nr)}</b></button><div class="sku">${esc(core.displayTitle(p) || p.category)}</div></td>
      <td class="q-ord"><span class="q-label">ORD NR </span>${p.ord_nr ? esc(p.ord_nr) : '<span class="v-missing">Not printed</span>'}</td>
      <td class="q-qty"><div class="stepper"><button class="step" type="button" data-step="-1" data-step-id="${esc(id)}" aria-label="Decrease quantity for ${esc(p.cat_nr)}">${icon("minus")}</button><input class="qty" type="text" inputmode="numeric" pattern="[0-9]*" autocomplete="off" value="${esc(qty)}" data-qty="${esc(id)}" aria-label="Quantity for ${esc(p.cat_nr)}" aria-describedby="qtyerr-${esc(id)}"/><button class="step" type="button" data-step="1" data-step-id="${esc(id)}" aria-label="Increase quantity for ${esc(p.cat_nr)}">${icon("plus")}</button></div><div class="err" id="qtyerr-${esc(id)}"></div></td>
      <td class="q-remove"><button class="btn danger sm" type="button" data-quote-remove="${esc(id)}" aria-label="Remove ${esc(p.cat_nr)} from quote">Remove</button></td></tr>`; }).join("")}</tbody></table>`;
}

function totalsHtml(items = quoteItems()) {
  const t = core.quoteTotals(items);
  return `<span>Products: <b>${t.lines}</b></span><span>Total units: <b>${t.units}</b></span>${t.invalid ? `<span class="v-review">${t.invalid} quantit${t.invalid > 1 ? "ies need" : "y needs"} fixing</span>` : ""}`;
}

function field(id, label, { type = "text", required = false, full = false, area = false, autocomplete = "", inputmode = "" } = {}) {
  const value = esc(state.contact[id] ?? "");
  const input = area
    ? `<textarea id="q-${id}" name="${id}" rows="3" placeholder="Model variants, delivery timing, anything else…">${value}</textarea>`
    : `<input id="q-${id}" name="${id}" type="${type}" value="${value}" ${required ? 'required aria-required="true"' : ""} ${autocomplete ? `autocomplete="${autocomplete}"` : ""} ${inputmode ? `inputmode="${inputmode}"` : ""} aria-describedby="err-${id}"/>`;
  return `<div class="field${full ? " full" : ""}"><label for="q-${id}">${label}${required ? ' <span aria-hidden="true">*</span>' : ""}</label>${input}<div class="err" id="err-${id}"></div></div>`;
}

function showQuote() {
  const entering = !backdrop.classList.contains("open") || modal.dataset.kind !== "quote";
  openModal("Let’s build your quote", `
    <p class="notice">This prepares a quotation request on your device. <b>Nothing is sent</b> — when it is ready you can copy, download or print it for your GROZ sales contact.</p>
    <div id="quoteItems">${quoteItemsHtml()}</div><div class="err" id="err-items" tabindex="-1"></div>
    <div class="quote-totals" id="quoteTotals" aria-live="polite">${totalsHtml()}</div>
    <form class="form-grid" id="quoteForm" novalidate>
      ${field("name", "Full name", { required: true, autocomplete: "name" })}
      ${field("company", "Company", { autocomplete: "organization" })}
      ${field("email", "Work email", { type: "email", required: true, autocomplete: "email", inputmode: "email" })}
      ${field("phone", "Phone", { type: "tel", autocomplete: "tel", inputmode: "tel" })}
      ${field("location", "Delivery location", { full: true, autocomplete: "address-level2" })}
      ${field("notes", "What else should we know?", { full: true, area: true })}
      <div class="field full form-foot"><button class="btn primary lg" type="submit">Prepare request</button><small>Fields marked * are required. Nothing is sent.</small></div>
    </form>`, { kind: "quote" });
  if (entering) fx.stagger($$("#quoteItems tbody tr", modal));
}

function refreshQuoteItems() {
  const box = $("#quoteItems");
  if (box) box.innerHTML = quoteItemsHtml();
  const t = $("#quoteTotals");
  if (t) t.innerHTML = totalsHtml();
}

function submitQuote(form) {
  for (const el of form.elements) if (el.name) state.contact[el.name] = el.value;
  const items = typedQuoteItems();
  const errors = core.validateQuote(items, state.contact);
  $$(".err", modal).forEach((e) => { e.textContent = ""; });
  $$("[aria-invalid]", modal).forEach((e) => e.removeAttribute("aria-invalid"));
  for (const [key, msg] of Object.entries(errors)) {
    if (key.startsWith("qty:")) {
      const id = key.slice(4);
      $(`[data-qty="${CSS.escape(id)}"]`, modal)?.setAttribute("aria-invalid", "true");
      const e = document.getElementById(`qtyerr-${id}`);
      if (e) e.textContent = msg;
    } else {
      const e = document.getElementById(`err-${key}`);
      if (e) e.textContent = msg;
      $(`#q-${key}`)?.setAttribute("aria-invalid", "true");
    }
  }
  if (Object.keys(errors).length) {
    const first = $("[aria-invalid='true']", modal) || $("#err-items");
    first?.focus();
    first?.scrollIntoView({ block: "center", behavior: reducedMotion.matches ? "auto" : "smooth" });
    notify(`Please check ${plural(Object.keys(errors).length, "highlighted field")}.`);
    return;
  }
  const when = new Date();
  const text = core.quoteText(items, state.byId, state.contact, when);
  const csv = core.quoteCsv(items, state.byId);
  const stamp = when.toISOString().slice(0, 10);
  openModal("Your request is ready", `
    <p class="notice ok">${icon("check")}<span>Your quotation request is prepared. It has <b>not been sent</b> — copy it into an email, download it or print it for your GROZ sales contact.</span></p>
    <div class="paper"><span class="slot" aria-hidden="true"></span><pre class="prepared" id="preparedText" tabindex="0" aria-label="Prepared quotation request">${esc(text)}</pre><span class="stamp" aria-hidden="true">Ready · not sent</span></div>
    <div class="detail-actions">
      <button class="btn primary" type="button" id="copyQuote" data-autofocus>${icon("copy")}Copy text</button>
      <button class="btn soft" type="button" id="dlTxt">${icon("download")}Download .txt</button>
      <button class="btn soft" type="button" id="dlCsv">${icon("download")}Download .csv</button>
      <button class="btn soft" type="button" id="printQuote">${icon("print")}Print</button>
      <button class="btn outline" type="button" id="editQuote">Edit request</button>
      <button class="btn danger" type="button" id="newQuote">Start a new quote</button>
    </div>`, { kind: "ready" });
  fx.printOut($(".paper", modal));
  $("#copyQuote").onclick = async () => {
    try { await navigator.clipboard.writeText(text); notify("Request copied to the clipboard"); }
    catch { selectText($("#preparedText")); notify("Copy blocked by the browser — the text is selected, press Ctrl+C."); }
  };
  $("#dlTxt").onclick = () => download(`groz-quote-request-${stamp}.txt`, text, "text/plain");
  $("#dlCsv").onclick = () => download(`groz-quote-request-${stamp}.csv`, "﻿" + csv, "text/csv");
  $("#printQuote").onclick = () => printText(text);
  $("#editQuote").onclick = showQuote;
  $("#newQuote").onclick = () => {
    if (!confirm("Clear the products in your quote? Your contact details stay filled in.")) return;
    state.quote.clear();
    persist();
    updateBadges();
    renderProducts({ quiet: true });
    showQuote();
  };
}

function selectText(el) {
  const r = document.createRange();
  r.selectNodeContents(el);
  const sel = getSelection();
  sel.removeAllRanges();
  sel.addRange(r);
}

function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type: `${type};charset=utf-8` }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  notify(`Downloaded ${name}`);
}

function printText(text) {
  $("#printArea").textContent = text;
  document.body.classList.add("print-quote");
  const done = () => { document.body.classList.remove("print-quote"); window.removeEventListener("afterprint", done); };
  window.addEventListener("afterprint", done);
  window.print();
  setTimeout(done, 1000);
}

function stepQty(id, delta) {
  const input = $(`[data-qty="${CSS.escape(id)}"]`, modal);
  if (!input) return;
  const n = core.parseQty(input.value);
  input.value = String(Math.min(core.MAX_QTY, Math.max(1, (n ?? (delta > 0 ? 0 : 2)) + delta)));
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

// ---------------------------------------------------------------- events
function setMenuOpen(open) {
  $("#mobileMenu").hidden = !open;
  $("#menuBtn").setAttribute("aria-expanded", String(open));
  $("#menuBtn").setAttribute("aria-label", open ? "Close menu" : "Open menu");
}

function setFiltersOpen(open, { restoreFocus = true } = {}) {
  const sheet = sheetQuery.matches;
  filtersEl.classList.toggle("open", open);
  $("#sheetScrim").hidden = !(open && sheet);
  document.body.classList.toggle("sheet-open", open && sheet);
  $("#filtersToggle").setAttribute("aria-expanded", String(open));
  if (open && sheet) {
    filtersEl.setAttribute("role", "dialog");
    filtersEl.setAttribute("aria-modal", "true");
    $("#filtersClose").focus();
  } else {
    filtersEl.removeAttribute("role");
    filtersEl.removeAttribute("aria-modal");
    if (!open && sheet && restoreFocus) $("#filtersToggle").focus({ preventScroll: true });
  }
}

function wire() {
  let typing;
  const onType = (e) => { clearTimeout(typing); const v = e.target.value; typing = setTimeout(() => setQuery(v, { typing: true }), 120); };
  $("#navSearch").addEventListener("input", onType);
  $("#mainSearch").addEventListener("input", onType);
  $("#navSearchForm").addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(typing); setQuery($("#navSearch").value.trim(), { scroll: true }); $("#navSearch").blur(); });
  $("#heroSearch").addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(typing); setQuery($("#mainSearch").value.trim(), { scroll: true }); $("#mainSearch").blur(); });
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; refresh(); });
  $("#gridView").addEventListener("click", () => setView("grid"));
  $("#tableView").addEventListener("click", () => setView("table"));
  $("#clearFilters").addEventListener("click", resetFilters);
  $("#browseAll").addEventListener("click", (e) => { e.preventDefault(); resetFilters(); scrollToEl($("#products")); });

  const showCategories = (cats, toggle) => {
    const f = state.filters;
    const same = cats.length === f.categories.size && cats.every((c) => f.categories.has(c));
    f.categories = toggle && same ? new Set() : new Set(cats);
    renderCategories(); renderFilters(); refresh();
    scrollToEl($("#products"));
  };
  // A GROZ category: its products, or a note that it is not in this preview yet.
  const openGroup = (name, toggle) => {
    const g = state.groups.find((x) => x.name === name);
    if (!g) return;
    if (g.soon) notify(`${g.name} is coming soon: its products are not in this preview yet.`);
    else showCategories(g.categories, toggle);
  };
  $("#categoryGrid").addEventListener("click", (e) => { const c = e.target.closest("[data-group]"); if (c) openGroup(c.dataset.group, true); });
  $("#catalogueList").addEventListener("click", (e) => { const b = e.target.closest("[data-show-cat]"); if (b) showCategories([b.dataset.showCat], false); });

  // Header Categories menu (desktop) and the category list in the phone menu.
  const catMenu = $("#catMenu"), catBtn = $("#catMenuBtn");
  const setCatMenu = (open) => { catMenu.hidden = !open; catBtn.setAttribute("aria-expanded", String(open)); };
  catBtn.addEventListener("click", (e) => {
    setCatMenu(catMenu.hidden);
    if (!catMenu.hidden && e.detail === 0) $("button", catMenu)?.focus(); // opened from the keyboard
  });
  catMenu.addEventListener("click", (e) => { const b = e.target.closest("[data-group]"); if (b) { setCatMenu(false); openGroup(b.dataset.group, false); } });
  document.addEventListener("click", (e) => { if (!catMenu.hidden && !e.target.closest(".nav-cats")) setCatMenu(false); });
  document.addEventListener("focusin", (e) => { if (!catMenu.hidden && !e.target.closest(".nav-cats")) setCatMenu(false); });
  $("#mobileCats").addEventListener("click", (e) => { const b = e.target.closest("[data-group]"); if (b) { setMenuOpen(false); openGroup(b.dataset.group, false); } });

  $("#filterBody").addEventListener("change", (e) => {
    const el = e.target;
    const f = state.filters;
    if (el.dataset.facet) {
      const set = f.facets.get(el.dataset.facet) || new Set();
      el.checked ? set.add(el.value) : set.delete(el.value);
      set.size ? f.facets.set(el.dataset.facet, set) : f.facets.delete(el.dataset.facet);
    } else if (el.dataset.filter === "group") {
      const g = state.groups.find((x) => x.name === el.value);
      for (const c of g?.categories || []) el.checked ? f.categories.add(c) : f.categories.delete(c);
      renderCategories();
      renderFilters();
      $(`[data-filter="group"][value="${CSS.escape(el.value)}"]`, filtersEl)?.focus();
    } else if (el.dataset.filter === "image") f.withImage = el.checked;
    else if (el.dataset.filter === "status") el.checked ? f.statuses.add(el.value) : f.statuses.delete(el.value);
    else if (el.dataset.filter === "notes") f.withNotes = el.checked;
    refresh();
  });
  $("#filterBody").addEventListener("click", (e) => {
    const b = e.target.closest("[data-expand]");
    if (!b) return;
    const k = b.dataset.expand;
    state.expandedFacets.has(k) ? state.expandedFacets.delete(k) : state.expandedFacets.add(k);
    renderFilters();
    $(`[data-expand="${CSS.escape(k)}"]`, filtersEl)?.focus();
  });
  $("#activeChips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-chip]");
    if (!b) return;
    const f = state.filters, type = b.dataset.chip, value = b.dataset.value;
    if (type === "all") { resetFilters(); $("#resultCount").focus?.(); return; }
    if (type === "query") setQuery("");
    else {
      if (type === "category") { f.categories.delete(value); renderCategories(); }
      else if (type === "image") f.withImage = false;
      else if (type === "status") f.statuses.delete(value);
      else if (type === "notes") f.withNotes = false;
      else if (type.startsWith("facet:")) { const k = type.slice(6); f.facets.get(k)?.delete(value); if (!f.facets.get(k)?.size) f.facets.delete(k); }
      renderFilters();
      refresh();
    }
    // keep keyboard focus in the chip row after the removed chip disappears
    ($("#activeChips .chip") || $("#sort")).focus({ preventScroll: true });
  });

  grid.addEventListener("click", (e) => {
    if (e.target.closest("[data-reset]")) return resetFilters();
    const host = e.target.closest("[data-id]");
    if (!host) return;
    const id = host.dataset.id;
    if (e.target.closest("[data-save]")) {
      toggleSaved(id); syncProductButtons(id);
      fx.burst(host.querySelector("[data-save]"), state.saved.has(id));
      return;
    }
    if (e.target.closest("[data-quote]")) {
      if (state.quote.has(id)) { showQuote(); return; }
      tossToQuote(host.querySelector(".product-image > img, .product-image > svg, .thumb > img, .thumb > svg"));
      addToQuote(id); syncProductButtons(id);
      const b = host.querySelector("[data-quote]");
      b?.focus({ preventScroll: true });
      fx.drawCheck(b);
      return;
    }
    if (e.target.closest("[data-detail]")) unboxThenShow(host, id);
  });
  grid.addEventListener("change", (e) => {
    const c = e.target.closest("[data-compare]");
    if (!c) return;
    const host = c.closest("[data-id]");
    const dock = $("#compareDock"), docked = dock.classList.contains("show");
    if (!toggleCompare(host.dataset.id, c.checked)) { c.checked = false; return; }
    // The first pick slides the compare bar up by itself; later picks fly into it.
    if (c.checked && docked) fx.flyTo(host.querySelector(".product-image > img, .product-image > svg, .thumb > img, .thumb > svg"), dock);
  });
  grid.addEventListener("error", (e) => { if (e.target.tagName === "IMG") placeholderFor(e.target); }, true);
  fx.tilt(grid, ".product");
  // Hero: a spotlight and a lean that follow the mouse. The hammer strikes when clicked, and once by
  // itself when the page is first opened in a visit (remembered for the visit only).
  const heroTool = $(".hero-tool");
  const strikeHammer = () => fx.strike(heroTool, { onImpact: () => fx.nudge($(".hero-visual")) });
  fx.heroFollow($(".hero"), { tool: heroTool, orbit: $(".orbit") });
  heroTool?.addEventListener("click", strikeHammer);
  let struck = false;
  try { struck = sessionStorage.getItem("groz.struck") === "1"; } catch { /* storage unavailable */ }
  if (heroTool && !struck) setTimeout(() => {
    const r = heroTool.getBoundingClientRect();
    if (document.visibilityState !== "visible" || r.bottom < 0 || r.top > innerHeight) return;
    try { sessionStorage.setItem("groz.struck", "1"); } catch { /* storage unavailable */ }
    strikeHammer();
  }, 1500);
  fx.wordsIn($$(".hero h1, .section-head h2, .quote-card h3"));
  fx.tilt($("#categoryGrid"), ".cat:not(.soon)", { max: 8, lift: -4 });
  $("#moreWrap").addEventListener("click", (e) => {
    if (!e.target.closest("#showMore")) return;
    const first = state.rendered;
    state.shown += core.PAGE_SIZE;
    renderProducts({ append: true });
    // keyboard users continue from the first newly shown product
    $$("[data-id]", grid)[first]?.querySelector(".title-btn")?.focus({ preventScroll: true });
  });

  $("#compareBtn").addEventListener("click", showCompare);
  $("#clearCompare").addEventListener("click", () => { state.compare.clear(); updateBadges(); renderProducts({ quiet: true }); });
  const openQuote = () => { setMenuOpen(false); showQuote(); };
  for (const id of ["#navQuote", "#bannerQuote", "#mobileQuote", "#mobileQuoteBtn"]) $(id).addEventListener("click", openQuote);
  $("#savedBtn").addEventListener("click", () => { setMenuOpen(false); showSaved(); });
  $("#menuBtn").addEventListener("click", () => setMenuOpen($("#mobileMenu").hidden));
  $("#mobileMenu").addEventListener("click", (e) => { if (e.target.closest("a")) setMenuOpen(false); });

  $("#filtersToggle").addEventListener("click", () => setFiltersOpen(!filtersEl.classList.contains("open")));
  $("#filtersClose").addEventListener("click", () => setFiltersOpen(false));
  $("#sheetScrim").addEventListener("click", () => setFiltersOpen(false));
  $("#filtersDone").addEventListener("click", () => { setFiltersOpen(false, { restoreFocus: false }); scrollToEl($("#products")); $("#resultCount").focus?.({ preventScroll: true }); });
  sheetQuery.addEventListener?.("change", () => { if (filtersEl.classList.contains("open")) setFiltersOpen(false, { restoreFocus: false }); });

  // modal content actions (delegated)
  $("#modalClose").addEventListener("click", closeModal);
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) closeModal(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!catMenu.hidden) { setCatMenu(false); catBtn.focus(); }
      else if (backdrop.classList.contains("open")) closeModal();
      else if (filtersEl.classList.contains("open") && sheetQuery.matches) setFiltersOpen(false);
      else if (!$("#mobileMenu").hidden) { setMenuOpen(false); $("#menuBtn").focus(); }
      return;
    }
    const typing = e.target instanceof Element && e.target.closest("input,textarea,select,[contenteditable]");
    if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && state.detailId && !typing && !e.altKey && !e.ctrlKey && !e.metaKey) {
      const n = core.neighbours(state.results, state.detailId);
      const to = e.key === "ArrowLeft" ? n.prev : n.next;
      if (to) { e.preventDefault(); showDetails(to, { dir: e.key === "ArrowLeft" ? -1 : 1 }); }
      return;
    }
    trapFocus(e);
  });
  modal.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    const d = t.dataset;
    if ("detailNav" in d) {
      const label = t.getAttribute("aria-label");
      if (d.detailNav) showDetails(d.detailNav, { focusNav: label, dir: label === "Previous product" ? -1 : 1 });
    } else if (d.modalQuote) {
      if (state.quote.has(d.modalQuote)) showQuote();
      else {
        tossToQuote($(".pd-stage > img, .pd-stage > svg", modal));
        addToQuote(d.modalQuote); syncProductButtons(d.modalQuote); showDetails(d.modalQuote, { still: true });
        fx.drawCheck($("[data-modal-quote]", modal));
      }
    } else if (d.modalSave) {
      toggleSaved(d.modalSave); syncProductButtons(d.modalSave); showDetails(d.modalSave, { still: true });
      const b = $("[data-modal-save]", modal);
      b?.focus();
      fx.burst(b?.querySelector("svg"), state.saved.has(d.modalSave));
    }
    else if (d.modalCompare) { if (toggleCompare(d.modalCompare, !state.compare.has(d.modalCompare))) { syncProductButtons(d.modalCompare); showDetails(d.modalCompare, { still: true }); $(`[data-modal-compare]`, modal)?.focus(); } }
    else if (d.uncompare) { state.compare.delete(d.uncompare); updateBadges(); syncProductButtons(d.uncompare); state.compare.size >= 2 ? showCompare() : (closeModal(), notify("Choose at least two products to compare.")); }
    else if ("quoteAll" in d) { addManyToQuote(state.compare); showQuote(); }
    else if ("clearCompare" in d) { state.compare.clear(); updateBadges(); renderProducts({ quiet: true }); closeModal(); }
    else if (d.savedView) showDetails(d.savedView);
    else if (d.savedQuote) {
      if (!state.quote.has(d.savedQuote)) tossToQuote(t.closest(".saved-item")?.querySelector(".thumb > img, .thumb > svg"));
      addToQuote(d.savedQuote); syncProductButtons(d.savedQuote); showSaved();
    }
    else if (d.savedRemove) { state.saved.delete(d.savedRemove); persist(); updateBadges(); syncProductButtons(d.savedRemove); showSaved(); }
    else if ("savedQuoteAll" in d) { addManyToQuote(state.saved); showQuote(); }
    else if (d.quoteRemove) { state.quote.delete(d.quoteRemove); persist(); updateBadges(); syncProductButtons(d.quoteRemove); refreshQuoteItems(); ($("[data-qty]", modal) || $("#q-name"))?.focus(); }
    else if (d.quoteView) showDetails(d.quoteView);
    else if ("quoteSaved" in d) { addManyToQuote(state.saved); refreshQuoteItems(); }
    else if ("quoteCompared" in d) { addManyToQuote(state.compare); refreshQuoteItems(); }
    else if (d.step) stepQty(d.stepId, Number(d.step));
  });
  modal.addEventListener("input", (e) => {
    const q = e.target.closest("[data-qty]");
    if (q) {
      const n = core.parseQty(q.value);
      if (n != null) { state.quote.set(q.dataset.qty, n); persist(); q.removeAttribute("aria-invalid"); const err = document.getElementById(`qtyerr-${q.dataset.qty}`); if (err) err.textContent = ""; }
      else q.setAttribute("aria-invalid", "true");
      $("#quoteTotals").innerHTML = totalsHtml(typedQuoteItems());
      return;
    }
    if (e.target.form?.id === "quoteForm" && e.target.name) {
      state.contact[e.target.name] = e.target.value;
      if (e.target.getAttribute("aria-invalid")) { e.target.removeAttribute("aria-invalid"); const err = document.getElementById(`err-${e.target.name}`); if (err) err.textContent = ""; }
    }
  });
  modal.addEventListener("submit", (e) => {
    if (e.target.id !== "quoteForm") return;
    e.preventDefault();
    submitQuote(e.target);
  });
  modal.addEventListener("error", (e) => {
    if (e.target.tagName !== "IMG") return;
    const parent = e.target.parentElement;
    e.target.remove();
    parent.insertAdjacentHTML("beforeend", `${art("tool")}${parent.classList.contains("pd-stage") ? '<span class="img-tag muted">Picture didn\'t load</span>' : ""}`);
  }, true);

  // Entrance effects and the hero's looping motion only run while visible (IntersectionObserver),
  // so nothing animates off screen.
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => es.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } }), { threshold: 0.08 });
    $$(".reveal").forEach((el) => io.observe(el));
    const hero = $(".hero");
    new IntersectionObserver(([en]) => hero.classList.toggle("paused", !en.isIntersecting)).observe(hero);
  } else {
    $$(".reveal").forEach((el) => el.classList.add("in"));
  }
}

wire();
load();
