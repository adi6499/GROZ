// GROZ catalogue website: DOM layer. Data comes from data/catalogue.json (built from output_v2 by
// build_site_data.py); all catalogue logic lives in core.mjs. Quotations are prepared locally only.
import * as core from "./core.mjs";
import { art } from "./art.mjs";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---------------------------------------------------------------- persistence (per-browser convenience only)
const store = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable: keep in memory */ } },
};

const state = {
  data: null, products: [], byId: new Map(), index: new Map(), artByCategory: new Map(),
  filters: core.emptyFilters(), sort: "catalogue", view: store.get("groz.view", "grid") === "table" ? "table" : "grid",
  shown: core.PAGE_SIZE, expandedFacets: new Set(),
  saved: new Set(store.get("groz.saved", [])), compare: new Set(),
  quote: new Map(store.get("groz.quote", [])), contact: { name: "", company: "", email: "", phone: "", location: "", notes: "" },
};

const grid = $("#productGrid");
const toastEl = $("#toast");
const backdrop = $("#backdrop");
const modal = $("#modal");

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

// ---------------------------------------------------------------- loading
function renderLoading() {
  grid.className = "products";
  grid.setAttribute("aria-busy", "true");
  grid.innerHTML = Array.from({ length: 6 }, () => '<div class="skeleton" aria-hidden="true"><i></i><i></i><i></i></div>').join("");
  $("#resultCount").innerHTML = "Loading products…";
}

function renderError(err) {
  grid.setAttribute("aria-busy", "false");
  const fileProtocol = location.protocol === "file:";
  grid.innerHTML = `<div class="state" role="alert"><div style="font-size:28px">⚠︎</div><strong>The catalogue could not be loaded.</strong>
    <p>${fileProtocol ? "This page must be opened through the local server, not as a file." : esc(err?.message || "Unknown error")}</p>
    <p>From the project folder run <code>python build_site_data.py</code> and <code>python serve_site.py</code>, then open the address it prints.</p>
    <button class="btn soft" id="retryLoad">Try again</button></div>`;
  $("#resultCount").textContent = "No products loaded";
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
}

// ---------------------------------------------------------------- static sections
function renderHero() {
  const m = state.data.meta || {};
  $("#heroStats").innerHTML = `<span><b>${state.products.length}</b> products</span><span><b>${(state.data.catalogues || []).length}</b> source catalogues</span><span><b>${m.with_confirmed_image ?? 0}</b> with catalogue images</span>`;
}

function renderCategories() {
  const cats = state.data.categories || [];
  $("#categoryGrid").innerHTML = cats.map((c) => `
    <button class="cat${state.filters.categories.has(c.name) ? " active" : ""}" data-cat="${esc(c.name)}" aria-pressed="${state.filters.categories.has(c.name)}">
      <div class="cat-art">${art(c.art)}</div><h3>${esc(c.name)}</h3><p>${esc(c.blurb || "")}</p><span class="cat-count">${c.records} products</span>
    </button>`).join("");
}

function renderCatalogues() {
  const list = state.data.catalogues || [];
  $("#catalogueList").innerHTML = list.map((c) => `
    <div class="catalogue-row"><div class="catalogue-info"><div class="pdf-icon" aria-hidden="true">▤</div><div><strong>${esc(c.title)}</strong>
      <small>${esc(c.category)} · ${c.records} products · ${esc(c.pdf)}</small></div></div>
      <div class="row-actions"><button class="btn soft" data-show-cat="${esc(c.category)}">Show products</button><a class="btn outline" href="${esc(c.href)}" target="_blank" rel="noopener">Open catalogue PDF ↗</a></div></div>`).join("")
    + `<div class="catalogue-row pending"><div class="catalogue-info"><div class="pdf-icon" aria-hidden="true">▤</div><div><strong>More GROZ catalogues</strong>
      <small>Hand Tools and Fluid Handling are not in this preview yet. Their products will appear once they have been extracted and reviewed.</small></div></div></div>`;
}

function renderDataNote() {
  const m = state.data.meta || {};
  const verified = m.verified ?? state.products.filter((p) => p.status === "verified").length;
  const review = m.fields_under_review ?? 0;
  $("#dataNote").innerHTML = `<span aria-hidden="true">ⓘ</span><span>${verified === 0
    ? `All <b>${state.products.length}</b> products were extracted from the original GROZ catalogues and are <b>not yet verified</b> by a person.`
    : `<b>${verified}</b> of ${state.products.length} products are verified; the rest were extracted automatically and are <b>not yet verified</b>.`}
    ${review ? ` ${review} values awaiting a corrected reading are shown as <b>Under review</b>.` : ""} Each product links to its source page — check it before you order.</span>`;
}

// ---------------------------------------------------------------- filters
function categoryScope() {
  const f = state.filters;
  return state.products.filter((p) => !f.categories.size || f.categories.has(p.category));
}

