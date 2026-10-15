// GROZ catalogue website: DOM layer. Data comes from data/catalogue.json (built from output_v2 by
// build_site_data.py); all catalogue logic lives in core.mjs. Quotations are prepared locally only.
import * as core from "./core.mjs";
import { art } from "./art.mjs";
import { icon } from "./icons.mjs";

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
  detailId: null,
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
  $("#resultCount").textContent = "Loading products…";
}

function renderError(err) {
  grid.setAttribute("aria-busy", "false");
  grid.className = "products";
  const fileProtocol = location.protocol === "file:";
  grid.innerHTML = `<div class="state" role="alert">${icon("alert", "state-icon")}<strong>The catalogue could not be loaded.</strong>
    <p>${fileProtocol ? "This page must be opened through the local server, not as a file." : esc(err?.message || "Unknown error")}</p>
    <p>From the project folder run <code>.venv/Scripts/python.exe build_site_data.py</code> and <code>python serve_site.py</code>, then open the address it prints.</p>
    <button class="btn soft" id="retryLoad" type="button">Try again</button></div>`;
  $("#resultCount").textContent = "No products loaded";
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
  // Drop saved/quoted ids that are no longer in the dataset (e.g. after a data rebuild).
  for (const id of [...state.saved]) if (!state.byId.has(id)) state.saved.delete(id);
  for (const id of [...state.quote.keys()]) if (!state.byId.has(id)) state.quote.delete(id);
  persist();
  renderHero();
  renderCategories();
  renderCatalogues();
  renderDataNote();
  setView(state.view, false);
  renderFilters();
  renderProducts();
  updateBadges();
  if ("requestIdleCallback" in window) requestIdleCallback(() => probeFrames(), { timeout: 2000 });
  else setTimeout(() => probeFrames(), 500);
}

// ---------------------------------------------------------------- static sections
function renderHero() {
  const m = state.data.meta || {};
  $("#heroStats").innerHTML = `<span><b>${state.products.length}</b> products</span><span><b>${(state.data.catalogues || []).length}</b> source catalogues</span><span><b>${m.with_confirmed_image ?? 0}</b> with catalogue images</span>`;
}

function renderCategories() {
  const cats = state.data.categories || [];
  $("#categoryGrid").innerHTML = cats.map((c) => `
    <button class="cat${state.filters.categories.has(c.name) ? " active" : ""}" type="button" data-cat="${esc(c.name)}" aria-pressed="${state.filters.categories.has(c.name)}">
      <span class="cat-art">${art(c.art)}</span><span class="cat-name">${esc(c.name)}</span><span class="cat-blurb">${esc(c.blurb || "")}</span><span class="cat-count">${plural(c.records, "product")}</span>
    </button>`).join("");
}

