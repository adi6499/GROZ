// Pure catalogue logic for the GROZ website: search, filters, sorting, comparison and quotation.
// No DOM access here, so every function can be unit-tested with `node --test "site/tests/*.test.mjs"`.
// Values are only ever read from product records; missing values are reported as missing.

export const PAGE_SIZE = 36;
export const MAX_COMPARE = 4;
export const MAX_QTY = 99999;
export const FACET_MAX_VALUES = 14;

// Which specifications summarise a product best on its card, per category. A description printed
// in the product's own table row comes first: it is what tells close variants apart.
const CARD_PRIORITY = {
  "LED Worklights": ["table_description", "lumens", "beam_distance", "run_time", "ip_rating", "battery"],
  "Tool Storage": ["table_description", "overall_load_capacity", "no_of_drawers", "top_options", "colour", "series"],
  "Striking Tools": ["head_weight", "weight", "overall_length", "length", "handle_length"],
  "Precision Tools": ["variant_label", "table_caption"],
};

export const STATUS_ORDER = ["verified", "unverified", "needs_review"];

// GROZ's own top-level categories, in the order of the main menu on groz-tools.com (India site,
// checked 17 Oct 2026), with the catalogue categories of this site that GROZ files under each:
// rolling tool cabinets and tool boxes under Mechanic's Tools, worklights under Lighting, hammers
// under Hand Tools. GROZ's menu has no place for precision measuring tools (its site search finds no
// micrometers, calipers, scribers or verniers), so Precision Tools follows GROZ's eight as a group of
// its own. A group with no categories here is not in this preview yet; `range` is what GROZ lists
// under it.
export const GROUPS = [
  { name: "Lubrication", art: "grease", categories: ["Lubrication"], range: "Grease, oil and waste-oil handling, drum handling & hose reels" },
  { name: "Fuel & DEF", art: "fuel", categories: ["Fuel & DEF"], range: "Fuel and DEF pumps, meters, nozzles & specialty pumps" },
  { name: "Air Tools", art: "air", categories: ["Air Tools"], range: "Impact wrenches & ratchets, blow guns & air control units" },
  { name: "Lighting", art: "light", categories: ["LED Worklights"] },
  { name: "Hand Tools", art: "sledge", categories: ["Striking Tools"] },
  { name: "Mechanic's Tools", art: "storage", categories: ["Tool Storage"] },
  { name: "Power Tools", art: "drill", categories: ["Power Tools"], range: "Cordless impact wrenches, drill drivers & grease guns" },
  { name: "New & Exciting", art: "spark", categories: [], range: "GROZ's newest products" },
  { name: "Precision Tools", art: "measure", categories: ["Precision Tools"] },
];

/** The group a catalogue category belongs to, or null. */
export function groupOf(category) {
  return GROUPS.find((g) => g.categories.includes(category)) || null;
}

/** The groups to show, with the categories this site has and their product counts. A group none of
 *  whose categories is in the data is `soon`. A data category that no group lists becomes a group
 *  of its own, so no product ever drops out of the navigation. */
export function siteGroups(categories) {
  const byName = new Map(categories.map((c) => [c.name, c]));
  const groups = GROUPS.map((g) => {
    const cats = g.categories.filter((name) => byName.has(name));
    return {
      name: g.name, art: g.art, categories: cats, soon: !cats.length,
      records: cats.reduce((n, name) => n + (byName.get(name).records || 0), 0),
      blurb: cats.length ? cats.map((name) => byName.get(name).blurb).filter(Boolean).join(" · ") : g.range,
    };
  });
  for (const c of categories) {
    if (!groupOf(c.name)) groups.push({ name: c.name, art: c.art, categories: [c.name], soon: false, records: c.records || 0, blurb: c.blurb || "" });
  }
  return groups;
}

