// GROZ verification tool: page layer. Talks only to the local review server (verify_server.py).
import * as vc from "./verify-core.mjs";
import { icon } from "/site/assets/js/icons.mjs";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode: keep in memory */ } },
};

const state = {
  records: [], byId: new Map(), filter: "to_check", catalogue: "", query: "",
  currentId: null, view: ["row", "table", "page"].includes(store.get("groz.verify.view", "row")) ? store.get("groz.verify.view", "row") : "row", busy: false, site: null,
};
const work = $("#work");
const toastEl = $("#toast");

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => toastEl.classList.remove("show"), 3000);
}

async function api(path, body) {
  const res = await fetch(path, body === undefined ? { cache: "no-store" } : {
    method: "POST", headers: { "Content-Type": "application/json", "X-GROZ-Review": "1" }, body: JSON.stringify(body),
  });
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) throw new Error(data?.error || `The review server answered ${res.status}.`);
  return data;
}

// ---------------------------------------------------------------- loading
async function load() {
  try {
    const data = await api("/api/review/records");
    state.records = data.records;
    state.byId = new Map(data.records.map((r) => [r.id, r]));
    state.site = data.site;
    if (!data.can_publish) {
      const b = $("#publish");
      b.disabled = true;
      b.textContent = "Test ledger";
      b.title = "This server uses a test ledger: its decisions never reach the catalogue site.";
    }
    const cats = [...new Map(data.records.map((r) => [r.pdf, r.catalogue])).entries()];
    $("#catFilter").innerHTML = '<option value="">All catalogues</option>' + cats.map(([pdf, title]) =>
      `<option value="${esc(pdf)}">${esc(title)} (${data.records.filter((r) => r.pdf === pdf).length})</option>`).join("");
    renderProgress();
    renderList();
    const first = visible()[0] || state.records[0];
    select(first?.id ?? null);
  } catch (err) {
    work.innerHTML = `<div class="vempty" role="alert"><strong>The verification tool needs its local server.</strong>
      <p>${esc(err.message)}</p><p>From the project folder run <code>.venv/Scripts/python.exe verify_server.py</code> and open the address it prints.</p></div>`;
    $("#progress").textContent = "Not connected";
  }
}

function visible() {
  return vc.filterQueue(state.records, { filter: state.filter, catalogue: state.catalogue, query: state.query });
}

function renderProgress() {
  const c = vc.counts(state.records);
  const pct = (n) => `${(n / Math.max(1, c.total)) * 100}%`;
  const behind = state.site?.behind;
  $("#progress").innerHTML = `<div class="vbar" aria-hidden="true"><i class="ok" style="width:${pct(c.verified)}"></i><i class="fl" style="width:${pct(c.flagged)}"></i></div>
    <span><b>${c.verified}</b> verified · <b>${c.flagged}</b> flagged · <b>${c.to_check}</b> to check${c.stale ? ` (${c.stale} changed since checked)` : ""} of ${c.total}</span>
    ${behind ? `<span class="v-review">${behind} decision${behind === 1 ? "" : "s"} not on the catalogue site yet</span>` : ""}`;
  for (const k of ["to_check", "flagged", "verified"]) { const el = $(`[data-count="${k}"]`); if (el) el.textContent = c[k]; }
}

function itemHtml(r) {
  const st = vc.isStale(r) ? "stale" : vc.stateOf(r);
  return `<li><button class="vitem" type="button" data-id="${esc(r.id)}" aria-current="${r.id === state.currentId}">
    <span class="dot ${st}" title="${esc(vc.decisionText(r).text)}"></span><b>${esc(r.cat_nr || "—")}</b><span class="pg">p. ${esc(r.printed_page ?? r.page)}</span>
    <small>${esc(r.title || r.category)}</small></button></li>`;
}