function renderCatalogues() {
  const list = state.data.catalogues || [];
  $("#catalogueList").innerHTML = list.map((c) => `
    <div class="catalogue-row"><div class="catalogue-info"><div class="pdf-icon">${icon("file")}</div><div><strong>${esc(c.title)}</strong>
      <small>${esc(c.category)} · ${plural(c.records, "product")} · ${esc(c.pdf)}</small></div></div>
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
  const cats = state.data.categories || [];
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
    <fieldset class="filter-group"><legend>Category</legend>${cats.map((c) =>
      option(`data-filter="category" value="${esc(c.name)}"`, f.categories.has(c.name), c.name, c.records)).join("")}</fieldset>
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
  for (const c of f.categories) chips.push(["category", c, c]);
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
  const host = img.closest("[data-id]");
  const p = host && state.byId.get(host.dataset.id);
  const holder = img.parentElement;
  img.remove();
  holder.querySelector(".img-tag")?.remove();
  holder.insertAdjacentHTML("beforeend", `${art(p ? state.artByCategory.get(p.category) : "tool")}<span class="img-tag muted">Image unavailable</span>`);
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
  return `ORD NR <b>${p.ord_nr ? esc(p.ord_nr) : "not printed"}</b> · ${esc(p.catalogue.title)}, p.&nbsp;${esc(p.printed_page ?? p.page)}`;
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
  return `<div class="empty">${icon("search", "state-icon")}<strong>No matches${q ? ` for “${esc(q)}”` : ""}.</strong>
    <p>Try a catalogue number such as <b>LED/621</b>, an order number such as <b>55044</b>, or a word such as <b>micrometer</b>${core.activeFilterCount(state.filters) > (q ? 1 : 0) ? ", or remove a filter" : ""}.</p>
    <button class="btn soft" type="button" data-reset>Reset search and filters</button></div>`;
}

/** Renders the current results. `append` adds only the next page (Show more) instead of rebuilding. */
function renderProducts({ append = false } = {}) {
  if (!state.data) return;
  if (!append) state.results = core.sortProducts(core.filterProducts(state.products, state.index, state.filters), state.sort);
  const list = state.results;
  grid.setAttribute("aria-busy", "false");
  $("#resultCount").innerHTML = `<strong>${list.length}</strong> of ${state.products.length} products`;
  if (!append) renderChips();
  if (!state.products.length || !list.length) {
    grid.className = "products";
    grid.innerHTML = state.products.length ? emptyHtml()
      : '<div class="state"><strong>No products in this catalogue yet.</strong><p>The data file loaded, but it contains no products.</p></div>';
    state.rendered = 0;
    $("#moreWrap").innerHTML = "";
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

function refresh({ resetPaging = true } = {}) {
  if (resetPaging) state.shown = core.PAGE_SIZE;
  renderProducts();
}

function setQuery(value, { scroll = false } = {}) {
  state.filters.query = value;
  if ($("#navSearch").value !== value) $("#navSearch").value = value;
  if ($("#mainSearch").value !== value) $("#mainSearch").value = value;
  refresh();
  if (scroll) scrollToEl($("#products"));
}

function updateBadges() {
  $("#savedCount").textContent = state.saved.size;
  $("#savedBtn").setAttribute("aria-label", `Saved products, ${state.saved.size} saved`);
  for (const el of $$("[data-quote-count]")) el.textContent = state.quote.size;
  $("#mobileQuoteBtn").setAttribute("aria-label", `Quote, ${plural(state.quote.size, "product")}`);
  $("#compareCount").textContent = `${state.compare.size} of ${core.MAX_COMPARE} selected to compare`;
  $("#compareBtn").disabled = state.compare.size < 2;
  const dock = state.compare.size > 0;
  $("#compareDock").classList.toggle("show", dock);
  document.body.classList.toggle("has-dock", dock);
}

// ---------------------------------------------------------------- product actions
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
  renderProducts();
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
  if (!backdrop.classList.contains("open")) {
    lastFocus = document.activeElement && document.activeElement !== document.body ? document.activeElement : lastClicked;
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
  backdrop.classList.remove("open");
  document.body.classList.remove("modal-open");
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

function showDetails(id, { focusNav = "" } = {}) {
  const p = state.byId.get(id);
  if (!p) return;
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
          <p class="pd-eyebrow">${esc(p.category)}${p.brand ? ` · ${esc(p.brand)}` : ""}</p>
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
  openModal("Saved for later", list.length ? `<div class="saved-list">${list.map((p) => `
    <div class="saved-item" data-id="${esc(p.id)}"><div class="thumb">${p.image ? `<img src="${esc(p.image.src)}" alt="" width="54" height="44"/>` : art(state.artByCategory.get(p.category))}</div>
      <div class="grow"><strong>${esc(p.cat_nr)}</strong>${titleHtml(p, "ptitle row")}<div class="sku">${skuHtml(p)}</div></div>
      <div class="acts"><button class="btn soft sm" type="button" data-saved-view="${esc(p.id)}">View</button><button class="btn ${state.quote.has(p.id) ? "in-quote" : "primary"} sm" type="button" data-saved-quote="${esc(p.id)}">${state.quote.has(p.id) ? "In quote" : "Add to quote"}</button><button class="btn danger sm" type="button" data-saved-remove="${esc(p.id)}" aria-label="Remove ${esc(p.cat_nr)} from saved">Remove</button></div></div>`).join("")}</div>
    <div class="detail-actions"><button class="btn primary" type="button" data-saved-quote-all>Add all to quote</button></div>`
    : `<div class="empty plain">${icon("heart", "state-icon")}<strong>Nothing saved yet.</strong><p>Tap the heart on a product and it will be waiting here, even after you close the page.</p></div>`, { kind: "saved" });
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
    <p class="notice ok">${icon("check")} Your quotation request is prepared. It has <b>not been sent</b> — copy it into an email, download it or print it for your GROZ sales contact.</p>
    <pre class="prepared" id="preparedText" tabindex="0" aria-label="Prepared quotation request">${esc(text)}</pre>
    <div class="detail-actions">
      <button class="btn primary" type="button" id="copyQuote" data-autofocus>${icon("copy")}Copy text</button>
      <button class="btn soft" type="button" id="dlTxt">${icon("download")}Download .txt</button>
      <button class="btn soft" type="button" id="dlCsv">${icon("download")}Download .csv</button>
      <button class="btn soft" type="button" id="printQuote">${icon("print")}Print</button>
      <button class="btn outline" type="button" id="editQuote">Edit request</button>
      <button class="btn danger" type="button" id="newQuote">Start a new quote</button>
    </div>`, { kind: "ready" });
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
    renderProducts();
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
  const onType = (e) => { clearTimeout(typing); const v = e.target.value; typing = setTimeout(() => setQuery(v), 120); };
  $("#navSearch").addEventListener("input", onType);
  $("#mainSearch").addEventListener("input", onType);
  $("#navSearchForm").addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(typing); setQuery($("#navSearch").value.trim(), { scroll: true }); $("#navSearch").blur(); });
  $("#heroSearch").addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(typing); setQuery($("#mainSearch").value.trim(), { scroll: true }); $("#mainSearch").blur(); });
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; refresh(); });
  $("#gridView").addEventListener("click", () => setView("grid"));
  $("#tableView").addEventListener("click", () => setView("table"));
  $("#clearFilters").addEventListener("click", resetFilters);
  $("#browseAll").addEventListener("click", (e) => { e.preventDefault(); resetFilters(); scrollToEl($("#products")); });

  const showCategory = (name, toggle) => {
    const f = state.filters;
    f.categories = toggle && f.categories.has(name) && f.categories.size === 1 ? new Set() : new Set([name]);
    renderCategories(); renderFilters(); refresh();
    scrollToEl($("#products"));
  };
  $("#categoryGrid").addEventListener("click", (e) => { const c = e.target.closest("[data-cat]"); if (c) showCategory(c.dataset.cat, true); });
  $("#catalogueList").addEventListener("click", (e) => { const b = e.target.closest("[data-show-cat]"); if (b) showCategory(b.dataset.showCat, false); });

  $("#filterBody").addEventListener("change", (e) => {
    const el = e.target;
    const f = state.filters;
    if (el.dataset.facet) {
      const set = f.facets.get(el.dataset.facet) || new Set();
      el.checked ? set.add(el.value) : set.delete(el.value);
      set.size ? f.facets.set(el.dataset.facet, set) : f.facets.delete(el.dataset.facet);
    } else if (el.dataset.filter === "category") {
      el.checked ? f.categories.add(el.value) : f.categories.delete(el.value);
      renderCategories();
      renderFilters();
      $(`[data-filter="category"][value="${CSS.escape(el.value)}"]`, filtersEl)?.focus();
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
    if (e.target.closest("[data-save]")) { toggleSaved(id); syncProductButtons(id); return; }
    if (e.target.closest("[data-quote]")) {
      if (state.quote.has(id)) { showQuote(); return; }
      addToQuote(id); syncProductButtons(id);
      host.querySelector("[data-quote]")?.focus({ preventScroll: true });
      return;
    }
    if (e.target.closest("[data-detail]")) showDetails(id);
  });
  grid.addEventListener("change", (e) => {
    const c = e.target.closest("[data-compare]");
    if (!c) return;
    const id = c.closest("[data-id]").dataset.id;
    if (!toggleCompare(id, c.checked)) c.checked = false;
  });
  grid.addEventListener("error", (e) => { if (e.target.tagName === "IMG") placeholderFor(e.target); }, true);
  $("#moreWrap").addEventListener("click", (e) => {
    if (!e.target.closest("#showMore")) return;
    const first = state.rendered;
    state.shown += core.PAGE_SIZE;
    renderProducts({ append: true });
    // keyboard users continue from the first newly shown product
    $$("[data-id]", grid)[first]?.querySelector(".title-btn")?.focus({ preventScroll: true });
  });

  $("#compareBtn").addEventListener("click", showCompare);
  $("#clearCompare").addEventListener("click", () => { state.compare.clear(); updateBadges(); renderProducts(); });
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
      if (backdrop.classList.contains("open")) closeModal();
      else if (filtersEl.classList.contains("open") && sheetQuery.matches) setFiltersOpen(false);
      else if (!$("#mobileMenu").hidden) { setMenuOpen(false); $("#menuBtn").focus(); }
      return;
    }
    const typing = e.target instanceof Element && e.target.closest("input,textarea,select,[contenteditable]");
    if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && state.detailId && !typing && !e.altKey && !e.ctrlKey && !e.metaKey) {
      const n = core.neighbours(state.results, state.detailId);
      const to = e.key === "ArrowLeft" ? n.prev : n.next;
      if (to) { e.preventDefault(); showDetails(to); }
      return;
    }
    trapFocus(e);
  });
  modal.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    const d = t.dataset;
    if ("detailNav" in d) { if (d.detailNav) showDetails(d.detailNav, { focusNav: t.getAttribute("aria-label") }); }
    else if (d.modalQuote) { if (state.quote.has(d.modalQuote)) showQuote(); else { addToQuote(d.modalQuote); syncProductButtons(d.modalQuote); showDetails(d.modalQuote); } }
    else if (d.modalSave) { toggleSaved(d.modalSave); syncProductButtons(d.modalSave); showDetails(d.modalSave); $(`[data-modal-save]`, modal)?.focus(); }
    else if (d.modalCompare) { if (toggleCompare(d.modalCompare, !state.compare.has(d.modalCompare))) { syncProductButtons(d.modalCompare); showDetails(d.modalCompare); $(`[data-modal-compare]`, modal)?.focus(); } }
    else if (d.uncompare) { state.compare.delete(d.uncompare); updateBadges(); syncProductButtons(d.uncompare); state.compare.size >= 2 ? showCompare() : (closeModal(), notify("Choose at least two products to compare.")); }
    else if ("quoteAll" in d) { addManyToQuote(state.compare); showQuote(); }
    else if ("clearCompare" in d) { state.compare.clear(); updateBadges(); renderProducts(); closeModal(); }
    else if (d.savedView) showDetails(d.savedView);
    else if (d.savedQuote) { addToQuote(d.savedQuote); syncProductButtons(d.savedQuote); showSaved(); }
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
    parent.insertAdjacentHTML("beforeend", art("tool"));
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