export function norm(s) {
  return String(s ?? "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
}

/** Letters and digits only, upper case: "led 550", "LED-550" and "LED/550" share the key "LED550". */
export function codeKey(s) {
  return String(s ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

// One shared collator: String.localeCompare with options builds a new collator on every call,
// which made sorting all 941 products take 60-90 ms.
const COLLATOR = new Intl.Collator("en", { numeric: true, sensitivity: "base" });

export function naturalCompare(a, b) {
  return COLLATOR.compare(String(a ?? ""), String(b ?? ""));
}

/** The product's printed title (read from the catalogue page), else its extracted heading. */
export function displayTitle(p) {
  return p.title || p.heading || null;
}

/** How a product's picture should be labelled: never presents an unconfirmed image as the product. */
export function imageState(p) {
  if (p.image) return p.image.evidence === "product_family"
    ? { kind: "family", label: "Family image" } : { kind: "direct", label: "Catalogue image" };
  if (p.image_candidate_unconfirmed) return { kind: "unconfirmed", label: "Image not confirmed" };
  return { kind: "none", label: "Image unavailable" };
}

export function searchText(p) {
  return [
    p.cat_nr, p.ord_nr, p.model_code, p.title, p.heading, p.category, groupOf(p.category)?.name, p.brand, p.catalogue?.title,
    p.dimensions_inch, p.dimensions_mm,
    ...(p.specs || []).flatMap((s) => [s.label, s.value]),
  ].filter((x) => x != null && x !== "").join(" ");
}

export function buildIndex(products) {
  const index = new Map();
  for (const p of products) {
    index.set(p.id, {
      hay: norm(searchText(p)),
      codes: [p.cat_nr, p.ord_nr, p.model_code].map(codeKey).filter(Boolean),
    });
  }
  return index;
}

/** Every word of the query must match (text or product code); a whole-query code also matches. */
export function matchesQuery(entry, query) {
  const tokens = norm(query).split(/\s+/).filter(Boolean);
  if (!tokens.length) return true;
  if (!entry) return false;
  const whole = codeKey(query);
  if (whole.length >= 3 && entry.codes.some((c) => c.includes(whole))) return true;
  return tokens.every((t) => {
    if (entry.hay.includes(t)) return true;
    const k = codeKey(t);
    return k.length >= 2 && entry.codes.some((c) => c.includes(k));
  });
}

export function emptyFilters() {
  return { query: "", categories: new Set(), facets: new Map(), withImage: false, statuses: new Set(), withNotes: false };
}

export function filterProducts(products, index, f) {
  return products.filter((p) =>
    (!f.categories.size || f.categories.has(p.category)) &&
    (!f.withImage || !!p.image) &&
    (!f.statuses.size || f.statuses.has(p.status)) &&
    (!f.withNotes || (p.notes || []).length > 0) &&
    [...f.facets].every(([key, values]) => !values.size || (p.specs || []).some((s) => s.key === key && values.has(s.value))) &&
    matchesQuery(index.get(p.id), f.query));
}

export function activeFilterCount(f) {
  let n = f.categories.size + f.statuses.size + (f.withImage ? 1 : 0) + (f.withNotes ? 1 : 0) + (f.query.trim() ? 1 : 0);
  for (const values of f.facets.values()) n += values.size;
  return n;
}

/** Specification filters that make sense for the given products: 2-14 distinct values, used by 3+ products. */
export function facetGroups(products) {
  const groups = new Map();
  for (const p of products) {
    for (const s of p.specs || []) {
      if (!groups.has(s.key)) groups.set(s.key, { key: s.key, label: s.label, counts: new Map() });
      const g = groups.get(s.key);
      g.counts.set(s.value, (g.counts.get(s.value) || 0) + 1);
    }
  }
  return [...groups.values()]
    .filter((g) => g.counts.size >= 2 && g.counts.size <= FACET_MAX_VALUES && [...g.counts.values()].reduce((a, b) => a + b, 0) >= 3)
    .map((g) => ({
      key: g.key,
      label: g.label,
      values: [...g.counts].map(([value, count]) => ({ value, count })).sort((a, b) => naturalCompare(a.value, b.value)),
    }));
}

export function sortProducts(list, mode) {
  const a = [...list];
  if (mode === "code") a.sort((x, y) => naturalCompare(x.cat_nr, y.cat_nr));
  else if (mode === "ord") a.sort((x, y) => (x.ord_nr ? 0 : 1) - (y.ord_nr ? 0 : 1) || naturalCompare(x.ord_nr, y.ord_nr));
  else if (mode === "page") a.sort((x, y) => naturalCompare(x.catalogue?.title, y.catalogue?.title) || x.page - y.page);
  else if (mode === "title") a.sort((x, y) => (displayTitle(x) ? 0 : 1) - (displayTitle(y) ? 0 : 1)
    || naturalCompare(displayTitle(x), displayTitle(y)) || naturalCompare(x.cat_nr, y.cat_nr));
  return a; // "catalogue": the order of the source catalogues
}

/** Position of a product in a result list, for previous/next navigation in the detail view. */
export function neighbours(list, id) {
  const i = list.findIndex((p) => p.id === id);
  if (i < 0) return { index: -1, total: list.length, prev: null, next: null };
  return { index: i, total: list.length, prev: list[i - 1]?.id ?? null, next: list[i + 1]?.id ?? null };
}

/** Up to n label/value pairs for a product card; only values present in the record. */
export function summarySpecs(p, n = 2) {
  const out = [];
  const push = (label, value) => { if (value != null && value !== "" && out.length < n && !out.some((o) => o.label === label)) out.push({ label, value: String(value) }); };
  for (const key of CARD_PRIORITY[p.category] || []) {
    const s = (p.specs || []).find((x) => x.key === key);
    if (s) push(s.label, s.value);
  }
  if (p.dimensions_mm) push("Size (mm)", p.dimensions_mm);
  else if (p.dimensions_inch) push("Size (inch)", p.dimensions_inch);
  if (p.box_qty != null) push("Box quantity", p.box_qty);
  for (const s of p.specs || []) push(s.label, s.value);
  return out;
}

function cell(v) {
  return v == null || v === "" ? { state: "missing", text: "Not specified" } : { state: "value", text: String(v) };
}

/** Rows for the detail view: core fields always shown (missing ones say so), then the record's specs. */
export function detailRows(p) {
  const rows = [
    ["CAT NR (catalogue number)", p.cat_nr],
    ["ORD NR (order number)", p.ord_nr],
    ["Size (inch)", p.dimensions_inch],
    ["Size (mm)", p.dimensions_mm],
    ["Box quantity", p.box_qty == null ? null : String(p.box_qty)],
    ...(p.specs || []).map((s) => [s.label, s.value]),
  ].map(([label, value]) => ({ label, ...cell(value) }));
  for (const u of p.under_review || []) rows.push({ label: u.label, state: "review", text: "Under review" });
  return rows;
}

/** Comparison table rows: the union of every compared product's fields; gaps say "Not specified". */
export function compareRows(products) {
  const core = [
    ["Printed title", (p) => displayTitle(p)], ["Category", (p) => p.category], ["Brand", (p) => p.brand], ["CAT NR", (p) => p.cat_nr],
    ["ORD NR", (p) => p.ord_nr], ["Size (inch)", (p) => p.dimensions_inch], ["Size (mm)", (p) => p.dimensions_mm],
    ["Box quantity", (p) => (p.box_qty == null ? null : String(p.box_qty))],
  ];
  const keys = [];
  const labels = new Map();
  for (const p of products) {
    for (const s of [...(p.specs || []), ...(p.under_review || [])]) {
      if (!labels.has(s.key)) { labels.set(s.key, s.label); keys.push(s.key); }
    }
  }
  const rows = core.map(([label, get]) => ({ label, cells: products.map((p) => cell(get(p))) }));
  for (const key of keys) {
    rows.push({
      label: labels.get(key),
      cells: products.map((p) => {
        const s = (p.specs || []).find((x) => x.key === key);
        if (s) return cell(s.value);
        if ((p.under_review || []).some((u) => u.key === key)) return { state: "review", text: "Under review" };
        return cell(null);
      }),
    });
  }
  rows.push({ label: "Source", cells: products.map((p) => cell(`${p.catalogue?.title}, printed page ${p.printed_page ?? "not printed"} (PDF page ${p.page})`)) });
  rows.push({ label: "Review status", cells: products.map((p) => cell(p.status_label)) });
  return rows;
}

// ---------------------------------------------------------------- quotation (prepared locally only)

export function parseQty(v) {
  const s = String(v ?? "").trim();
  if (!/^\d+$/.test(s)) return null;
  const n = Number(s);
  return n >= 1 && n <= MAX_QTY ? n : null;
}

export function quoteTotals(items) {
  const valid = items.map((i) => parseQty(i.qty)).filter((q) => q != null);
  return { lines: items.length, units: valid.reduce((a, b) => a + b, 0), invalid: items.length - valid.length };
}

export function validateQuote(items, contact) {
  const errors = {};
  if (!items.length) errors.items = "Add at least one product to your quote.";
  for (const i of items) {
    if (parseQty(i.qty) == null) errors[`qty:${i.id}`] = `Enter a whole number from 1 to ${MAX_QTY}.`;
  }
  if (!String(contact.name ?? "").trim()) errors.name = "Enter your name.";
  const email = String(contact.email ?? "").trim();
  if (!email) errors.email = "Enter your email address.";
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) errors.email = "Enter a valid email address, like name@company.com.";
  return errors;
}

function productLine(p) {
  const where = `${p.catalogue?.title}, printed page ${p.printed_page ?? "not printed"} (PDF page ${p.page})`;
  return { code: p.cat_nr || "Not specified", ord: p.ord_nr || "Not printed in catalogue", heading: displayTitle(p) || "", where };
}

export function quoteText(items, byId, contact, when = new Date()) {
  const t = quoteTotals(items);
  const lines = [
    "GROZ QUOTATION REQUEST",
    "Prepared locally in the GROZ catalogue preview. Not sent to anyone.",
    `Prepared: ${when.toISOString().slice(0, 16).replace("T", " ")} UTC`,
    "",
    "CONTACT",
    ...[["Name", contact.name], ["Company", contact.company], ["Email", contact.email], ["Phone", contact.phone],
        ["Delivery location", contact.location]]
      .filter(([, v]) => String(v ?? "").trim()).map(([k, v]) => `${k}: ${String(v).trim()}`),
    "",
    "PRODUCTS",
  ];
  items.forEach((it, n) => {
    const p = byId.get(it.id);
    if (!p) return;
    const l = productLine(p);
    lines.push(`${n + 1}. ${l.code}  |  ORD NR ${l.ord}  |  Quantity ${parseQty(it.qty) ?? "invalid"}`);
    if (l.heading) lines.push(`   ${l.heading}`);
    lines.push(`   Source: ${l.where}`);
  });
  lines.push("", `Total: ${t.lines} product line${t.lines === 1 ? "" : "s"}, ${t.units} unit${t.units === 1 ? "" : "s"}`);
  if (String(contact.notes ?? "").trim()) lines.push("", "NOTES", String(contact.notes).trim());
  lines.push("", "Product data was extracted from GROZ catalogues and has not been verified. Please confirm codes, order numbers and specifications with GROZ.");
  return lines.join("\n");
}

function csvCell(v) {
  let s = String(v ?? "");
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`; // never let a spreadsheet run a value as a formula
  return `"${s.replace(/"/g, '""')}"`;
}

export function quoteCsv(items, byId) {
  const rows = [["Line", "CAT NR", "ORD NR", "Quantity", "Printed title", "Catalogue", "Printed page", "PDF page"]];
  items.forEach((it, n) => {
    const p = byId.get(it.id);
    if (!p) return;
    rows.push([n + 1, p.cat_nr ?? "", p.ord_nr ?? "", parseQty(it.qty) ?? "", displayTitle(p) ?? "", p.catalogue?.title ?? "", p.printed_page ?? "", p.page]);
  });
  return rows.map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n";
}