function renderList() {
  const list = visible();
  $("#listCount").textContent = `${list.length} product${list.length === 1 ? "" : "s"}`;
  $("#list").innerHTML = list.map(itemHtml).join("") || '<li class="vempty"><strong>Nothing here.</strong>Change the filter or search.</li>';
  for (const b of $$("#stateFilter button")) b.setAttribute("aria-pressed", String(b.dataset.filter === state.filter));
}

function markCurrentInList() {
  for (const b of $$("#list .vitem")) b.setAttribute("aria-current", String(b.dataset.id === state.currentId));
  $(`#list .vitem[data-id="${CSS.escape(state.currentId || "")}"]`)?.scrollIntoView({ block: "nearest" });
}

// ---------------------------------------------------------------- one product
function valueRows(r) {
  return r.values.map((v) => `<tr><th scope="row">${esc(v.label)}</th>${v.value == null || v.value === ""
    ? '<td class="empty">— not extracted</td>' : `<td>${esc(v.value)}</td>`}</tr>`).join("");
}

function select(id) {
  state.currentId = id;
  const r = id && state.byId.get(id);
  if (!r) {
    work.innerHTML = `<div class="vempty"><strong>${state.filter === "to_check" ? "Everything in this list has been checked." : "No product selected."}</strong>Choose another filter or catalogue.</div>`;
    markCurrentInList();
    return;
  }
  const list = visible();
  const pos = list.findIndex((x) => x.id === id);
  const d = vc.decisionText(r);
  const flagFields = [...r.values.map((v) => v.label), "Image", "Other"];
  work.innerHTML = `
    <div class="vhead">
      <div><div class="eyebrow accent">${esc(r.category)} · ${esc(r.catalogue)}, printed p. ${esc(r.printed_page ?? "—")} (PDF p. ${r.page})</div>
        <h1>${esc(r.cat_nr || "No CAT NR")}</h1><p class="lead">${esc(r.title || "")}</p></div>
      <div class="vnav">${pos >= 0 ? `<span>${pos + 1} of ${list.length}</span>` : ""}
        <button class="btn soft sm" type="button" data-step="-1" aria-label="Previous product">${icon("left")}<kbd>K</kbd></button>
        <button class="btn soft sm" type="button" data-step="1" aria-label="Next product">${icon("right")}<kbd>J</kbd></button></div>
    </div>
    <div class="vpanes">
      <figure class="vpage">
        <div class="vpage-tools"><div class="segmented" role="group" aria-label="Page view">
            ${VIEWS.map((v) => `<button type="button" data-view="${v}" class="${state.view === v ? "active" : ""}" aria-pressed="${state.view === v}">${VIEW_LABELS[v]}</button>`).join("")}</div>
          <a href="${esc(r.pdf_href)}" target="_blank" rel="noopener">Open PDF page ${icon("external")}</a></div>
        <div class="vimg-wrap"><div class="vstage" id="stage"><div class="vloading">Rendering the catalogue page…</div></div></div>
        <figcaption id="pageCaption"></figcaption>
      </figure>
      <div class="vvalues">
        <h2>Extracted values</h2>
        <p class="vhint">Compare every value with the highlighted row on the page. Mark it verified only if all of them match what is printed; “— not extracted” must also be true on the page.</p>
        <table class="vtable"><tbody>${valueRows(r)}</tbody></table>
        ${r.title_evidence ? `<div class="vsection"><h3>Printed title</h3>${esc(r.title_evidence)}</div>` : ""}
        <div class="vsection"><h3>Image shown on the catalogue site</h3>${r.image
          ? `<div class="vthumb"><img src="${esc(r.image.src)}" alt="Image shown for ${esc(r.cat_nr)}"/><div><b>${esc(r.image.label)}.</b> ${esc(r.image.evidence || "")}</div></div>`
          : r.image_unconfirmed ? "None: a picture is printed nearby, but nothing links it to this product." : "None: no product picture was found."}</div>
        ${r.notes.length ? `<div class="vsection"><h3>Catalogue review notes</h3>${r.notes.map((n) => `<div class="vnote"><b>${esc(n.field)}</b> — printed “${esc(n.published_value)}”. ${esc(n.issue)}</div>`).join("")}</div>` : ""}
        ${r.source_row_text ? `<div class="vsection"><h3>Table row as extracted</h3><pre>${esc(r.source_row_text)}</pre></div>` : ""}
        <p class="vkeys">Keys: <kbd>V</kbd> verified · <kbd>F</kbd> flag · <kbd>J</kbd>/<kbd>K</kbd> next/previous · <kbd>T</kbd> switch view</p>
      </div>
    </div>
    <form class="vflag" id="flagForm" hidden novalidate>
      <h3>Flag a problem with ${esc(r.cat_nr)}</h3>
      <fieldset><legend>Which values do not match the page?</legend>
        ${flagFields.map((f) => `<label><input type="checkbox" name="field" value="${esc(f)}"/> ${esc(f)}</label>`).join("")}</fieldset>
      <div class="err" id="flagFieldsErr"></div>
      <label for="flagComment" class="sr-only">What is wrong</label>
      <textarea id="flagComment" placeholder="What is printed on the page, and what was extracted instead?" maxlength="2000"></textarea>
      <div class="err" id="flagCommentErr"></div>
      <div class="detail-actions"><button class="btn danger" type="submit">Save flag</button><button class="btn soft" type="button" data-cancel-flag>Cancel <kbd>Esc</kbd></button></div>
    </form>
    <div class="vactions">
      <div class="vdecision ${d.tone}" id="decisionText">${esc(d.text)}</div>
      <div class="vbtns">
        ${r.decision ? '<button class="btn outline" type="button" data-undo>Undo decision</button>' : ""}
        <button class="btn danger" type="button" data-flag>Flag a problem <kbd>F</kbd></button>
        <button class="btn soft" type="button" data-step="1">Skip <kbd>J</kbd></button>
        <button class="btn primary" type="button" data-verify>${icon("check")} All values match — verified <kbd>V</kbd></button>
      </div>
    </div>`;
  markCurrentInList();
  loadPage(r);
}