function renderFilters() {
  const f = state.filters;
  const cats = state.data.categories || [];
  // Specification filters are offered per category: across all categories they would be a long,
  // mixed list (beam angles next to drawer capacities).
  const groups = f.categories.size ? core.facetGroups(categoryScope()) : [];
  // Keep selected facet values visible even if the category change hid their group.
  for (const [key, values] of [...f.facets]) {
    if (!groups.some((g) => g.key === key) && values.size) f.facets.delete(key);
  }
  const count = (pred) => state.products.filter(pred).length;
  const statusCounts = core.STATUS_ORDER.map((s) => [s, count((p) => p.status === s)]).filter(([, n]) => n > 0);
  const statusLabel = { verified: "Verified", unverified: "Not yet verified", needs_review: "Needs review" };
  const facetHtml = groups.map((g) => {
    const selected = f.facets.get(g.key) || new Set();
    const expanded = state.expandedFacets.has(g.key);
    const values = expanded ? g.values : g.values.slice(0, 6);
    return `<div class="filter-group"><h4>${esc(g.label)}</h4>${values.map((v) => `
      <label class="filter-option"><input type="checkbox" data-facet="${esc(g.key)}" value="${esc(v.value)}" ${selected.has(v.value) ? "checked" : ""}/> <span>${esc(v.value)}</span><span class="n">${v.count}</span></label>`).join("")}
      ${g.values.length > 6 ? `<button class="filter-more" type="button" data-expand="${esc(g.key)}">${expanded ? "Show fewer" : `Show all ${g.values.length}`}</button>` : ""}</div>`;
  }).join("");
  $("#filterBody").innerHTML = `
    <div class="filter-group"><h4>Category</h4>${cats.map((c) => `
      <label class="filter-option"><input type="checkbox" data-filter="category" value="${esc(c.name)}" ${f.categories.has(c.name) ? "checked" : ""}/> <span>${esc(c.name)}</span><span class="n">${c.records}</span></label>`).join("")}</div>
    ${facetHtml || (f.categories.size ? "" : `<div class="filter-group"><h4>Specifications</h4><p class="filter-option" style="cursor:default">Choose a category to filter by its specifications.</p></div>`)}
    <div class="filter-group"><h4>Images</h4><label class="filter-option"><input type="checkbox" data-filter="image" ${f.withImage ? "checked" : ""}/> <span>Only with a catalogue image</span><span class="n">${count((p) => !!p.image)}</span></label></div>
    <div class="filter-group"><h4>Review status</h4>${statusCounts.map(([s, n]) => `
      <label class="filter-option"><input type="checkbox" data-filter="status" value="${s}" ${f.statuses.has(s) ? "checked" : ""}/> <span>${statusLabel[s]}</span><span class="n">${n}</span></label>`).join("")}
      <label class="filter-option"><input type="checkbox" data-filter="notes" ${f.withNotes ? "checked" : ""}/> <span>Has a catalogue review note</span><span class="n">${count((p) => p.notes.length > 0)}</span></label></div>`;
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
  for (const s of f.statuses) chips.push(["status", s, { verified: "Verified", unverified: "Not yet verified", needs_review: "Needs review" }[s]]);
  if (f.withNotes) chips.push(["notes", "", "Has review note"]);
  $("#activeChips").innerHTML = chips.map(([type, value, label]) =>
    `<span class="chip">${esc(label)}<button type="button" data-chip="${esc(type)}" data-value="${esc(value)}" aria-label="Remove filter ${esc(label)}">×</button></span>`).join("")
    + (chips.length > 1 ? '<button class="chip clear" type="button" data-chip="all">Clear all</button>' : "");
  const n = core.activeFilterCount(f);
  $("#filterBadge").textContent = n ? `(${n})` : "";
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
function imageHtml(p, cls = "") {
  if (p.image) {
    const tag = p.image.evidence === "product_family" ? '<span class="img-tag">Family image</span>' : "";
    return `<img src="${esc(p.image.src)}" alt="Catalogue image for ${esc(p.cat_nr)}${p.image.evidence === "product_family" ? " (product family)" : ""}" loading="lazy" decoding="async"${cls}/>${tag}`;
  }
  return `${art(state.artByCategory.get(p.category))}<span class="img-tag">No confirmed image</span>`;
}

function placeholderFor(img) {
  const card = img.closest("[data-id]");
  const p = card && state.byId.get(card.dataset.id);
  const holder = img.parentElement;
  img.remove();
  holder.querySelector(".img-tag")?.remove();
  holder.insertAdjacentHTML("beforeend", `${art(p ? state.artByCategory.get(p.category) : "tool")}<span class="img-tag">Image unavailable</span>`);
}

function statusHtml(p) {
  const notes = p.notes.length ? `<span class="note-flag" title="This product has a catalogue review note">Review note</span>` : "";
  return `<span class="status status-${esc(p.status)}">${esc(p.status_label)}</span>${notes}`;
}

function skuHtml(p) {
  return `ORD NR <b>${p.ord_nr ? esc(p.ord_nr) : "not printed"}</b> · ${esc(p.catalogue.title)}, p. ${esc(p.printed_page ?? p.page)}`;
}

function headingHtml(p) {
  return p.heading ? `<div class="heading">${esc(p.heading)}</div>` : `<div class="heading muted">${esc(p.category)} · no heading printed</div>`;
}

function cardHtml(p) {
  const saved = state.saved.has(p.id);
  const inQuote = state.quote.has(p.id);
  const specs = core.summarySpecs(p, 2);
  return `<article class="product" data-id="${esc(p.id)}">
    <button class="product-image" type="button" data-detail aria-label="View details for ${esc(p.cat_nr)}">${imageHtml(p)}</button>
    <button class="heart${saved ? " saved" : ""}" type="button" data-save aria-pressed="${saved}" aria-label="${saved ? "Remove from saved" : "Save"} ${esc(p.cat_nr)}">${saved ? "♥" : "♡"}</button>
    <div class="card-meta">${statusHtml(p)}</div>
    <h3><button class="title-btn" type="button" data-detail>${esc(p.cat_nr || "No catalogue number")}</button></h3>
    <div class="sku">${skuHtml(p)}</div>
    ${headingHtml(p)}
    <dl class="spec">${specs.length ? specs.map((s) => `<div><dt>${esc(s.label)}</dt><dd>${esc(s.value)}</dd></div>`).join("") : '<div><dt>Specifications</dt><dd class="v-missing">See details</dd></div>'}</dl>
    <div class="product-actions"><button class="btn ${inQuote ? "in-quote" : "primary"}" type="button" data-quote>${inQuote ? "In quote ✓" : "Add to quote"}</button>
      <label class="compare-check"><input type="checkbox" data-compare ${state.compare.has(p.id) ? "checked" : ""}/> Compare</label></div>
  </article>`;
}

function tableHtml(list) {
  return `<div class="ptable-wrap"><table class="ptable"><thead><tr><th scope="col"><span class="sr-only">Image</span></th><th scope="col">Product</th><th scope="col">ORD NR</th>
    <th scope="col" class="hide-sm">Key specifications</th><th scope="col" class="hide-sm">Source</th><th scope="col" class="hide-sm">Status</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead><tbody>
    ${list.map((p) => `<tr data-id="${esc(p.id)}">
      <td><button class="thumb" type="button" data-detail aria-label="View details for ${esc(p.cat_nr)}">${p.image ? `<img src="${esc(p.image.src)}" alt="" loading="lazy"/>` : art(state.artByCategory.get(p.category))}</button></td>
      <td><button class="title-btn code" type="button" data-detail>${esc(p.cat_nr)}</button>${headingHtml(p)}</td>
      <td>${p.ord_nr ? esc(p.ord_nr) : '<span class="muted">Not printed</span>'}</td>
      <td class="hide-sm">${core.summarySpecs(p, 2).map((s) => `${esc(s.label)}: <b>${esc(s.value)}</b>`).join("<br/>") || '<span class="muted">See details</span>'}</td>
      <td class="hide-sm">${esc(p.catalogue.title)}<br/><span class="muted">printed p. ${esc(p.printed_page ?? "—")}</span></td>
      <td class="hide-sm">${statusHtml(p)}</td>
      <td class="actions"><button class="btn ${state.quote.has(p.id) ? "in-quote" : "primary"}" type="button" data-quote>${state.quote.has(p.id) ? "In quote ✓" : "Add to quote"}</button>
        <label class="compare-check"><input type="checkbox" data-compare ${state.compare.has(p.id) ? "checked" : ""}/> Compare</label></td>
    </tr>`).join("")}</tbody></table></div>`;
}

function currentResults() {
  return core.sortProducts(core.filterProducts(state.products, state.index, state.filters), state.sort);
}

function renderProducts() {
  if (!state.data) return;
  const list = currentResults();
  grid.setAttribute("aria-busy", "false");
  $("#resultCount").innerHTML = `<strong>${list.length}</strong> of ${state.products.length} products`;
  renderChips();
  if (!state.products.length) {
    grid.className = "products";
    grid.innerHTML = '<div class="state"><strong>No products in this catalogue yet.</strong><p>The data file loaded, but it contains no products.</p></div>';
    $("#moreWrap").innerHTML = "";
    return;
  }
  if (!list.length) {
    grid.className = "products";
    grid.innerHTML = `<div class="empty"><div style="font-size:28px" aria-hidden="true">⌕</div><strong>No matches this time.</strong><p>Try another search or remove a filter.</p><button class="btn soft" type="button" data-reset>Reset search and filters</button></div>`;
    $("#moreWrap").innerHTML = "";
    return;
  }
  const page = list.slice(0, state.shown);
  if (state.view === "table") {
    grid.className = "products-table";
    grid.innerHTML = tableHtml(page);
  } else {
    grid.className = "products";
    grid.innerHTML = page.map(cardHtml).join("");
  }
  const remaining = list.length - page.length;
  $("#moreWrap").innerHTML = remaining > 0 ? `<button class="btn outline" type="button" id="showMore">Show ${Math.min(remaining, core.PAGE_SIZE)} more · ${remaining} remaining</button>` : "";
}

function setView(view, rerender = true) {
  state.view = view;
  store.set("groz.view", view);
  $("#gridView").classList.toggle("active", view === "grid");
  $("#tableView").classList.toggle("active", view === "table");
  $("#gridView").setAttribute("aria-pressed", String(view === "grid"));
  $("#tableView").setAttribute("aria-pressed", String(view === "table"));
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
  if (scroll) $("#products").scrollIntoView({ behavior: "smooth" });
}

function updateBadges() {
  $("#savedCount").textContent = state.saved.size;
  $("#savedBtn").setAttribute("aria-label", `Saved products, ${state.saved.size} saved`);
  $("#quoteCount").textContent = state.quote.size;
  const dock = $("#compareDock");
  $("#compareCount").textContent = `${state.compare.size} selected to compare`;
  dock.classList.toggle("show", state.compare.size > 0);
}

// ---------------------------------------------------------------- product actions
function toggleSaved(id) {
  if (state.saved.has(id)) { state.saved.delete(id); notify("Removed from saved"); }
  else { state.saved.add(id); notify("Saved for later ♥"); }
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

function syncProductButtons(id) {
  for (const el of $$(`[data-id="${CSS.escape(id)}"]`, grid)) {
    const q = el.querySelector("[data-quote]");
    if (q) { const inQ = state.quote.has(id); q.className = `btn ${inQ ? "in-quote" : "primary"}`; q.textContent = inQ ? "In quote ✓" : "Add to quote"; }
    const h = el.querySelector("[data-save]");
    if (h) { const sv = state.saved.has(id); h.classList.toggle("saved", sv); h.textContent = sv ? "♥" : "♡"; h.setAttribute("aria-pressed", String(sv)); }
    const c = el.querySelector("[data-compare]");
    if (c) c.checked = state.compare.has(id);
  }
}

// ---------------------------------------------------------------- modal
let lastFocus = null;
let lastClicked = null; // fallback when a click does not move focus (e.g. some browsers, scripted clicks)
document.addEventListener("click", (e) => { const b = e.target.closest("button,a"); if (b && !modal.contains(b)) lastClicked = b; }, true);
function openModal(title, html, { wide = false } = {}) {
  if (!backdrop.classList.contains("open")) {
    lastFocus = document.activeElement && document.activeElement !== document.body ? document.activeElement : lastClicked;
  }
  $("#modalTitle").textContent = title;
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
  if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
}
function trapFocus(e) {
  if (e.key !== "Tab" || !backdrop.classList.contains("open")) return;
  const items = $$('button,a[href],input,select,textarea,[tabindex]:not([tabindex="-1"])', modal).filter((el) => !el.disabled && el.offsetParent !== null);
  if (!items.length) return;
  const first = items[0], last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

function valueCell(r) {
  if (r.state === "missing") return `<span class="v-missing">Not specified</span>`;
  if (r.state === "review") return `<span class="v-review" title="A corrected reading of this value is awaiting approval">Under review</span>`;
  return esc(r.text);
}

function showDetails(id) {
  const p = state.byId.get(id);
  if (!p) return;
  const rows = core.detailRows(p);
  const inQ = state.quote.has(p.id), saved = state.saved.has(p.id), cmp = state.compare.has(p.id);
  const image = p.image
    ? `<img src="${esc(p.image.src)}" alt="Catalogue image for ${esc(p.cat_nr)}"/>`
    : `${art(state.artByCategory.get(p.category))}`;
  const evidence = p.image
    ? `<b>${esc(p.image.evidence_label)}.</b>${p.image.evidence_detail ? ` Why this image: ${esc(p.image.evidence_detail)}.` : ""}`
    : p.image_candidate_unconfirmed
      ? "No confirmed image: the catalogue page has an image near this product, but nothing links it to this product specifically. The illustration is a category icon."
      : "No product image was found for this product. The illustration is a category icon.";
  const notes = p.notes.length ? `<div class="review-notes"><h4>Catalogue review note${p.notes.length > 1 ? "s" : ""}</h4>${p.notes.map((n) => `
      <p style="margin:6px 0"><b>${esc(n.field)}</b> — printed value: <code>${esc(n.published_value)}</code> (${esc(n.status)})<br/>${esc(n.issue)}</p>`).join("")}</div>` : "";
  const reviewList = p.under_review.length
    ? `<p class="evidence"><b>Under review:</b> ${p.under_review.map((u) => esc(u.label)).join(", ")} — a corrected reading of ${p.under_review.length > 1 ? "these values is" : "this value is"} awaiting approval, so ${p.under_review.length > 1 ? "they are" : "it is"} not shown.</p>` : "";
  openModal("Product details", `
    <div class="detail-grid">
      <div><div class="detail-art">${image}</div><p class="evidence">${evidence}</p></div>
      <div class="detail-copy">
        <div class="eyebrow" style="color:var(--orange2)">${esc(p.category)}${p.brand ? ` · ${esc(p.brand)}` : ""}</div>
        <h2>${esc(p.cat_nr || "No catalogue number")}</h2>
        <div class="sku">${skuHtml(p)}</div>
        <div class="card-meta">${statusHtml(p)}</div>
        ${p.heading ? `<p class="lead">${esc(p.heading)}</p>` : ""}
        <div class="detail-actions">
          <button class="btn ${inQ ? "in-quote" : "primary"}" type="button" data-modal-quote="${esc(p.id)}" data-autofocus>${inQ ? "In quote ✓ — view quote" : "Add to quote"}</button>
          <button class="btn soft" type="button" data-modal-save="${esc(p.id)}" aria-pressed="${saved}">${saved ? "♥ Saved" : "♡ Save"}</button>
          <button class="btn soft" type="button" data-modal-compare="${esc(p.id)}" aria-pressed="${cmp}">${cmp ? "✓ Comparing" : "↔ Compare"}</button>
          <a class="btn outline" href="${esc(p.catalogue.href)}" target="_blank" rel="noopener">Open catalogue page ↗</a>
        </div>
      </div>
    </div>
    <table class="spec-table"><caption class="sr-only">Specifications for ${esc(p.cat_nr)}</caption><tbody>
      ${rows.map((r) => `<tr><th scope="row">${esc(r.label)}</th><td>${valueCell(r)}</td></tr>`).join("")}
    </tbody></table>
    ${reviewList}${notes}
    <div class="source-box"><b>Source</b>: ${esc(p.catalogue.title)} — printed page ${esc(p.printed_page ?? "not printed")} (PDF page ${p.page}), file <code>${esc(p.catalogue.pdf)}</code>.
      ${p.source_row_text ? `<br/><b>Catalogue table row</b> (text as extracted):<pre>${esc(p.source_row_text)}</pre>` : ""}
      <div style="margin-top:6px">Review status: <b>${esc(p.status_label)}</b>. Values were extracted automatically; check the catalogue page before ordering.</div></div>`, { wide: true });
}

function showCompare() {
  const list = [...state.compare].map((id) => state.byId.get(id)).filter(Boolean);
  if (list.length < 2) { notify("Choose at least two products to compare."); return; }
  const rows = core.compareRows(list);
  openModal("Compare your shortlist", `
    <div style="overflow:auto"><table class="compare-table"><thead><tr><th scope="col">Specification</th>${list.map((p) => `
      <th scope="col"><div class="compare-head"><span>${esc(p.cat_nr)}</span><span class="sku" style="font-weight:400">${esc(p.heading || p.category)}</span>
      <button class="remove" type="button" data-uncompare="${esc(p.id)}" aria-label="Remove ${esc(p.cat_nr)} from comparison">Remove ×</button></div></th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr><th scope="row">${esc(r.label)}</th>${r.cells.map((c) => `<td>${valueCell(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    <p class="evidence">“Not specified” means the catalogue table for that product does not print the value. “Under review” values await a corrected reading.</p>
    <div class="detail-actions"><button class="btn primary" type="button" data-quote-all data-autofocus>Add all to quote ↗</button><button class="btn soft" type="button" data-clear-compare>Clear comparison</button></div>`, { wide: true });
}

function showSaved() {
  const list = [...state.saved].map((id) => state.byId.get(id)).filter(Boolean);
  openModal("Saved for later", list.length ? `<div class="saved-list">${list.map((p) => `
    <div class="saved-item" data-id="${esc(p.id)}"><div class="thumb">${p.image ? `<img src="${esc(p.image.src)}" alt=""/>` : art(state.artByCategory.get(p.category))}</div>
      <div class="grow"><strong>${esc(p.cat_nr)}</strong><div class="sku">${skuHtml(p)}</div></div>
      <div class="acts"><button class="btn soft" type="button" data-saved-view="${esc(p.id)}">View</button><button class="btn primary" type="button" data-saved-quote="${esc(p.id)}">${state.quote.has(p.id) ? "In quote ✓" : "Add to quote"}</button><button class="btn danger" type="button" data-saved-remove="${esc(p.id)}">Remove</button></div></div>`).join("")}</div>
    <div class="detail-actions"><button class="btn primary" type="button" data-saved-quote-all>Add all to quote ↗</button></div>`
    : `<div class="empty" style="border:0"><div style="font-size:28px" aria-hidden="true">♡</div><strong>Nothing saved yet.</strong><p>Tap ♡ on a product and it will be waiting here, even after you close the page.</p></div>`);
}

// ---------------------------------------------------------------- quotation (local preparation only)
function quoteItems() {
  return [...state.quote].map(([id, qty]) => ({ id, qty })).filter((i) => state.byId.has(i.id));
}

function quoteItemsHtml() {
  const items = quoteItems();
  if (!items.length) return `<div class="empty" style="border:0;padding:24px"><strong>Your quote is empty.</strong><p>Use “Add to quote” on any product, or add your saved or compared products.</p>
    <div class="detail-actions" style="justify-content:center">${state.saved.size ? '<button class="btn soft" type="button" data-quote-saved>Add saved products</button>' : ""}${state.compare.size ? '<button class="btn soft" type="button" data-quote-compared>Add compared products</button>' : ""}</div></div>`;
  return `<table class="quote-table"><thead><tr><th scope="col">Product</th><th scope="col">ORD NR</th><th scope="col">Quantity</th><th scope="col"><span class="sr-only">Remove</span></th></tr></thead><tbody>
    ${items.map(({ id, qty }) => { const p = state.byId.get(id); return `<tr data-qid="${esc(id)}"><td><button class="title-btn" type="button" data-quote-view="${esc(id)}"><b>${esc(p.cat_nr)}</b></button><div class="sku">${esc(p.heading || p.category)}</div></td>
      <td>${p.ord_nr ? esc(p.ord_nr) : '<span class="v-missing">Not printed</span>'}</td>
      <td><input class="qty" type="number" inputmode="numeric" min="1" max="${core.MAX_QTY}" step="1" value="${esc(qty)}" data-qty="${esc(id)}" aria-label="Quantity for ${esc(p.cat_nr)}"/><div class="err" id="qtyerr-${esc(id)}"></div></td>
      <td><button class="btn danger" type="button" data-quote-remove="${esc(id)}" aria-label="Remove ${esc(p.cat_nr)} from quote" style="padding:7px 10px;font-size:10px">Remove</button></td></tr>`; }).join("")}</tbody></table>`;
}

function totalsHtml() {
  const t = core.quoteTotals(quoteItems());
  return `<span>Products: <b>${t.lines}</b></span><span>Total units: <b>${t.units}</b></span>${t.invalid ? `<span class="v-review">${t.invalid} quantit${t.invalid > 1 ? "ies need" : "y needs"} fixing</span>` : ""}`;
}

function field(id, label, { type = "text", required = false, full = false, area = false, autocomplete = "" } = {}) {
  const value = esc(state.contact[id] ?? "");
  const input = area
    ? `<textarea id="q-${id}" name="${id}" placeholder="Model variants, delivery timing, anything else…">${value}</textarea>`
    : `<input id="q-${id}" name="${id}" type="${type}" value="${value}" ${required ? 'required aria-required="true"' : ""} ${autocomplete ? `autocomplete="${autocomplete}"` : ""} aria-describedby="err-${id}"/>`;
  return `<div class="field${full ? " full" : ""}"><label for="q-${id}">${label}${required ? " *" : ""}</label>${input}<div class="err" id="err-${id}" role="alert"></div></div>`;
}

function showQuote() {
  openModal("Let’s build your quote", `
    <p class="notice">This prepares a quotation request on your device. <b>Nothing is sent</b> — when it is ready you can copy, download or print it for your GROZ sales contact.</p>
    <div id="quoteItems">${quoteItemsHtml()}</div><div class="err" id="err-items" role="alert"></div>
    <div class="quote-totals" id="quoteTotals" aria-live="polite">${totalsHtml()}</div>
    <form class="form-grid" id="quoteForm" novalidate>
      ${field("name", "Full name", { required: true, autocomplete: "name" })}
      ${field("company", "Company", { autocomplete: "organization" })}
      ${field("email", "Work email", { type: "email", required: true, autocomplete: "email" })}
      ${field("phone", "Phone", { type: "tel", autocomplete: "tel" })}
      ${field("location", "Delivery location", { full: true, autocomplete: "address-level2" })}
      ${field("notes", "What else should we know?", { full: true, area: true })}
      <div class="field full"><button class="btn primary" type="submit">Prepare request ↗</button><small style="color:#77777d;font-size:10px">Fields marked * are required.</small></div>
    </form>`);
}

function refreshQuoteItems() {
  const box = $("#quoteItems");
  if (box) box.innerHTML = quoteItemsHtml();
  const t = $("#quoteTotals");
  if (t) t.innerHTML = totalsHtml();
}

function submitQuote(form) {
  for (const el of form.elements) if (el.name) state.contact[el.name] = el.value;
  const items = quoteItems().map((i) => ({ id: i.id, qty: $(`[data-qty="${CSS.escape(i.id)}"]`)?.value ?? i.qty }));
  const errors = core.validateQuote(items, state.contact);
  $$(".err", modal).forEach((e) => { e.textContent = ""; });
  $$("[aria-invalid]", modal).forEach((e) => e.removeAttribute("aria-invalid"));
  for (const [key, msg] of Object.entries(errors)) {
    if (key.startsWith("qty:")) {
      const id = key.slice(4);
      const input = $(`[data-qty="${CSS.escape(id)}"]`);
      input?.setAttribute("aria-invalid", "true");
      const e = document.getElementById(`qtyerr-${id}`);
      if (e) e.textContent = msg;
    } else {
      const e = document.getElementById(`err-${key}`);
      if (e) e.textContent = msg;
      $(`#q-${key}`)?.setAttribute("aria-invalid", "true");
    }
  }
  if (Object.keys(errors).length) {
    ($("[aria-invalid='true']", modal) || $("#err-items"))?.focus?.();
    notify("Please check the highlighted fields.");
    return;
  }
  const when = new Date();
  const text = core.quoteText(items, state.byId, state.contact, when);
  const csv = core.quoteCsv(items, state.byId);
  const stamp = when.toISOString().slice(0, 10);
  openModal("Your request is ready ✓", `
    <p class="notice">Your quotation request is prepared. It has <b>not been sent</b> — copy it into an email, download it or print it for your GROZ sales contact.</p>
    <pre class="prepared" id="preparedText" tabindex="0">${esc(text)}</pre>
    <div class="detail-actions">
      <button class="btn primary" type="button" id="copyQuote" data-autofocus>Copy text</button>
      <button class="btn soft" type="button" id="dlTxt">Download .txt</button>
      <button class="btn soft" type="button" id="dlCsv">Download .csv</button>
      <button class="btn soft" type="button" id="printQuote">Print</button>
      <button class="btn outline" type="button" id="editQuote">Edit request</button>
      <button class="btn danger" type="button" id="newQuote">Start a new quote</button>
    </div>`);
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

// ---------------------------------------------------------------- events
function wire() {
  let typing;
  const onType = (e) => { clearTimeout(typing); const v = e.target.value; typing = setTimeout(() => setQuery(v), 120); };
  $("#navSearch").addEventListener("input", onType);
  $("#mainSearch").addEventListener("input", onType);
  $("#navSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); setQuery(e.target.value.trim(), { scroll: true }); } });
  $("#heroSearch").addEventListener("submit", (e) => { e.preventDefault(); setQuery($("#mainSearch").value.trim(), { scroll: true }); });
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; refresh(); });
  $("#gridView").addEventListener("click", () => setView("grid"));
  $("#tableView").addEventListener("click", () => setView("table"));
  $("#clearFilters").addEventListener("click", resetFilters);

  $("#categoryGrid").addEventListener("click", (e) => {
    const c = e.target.closest("[data-cat]");
    if (!c) return;
    const name = c.dataset.cat;
    state.filters.categories = state.filters.categories.has(name) && state.filters.categories.size === 1 ? new Set() : new Set([name]);
    renderCategories(); renderFilters(); refresh();
    $("#products").scrollIntoView({ behavior: "smooth" });
  });
  $("#catalogueList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-show-cat]");
    if (!b) return;
    state.filters.categories = new Set([b.dataset.showCat]);
    renderCategories(); renderFilters(); refresh();
    $("#products").scrollIntoView({ behavior: "smooth" });
  });

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
  });
  $("#activeChips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-chip]");
    if (!b) return;
    const f = state.filters, type = b.dataset.chip, value = b.dataset.value;
    if (type === "all") return resetFilters();
    if (type === "query") { setQuery(""); return; }
    if (type === "category") { f.categories.delete(value); renderCategories(); }
    else if (type === "image") f.withImage = false;
    else if (type === "status") f.statuses.delete(value);
    else if (type === "notes") f.withNotes = false;
    else if (type.startsWith("facet:")) { const k = type.slice(6); f.facets.get(k)?.delete(value); if (!f.facets.get(k)?.size) f.facets.delete(k); }
    renderFilters();
    refresh();
  });

  grid.addEventListener("click", (e) => {
    if (e.target.closest("[data-reset]")) return resetFilters();
    const host = e.target.closest("[data-id]");
    if (!host) return;
    const id = host.dataset.id;
    if (e.target.closest("[data-save]")) { toggleSaved(id); syncProductButtons(id); return; }
    if (e.target.closest("[data-quote]")) {
      if (state.quote.has(id)) { showQuote(); return; }
      addToQuote(id); syncProductButtons(id); return;
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
    if (e.target.id !== "showMore") return;
    state.shown += core.PAGE_SIZE;
    refresh({ resetPaging: false });
  });

  $("#compareBtn").addEventListener("click", showCompare);
  $("#clearCompare").addEventListener("click", () => { state.compare.clear(); updateBadges(); renderProducts(); });
  const openQuote = () => { $("#mobileMenu").hidden = true; $("#menuBtn").setAttribute("aria-expanded", "false"); showQuote(); };
  $("#navQuote").addEventListener("click", openQuote);
  $("#bannerQuote").addEventListener("click", openQuote);
  $("#mobileQuote").addEventListener("click", openQuote);
  $("#savedBtn").addEventListener("click", showSaved);
  $("#menuBtn").addEventListener("click", () => {
    const menu = $("#mobileMenu");
    menu.hidden = !menu.hidden;
    $("#menuBtn").setAttribute("aria-expanded", String(!menu.hidden));
  });
  $("#mobileMenu").addEventListener("click", (e) => { if (e.target.closest("a")) { $("#mobileMenu").hidden = true; $("#menuBtn").setAttribute("aria-expanded", "false"); } });

  const filters = $("#filters");
  const setFiltersOpen = (open) => { filters.classList.toggle("open", open); $("#filtersToggle").setAttribute("aria-expanded", String(open)); if (open) $("#filtersClose").focus(); };
  $("#filtersToggle").addEventListener("click", () => setFiltersOpen(!filters.classList.contains("open")));
  $("#filtersClose").addEventListener("click", () => setFiltersOpen(false));
  $("#filtersDone").addEventListener("click", () => { setFiltersOpen(false); $("#resultCount").scrollIntoView({ behavior: "smooth", block: "center" }); });

  // modal content actions (delegated)
  $("#modalClose").addEventListener("click", closeModal);
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) closeModal(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { if (backdrop.classList.contains("open")) closeModal(); else if (filters.classList.contains("open")) setFiltersOpen(false); }
    trapFocus(e);
  });
  modal.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    const d = t.dataset;
    if (d.modalQuote) { if (state.quote.has(d.modalQuote)) showQuote(); else { addToQuote(d.modalQuote); syncProductButtons(d.modalQuote); showDetails(d.modalQuote); } }
    else if (d.modalSave) { toggleSaved(d.modalSave); syncProductButtons(d.modalSave); showDetails(d.modalSave); }
    else if (d.modalCompare) { if (toggleCompare(d.modalCompare, !state.compare.has(d.modalCompare))) { syncProductButtons(d.modalCompare); showDetails(d.modalCompare); } }
    else if (d.uncompare) { state.compare.delete(d.uncompare); updateBadges(); syncProductButtons(d.uncompare); state.compare.size >= 2 ? showCompare() : (closeModal(), notify("Choose at least two products to compare.")); }
    else if ("quoteAll" in d) { for (const id of state.compare) if (!state.quote.has(id)) state.quote.set(id, 1); persist(); updateBadges(); renderProducts(); showQuote(); }
    else if ("clearCompare" in d) { state.compare.clear(); updateBadges(); renderProducts(); closeModal(); }
    else if (d.savedView) showDetails(d.savedView);
    else if (d.savedQuote) { addToQuote(d.savedQuote); syncProductButtons(d.savedQuote); showSaved(); }
    else if (d.savedRemove) { state.saved.delete(d.savedRemove); persist(); updateBadges(); syncProductButtons(d.savedRemove); showSaved(); }
    else if ("savedQuoteAll" in d) { for (const id of state.saved) if (!state.quote.has(id)) state.quote.set(id, 1); persist(); updateBadges(); renderProducts(); showQuote(); }
    else if (d.quoteRemove) { state.quote.delete(d.quoteRemove); persist(); updateBadges(); syncProductButtons(d.quoteRemove); refreshQuoteItems(); }
    else if (d.quoteView) showDetails(d.quoteView);
    else if ("quoteSaved" in d) { for (const id of state.saved) if (!state.quote.has(id)) state.quote.set(id, 1); persist(); updateBadges(); renderProducts(); refreshQuoteItems(); }
    else if ("quoteCompared" in d) { for (const id of state.compare) if (!state.quote.has(id)) state.quote.set(id, 1); persist(); updateBadges(); renderProducts(); refreshQuoteItems(); }
  });
  modal.addEventListener("input", (e) => {
    const q = e.target.closest("[data-qty]");
    if (q) {
      const n = core.parseQty(q.value);
      if (n != null) { state.quote.set(q.dataset.qty, n); persist(); q.removeAttribute("aria-invalid"); const err = document.getElementById(`qtyerr-${q.dataset.qty}`); if (err) err.textContent = ""; }
      else q.setAttribute("aria-invalid", "true");
      // totals use the visible inputs, so a half-typed value is reported rather than silently replaced
      const items = quoteItems().map((i) => ({ id: i.id, qty: $(`[data-qty="${CSS.escape(i.id)}"]`)?.value ?? i.qty }));
      const t = core.quoteTotals(items);
      $("#quoteTotals").innerHTML = `<span>Products: <b>${t.lines}</b></span><span>Total units: <b>${t.units}</b></span>${t.invalid ? `<span class="v-review">${t.invalid} quantit${t.invalid > 1 ? "ies need" : "y needs"} fixing</span>` : ""}`;
      return;
    }
    if (e.target.form?.id === "quoteForm" && e.target.name) state.contact[e.target.name] = e.target.value;
  });
  modal.addEventListener("submit", (e) => {
    if (e.target.id !== "quoteForm") return;
    e.preventDefault();
    submitQuote(e.target);
  });
  modal.addEventListener("error", (e) => { if (e.target.tagName === "IMG") { const parent = e.target.parentElement; e.target.remove(); parent.insertAdjacentHTML("beforeend", art("tool")); } }, true);

  const io = "IntersectionObserver" in window
    ? new IntersectionObserver((es) => es.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } }), { threshold: 0.08 })
    : null;
  $$(".reveal").forEach((el) => (io ? io.observe(el) : el.classList.add("in")));
}

wire();
load();
