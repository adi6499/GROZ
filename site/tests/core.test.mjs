// Unit tests for the website logic.  Run:  node --test "site/tests/*.test.mjs"
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as core from "../assets/js/core.mjs";

const P = (o) => ({
  id: o.id, cat_nr: o.cat_nr, ord_nr: o.ord_nr ?? null, model_code: o.cat_nr?.replace(/\//g, "-"), heading: o.heading ?? null,
  category: o.category ?? "LED Worklights", brand: "GROZ", catalogue: { title: o.title ?? "GROZ Lighting GL-10", pdf: "x.pdf" },
  page: o.page ?? 1, printed_page: o.printed_page ?? "1", dimensions_inch: o.inch ?? null, dimensions_mm: o.mm ?? null,
  box_qty: o.box ?? null, specs: o.specs ?? [], under_review: o.review ?? [], image: o.image ?? null,
  status: o.status ?? "unverified", status_label: "Not yet verified", notes: o.notes ?? [],
});

const A = P({ id: "a", cat_nr: "LED/550", ord_nr: "55046", heading: "Worklight Impact Resistant", mm: "170 × 125", box: 10,
  specs: [{ key: "lumens", label: "Light output (lumens)", value: "1000" }, { key: "ip_rating", label: "IP rating", value: "IP54" }] });
const B = P({ id: "b", cat_nr: "LED/621", ord_nr: "55044", heading: "Worklight 270° Swivelling", page: 12,
  specs: [{ key: "ip_rating", label: "IP rating", value: "IP65" }], review: [{ key: "beam_angle", label: "Beam angle" }] });
const C = P({ id: "c", cat_nr: "EPAX-336F", category: "Striking Tools", heading: "PULASKI FIBERGLASS HANDLE", title: "Estwing Hammers E-03",
  specs: [{ key: "head_weight", label: "Head weight", value: "3.5 lb./1.58 kg" }], notes: [{ field: "ord_nr" }], status: "needs_review" });
const D = P({ id: "d", cat_nr: "SS/A/2", ord_nr: "01000", category: "Precision Tools", heading: "Machinist’s Squares", box: 200,
  specs: [{ key: "variant_label", label: "Variant (printed column)", value: "GRADE A" }], image: { src: "x.png", evidence: "direct_product" } });
const ALL = [A, B, C, D];
const INDEX = core.buildIndex(ALL);
const filters = (o = {}) => ({ ...core.emptyFilters(), ...o });
const ids = (list) => list.map((p) => p.id);

test("search matches codes in any spelling, order numbers and words", () => {
  for (const q of ["LED/621", "led 621", "LED-621", "led621", "55044"]) {
    assert.deepEqual(ids(core.filterProducts(ALL, INDEX, filters({ query: q }))), ["b"], q);
  }
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, filters({ query: "worklight" }))), ["a", "b"]);
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, filters({ query: "worklight IP65" }))), ["b"]); // every word must match
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, filters({ query: "nothing-like-this" }))), []);
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, filters({ query: "  " }))), ["a", "b", "c", "d"]);
});

test("search and filters combine (AND across filter types, OR within one facet)", () => {
  const f = filters({ query: "worklight", categories: new Set(["LED Worklights"]), facets: new Map([["ip_rating", new Set(["IP54", "IP65"])]]) });
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, f)), ["a", "b"]);
  f.facets.set("ip_rating", new Set(["IP65"]));
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, f)), ["b"]);
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, filters({ withImage: true }))), ["d"]);
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, filters({ statuses: new Set(["needs_review"]) }))), ["c"]);
  assert.deepEqual(ids(core.filterProducts(ALL, INDEX, filters({ withNotes: true }))), ["c"]);
  assert.equal(core.activeFilterCount(filters({ query: "x", withImage: true, facets: new Map([["k", new Set(["1", "2"])]]) })), 4);
});

test("facets only offer specifications with 2-14 values used by 3+ products", () => {
  const many = Array.from({ length: 4 }, (_, i) => P({ id: `m${i}`, cat_nr: `X/${i}`, specs: [
    { key: "ip_rating", label: "IP rating", value: i % 2 ? "IP54" : "IP65" },
    { key: "unique", label: "Unique", value: `v${i}` }] }));
  const groups = core.facetGroups(many);
  assert.deepEqual(groups.map((g) => g.key), ["ip_rating", "unique"]);
  assert.deepEqual(groups[0].values, [{ value: "IP54", count: 2 }, { value: "IP65", count: 2 }]);
  assert.deepEqual(core.facetGroups([A]), []); // a single value is not a useful filter
  assert.deepEqual(core.facetGroups([]), []);
});

test("sorting by code, order number (missing last) and page; default keeps catalogue order", () => {
  assert.deepEqual(ids(core.sortProducts(ALL, "code")), ["c", "a", "b", "d"]);
  assert.deepEqual(ids(core.sortProducts(ALL, "ord")), ["d", "b", "a", "c"]);
  assert.deepEqual(ids(core.sortProducts(ALL, "catalogue")), ["a", "b", "c", "d"]);
  assert.deepEqual(ids(ALL), ["a", "b", "c", "d"]); // input not mutated
});