const VIEW_LABELS = { row: "Row", table: "Table", page: "Whole page" };
const VIEWS = Object.keys(VIEW_LABELS);
const PX_PER_PT = 1.55; // never shrink catalogue text below about 12 px for 8 pt type (scroll sideways instead)

async function renderPart(r, view) {
  const g = await api(`/api/review/geometry?id=${encodeURIComponent(r.id)}&view=${view}`);
  if (!g.clip) return null;
  const img = new Image();
  img.alt = `${r.catalogue}, PDF page ${r.page}: ${view === "head" ? "column headings of the ordering table" : view === "row" ? `the printed row of ${r.cat_nr}` : view === "table" ? "the ordering table" : "the whole page"}`;
  img.decoding = "async";
  img.src = `/api/review/page.png?id=${encodeURIComponent(r.id)}&view=${view}`;
  await img.decode().catch(() => {});
  const part = document.createElement("div");
  part.className = `vpart vpart-${view}`;
  if (view !== "page") part.style.width = `max(100%, ${Math.round((g.clip[2] - g.clip[0]) * PX_PER_PT)}px)`;
  part.appendChild(img);
  for (const b of g.boxes) {
    const el = document.createElement("div");
    el.className = `vbox vb-${b.kind}`;
    Object.assign(el.style, vc.boxStyle(b.rect, g.clip));
    part.appendChild(el);
  }
  return { part, g };
}

async function loadPage(r) {
  const view = state.view;
  const stage = $("#stage");
  const cap = $("#pageCaption");
  const stillHere = () => state.currentId === r.id && state.view === view;
  try {
    let parts, shown = view, row;
    if (view === "row") {
      const [head, rowPart] = await Promise.all([renderPart(r, "head"), renderPart(r, "row")]);
      row = rowPart;
      parts = rowPart ? [head, rowPart].filter(Boolean) : null;
      if (!parts) { shown = "table"; parts = [await renderPart(r, "table")]; }
    } else {
      parts = [await renderPart(r, view)];
    }
    if (!stillHere()) return; // the reviewer moved on
    stage.innerHTML = "";
    stage.classList.toggle("is-row", shown === "row");
    for (const p of parts) {
      if (shown === "row") {
        const label = document.createElement("div");
        label.className = "vpart-label";
        label.textContent = p.part.classList.contains("vpart-head") ? "Column headings" : `Printed row of ${r.cat_nr}`;
        stage.appendChild(label);
      }
      stage.appendChild(p.part);
    }
    const g = parts[parts.length - 1].g;
    const found = g.row_found;
    cap.className = found ? "" : "warn";
    cap.textContent = shown === "row"
      ? `The column headings and ${r.cat_nr}'s own row, as printed (CAT NR${g.boxes.some((b) => b.kind === "ord") ? " and ORD NR" : ""} outlined in green). Switch to Table or Whole page for context.`
      : found
        ? `Highlighted: the row of ${r.cat_nr} (CAT NR${g.boxes.some((b) => b.kind === "ord") ? " and ORD NR" : ""} outlined in green). Click the image to zoom.`
        : `The row of ${r.cat_nr} could not be located automatically — find it in the table by its CAT NR. Click the image to zoom.`;
    if (view === "row" && shown !== "row") cap.textContent = `The row of ${r.cat_nr} could not be located automatically, so the whole table is shown — find it by its CAT NR.`;
  } catch (err) {
    if (stillHere()) stage.innerHTML = `<div class="vloading" role="alert">The page could not be rendered: ${esc(err.message)}</div>`;
  }
}

// ---------------------------------------------------------------- decisions
function reviewerName() {
  const input = $("#reviewer");
  const name = input.value.trim();
  input.toggleAttribute("aria-invalid", !name);
  if (!name) { input.focus(); toast("Enter your name first: every decision records who made it."); }
  return name;
}

async function decide(status, extra = {}) {
  const r = state.byId.get(state.currentId);
  if (!r || state.busy) return;
  const reviewer = reviewerName();
  if (!reviewer) return;
  const errors = vc.decisionErrors({ status, reviewer, ...extra });
  if (Object.keys(errors).length) return showFlagErrors(errors);
  const before = visible();
  state.busy = true;
  try {
    const { record, site } = await api("/api/review/decision", { id: r.id, fingerprint: r.fingerprint, status, reviewer, ...extra });
    replaceRecord(record, site);
    toast(status === "verified" ? `${r.cat_nr} verified` : `${r.cat_nr} flagged`);
    const next = vc.afterDecision(before, visible(), r.id);
    renderProgress();
    renderList();
    select(state.filter === "all" || state.filter === status ? vc.step(visible(), r.id, 1) ?? r.id : next);
  } catch (err) {
    toast(err.message);
    if (/changed since/.test(err.message)) load();
  } finally {
    state.busy = false;
  }
}

async function undo() {
  const r = state.byId.get(state.currentId);
  if (!r || state.busy) return;
  const reviewer = reviewerName();
  if (!reviewer) return;
  state.busy = true;
  try {
    const { record, site } = await api("/api/review/undo", { id: r.id, reviewer });
    replaceRecord(record, site);
    toast(`Decision on ${r.cat_nr} undone`);
    renderProgress();
    renderList();
    select(r.id);
  } catch (err) {
    toast(err.message);
  } finally {
    state.busy = false;
  }
}

function replaceRecord(record, site) {
  const i = state.records.findIndex((x) => x.id === record.id);
  if (i >= 0) state.records[i] = record;
  state.byId.set(record.id, record);
  if (site) state.site = site;
}

function showFlagErrors(errors) {
  const form = $("#flagForm");
  if (form?.hidden) openFlag();
  $("#flagFieldsErr").textContent = errors.fields || "";
  $("#flagCommentErr").textContent = errors.comment || "";
  if (errors.comment) $("#flagComment").focus();
}