test("card summaries only use values present in the record", () => {
  assert.deepEqual(core.summarySpecs(A), [{ label: "Light output (lumens)", value: "1000" }, { label: "IP rating", value: "IP54" }]);
  assert.deepEqual(core.summarySpecs(D), [{ label: "Variant (printed column)", value: "GRADE A" }, { label: "Box quantity", value: "200" }]);
  assert.deepEqual(core.summarySpecs(P({ id: "e", cat_nr: "Z/1" })), []);
});

test("detail rows say 'Not specified' for missing values and keep under-review values hidden", () => {
  const rows = core.detailRows(B);
  const byLabel = Object.fromEntries(rows.map((r) => [r.label, r]));
  assert.equal(byLabel["ORD NR (order number)"].text, "55044");
  assert.equal(byLabel["Size (mm)"].state, "missing");
  assert.equal(byLabel["Box quantity"].text, "Not specified");
  assert.equal(byLabel["Beam angle"].state, "review");
  assert.ok(!rows.some((r) => r.text === "270°"));
  assert.equal(core.detailRows(C).find((r) => r.label.startsWith("ORD NR")).state, "missing");
});

test("comparison uses the union of fields and handles missing ones", () => {
  const rows = core.compareRows([A, B, C]);
  const row = (label) => rows.find((r) => r.label === label);
  assert.deepEqual(row("ORD NR").cells.map((c) => c.text), ["55046", "55044", "Not specified"]);
  assert.deepEqual(row("Head weight").cells.map((c) => c.state), ["missing", "missing", "value"]);
  assert.deepEqual(row("Beam angle").cells.map((c) => c.state), ["missing", "review", "missing"]);
  assert.ok(row("Source") && row("Review status"));
  assert.equal(core.compareRows([]).length, 9);
});

test("quantities, totals and validation", () => {
  assert.equal(core.parseQty("10"), 10);
  for (const bad of ["0", "-1", "1.5", "abc", "", " ", "100000", null]) assert.equal(core.parseQty(bad), null, String(bad));
  assert.deepEqual(core.quoteTotals([{ id: "a", qty: "10" }, { id: "b", qty: 5 }, { id: "c", qty: "0" }]), { lines: 3, units: 15, invalid: 1 });
  assert.deepEqual(core.quoteTotals([]), { lines: 0, units: 0, invalid: 0 });
  const e = core.validateQuote([{ id: "a", qty: "0" }], { name: " ", email: "bad@" });
  assert.deepEqual(Object.keys(e).sort(), ["email", "name", "qty:a"]);
  assert.ok(core.validateQuote([], { name: "N", email: "n@x.com" }).items);
  assert.deepEqual(core.validateQuote([{ id: "a", qty: 2 }], { name: "N", email: "n@x.co" }), {});
});

test("prepared quotation states it was not sent and never invents an order number", () => {
  const byId = new Map(ALL.map((p) => [p.id, p]));
  const text = core.quoteText([{ id: "a", qty: 10 }, { id: "c", qty: "2" }], byId,
    { name: "Asha", email: "a@x.com", company: "", notes: "Deliver to Pune" }, new Date("2026-10-14T08:00:00Z"));
  assert.match(text, /Not sent to anyone/);
  assert.match(text, /LED\/550 {2}\| {2}ORD NR 55046 {2}\| {2}Quantity 10/);
  assert.match(text, /EPAX-336F {2}\| {2}ORD NR Not printed in catalogue/);
  assert.match(text, /Total: 2 product lines, 12 units/);
  assert.match(text, /Deliver to Pune/);
  assert.doesNotMatch(text, /Company:/); // empty fields are left out, not filled in
});

test("CSV export escapes quotes and neutralises spreadsheet formulas", () => {
  const evil = P({ id: "x", cat_nr: "=HYPERLINK(1)", heading: 'He said "hi"' });
  const csv = core.quoteCsv([{ id: "x", qty: 3 }], new Map([["x", evil]]));
  assert.match(csv, /"'=HYPERLINK\(1\)"/);
  assert.match(csv, /"He said ""hi"""/);
  assert.equal(csv.split("\r\n").length, 3);
});

test("real catalogue data: every product searchable by its own code and order number", () => {
  const data = JSON.parse(readFileSync(new URL("../data/catalogue.json", import.meta.url), "utf8"));
  const index = core.buildIndex(data.products);
  assert.equal(data.products.length, data.meta.records);
  for (const p of data.products) {
    const hits = ids(core.filterProducts(data.products, index, filters({ query: p.cat_nr })));
    assert.ok(hits.includes(p.id), `${p.cat_nr} not found by its own code`);
    if (p.ord_nr) assert.ok(ids(core.filterProducts(data.products, index, filters({ query: p.ord_nr }))).includes(p.id));
  }
  const byCategory = data.categories.map((c) => core.filterProducts(data.products, index, filters({ categories: new Set([c.name]) })).length);
  assert.deepEqual(byCategory, data.categories.map((c) => c.records));
  assert.equal(byCategory.reduce((a, b) => a + b, 0), data.products.length);
});