function openFlag() {
  const form = $("#flagForm");
  if (!form) return;
  form.hidden = false;
  form.scrollIntoView({ block: "nearest", behavior: "smooth" });
  $("input[name=field]", form)?.focus();
}

async function publish() {
  const btn = $("#publish");
  btn.disabled = true;
  btn.textContent = "Updating…";
  try {
    const { site } = await api("/api/review/publish", {});
    toast(`Catalogue site updated: ${site.verified} verified, ${site.flagged} flagged. Reload the catalogue to see it.`);
    state.site = { ...(state.site || {}), behind: 0, verified: site.verified };
    renderProgress();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Update catalogue site";
  }
}

// ---------------------------------------------------------------- events
function wire() {
  const reviewer = $("#reviewer");
  reviewer.value = store.get("groz.reviewer", "");
  reviewer.addEventListener("input", () => { store.set("groz.reviewer", reviewer.value.trim()); reviewer.removeAttribute("aria-invalid"); });
  let typing;
  $("#q").addEventListener("input", (e) => { clearTimeout(typing); typing = setTimeout(() => { state.query = e.target.value; renderList(); }, 120); });
  $("#catFilter").addEventListener("change", (e) => { state.catalogue = e.target.value; renderList(); select(visible()[0]?.id ?? null); });
  $("#stateFilter").addEventListener("click", (e) => {
    const b = e.target.closest("[data-filter]");
    if (!b) return;
    state.filter = b.dataset.filter;
    renderList();
    const list = visible();
    select(list.some((r) => r.id === state.currentId) ? state.currentId : list[0]?.id ?? null);
  });
  $("#list").addEventListener("click", (e) => { const b = e.target.closest("[data-id]"); if (b) select(b.dataset.id); });
  $("#publish").addEventListener("click", publish);

  work.addEventListener("click", (e) => {
    const t = e.target.closest("button, .vstage");
    if (!t) return;
    if (t.matches(".vstage")) { if (!t.classList.contains("is-row")) t.classList.toggle("zoomed"); return; }
    if (t.dataset.step) { const id = vc.step(visible(), state.currentId, Number(t.dataset.step)); if (id) select(id); else toast("End of the list."); }
    else if (t.dataset.view) { state.view = t.dataset.view; store.set("groz.verify.view", state.view); select(state.currentId); }
    else if ("verify" in t.dataset) decide("verified");
    else if ("flag" in t.dataset) openFlag();
    else if ("cancelFlag" in t.dataset) { $("#flagForm").hidden = true; $("[data-flag]", work)?.focus(); }
    else if ("undo" in t.dataset) undo();
  });
  work.addEventListener("submit", (e) => {
    if (e.target.id !== "flagForm") return;
    e.preventDefault();
    const fields = $$("input[name=field]:checked", e.target).map((c) => c.value);
    decide("flagged", { comment: $("#flagComment").value, fields });
  });

  document.addEventListener("keydown", (e) => {
    if (e.target.closest?.("input, textarea, select") || e.ctrlKey || e.metaKey || e.altKey) {
      if (e.key === "Escape" && e.target.closest?.("#flagForm")) { $("#flagForm").hidden = true; $("[data-flag]", work)?.focus(); }
      return;
    }
    const k = e.key.toLowerCase();
    if (k === "v") { e.preventDefault(); decide("verified"); }
    else if (k === "f") { e.preventDefault(); openFlag(); }
    else if (k === "j" || e.key === "ArrowRight") { e.preventDefault(); const id = vc.step(visible(), state.currentId, 1); if (id) select(id); }
    else if (k === "k" || e.key === "ArrowLeft") { e.preventDefault(); const id = vc.step(visible(), state.currentId, -1); if (id) select(id); }
    else if (k === "t") { e.preventDefault(); state.view = VIEWS[(VIEWS.indexOf(state.view) + 1) % VIEWS.length]; store.set("groz.verify.view", state.view); select(state.currentId); }
    else if (e.key === "Escape" && !$("#flagForm")?.hidden) { $("#flagForm").hidden = true; }
  });
}

wire();
load();
