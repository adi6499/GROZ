// Checks the page per product (tools/build_product_pages.py): every product has one, its schema.org
// data says only what the catalogue data says (no prices, offers or ratings), and the sitemap lists them.
// Run:  node --test site/tests/pages.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";

const site = (rel) => new URL(`../${rel}`, import.meta.url);
const data = JSON.parse(readFileSync(site("data/catalogue.json"), "utf8"));
const BASE = "https://groz.tools/site/";

function productData(html) {
  const m = html.match(/<script type="application\/ld\+json">\n([\s\S]*?)\n<\/script>/);
  assert.ok(m, "the page carries schema.org data");
  return JSON.parse(m[1]);
}

test("every product has its own page, and no page is left for a product that is gone", () => {
  const files = readdirSync(site("p")).filter((f) => f.endsWith(".html") && f !== "index.html");
  assert.equal(files.length, data.products.length);
  const ids = new Set(data.products.map((p) => p.id));
  for (const f of files) assert.ok(ids.has(f.slice(0, -5)), `${f} belongs to no product`);
});

test("each page's schema.org data matches the product, and says nothing the catalogue does not", () => {
  for (const p of data.products) {
    const html = readFileSync(site(`p/${p.id}.html`), "utf8");
    const ld = productData(html);
    const url = `${BASE}p/${p.id}.html`;
    assert.equal(ld["@type"], "Product", p.id);
    assert.equal(ld.url, url);
    assert.equal(ld.brand.name, p.brand || "GROZ");
    if (p.cat_nr) assert.equal(ld.mpn, p.cat_nr);
    if (p.ord_nr) assert.equal(ld.sku, p.ord_nr);
    assert.ok(ld.category.endsWith(p.category), p.id);
    assert.equal(ld.image, p.image ? BASE + p.image.src : undefined, p.id);
    for (const key of ["offers", "aggregateRating", "review", "price", "gtin"]) assert.ok(!(key in ld), `${p.id} has ${key}`);
    for (const prop of ld.additionalProperty || []) {
      const printed = [p.dimensions_inch, p.dimensions_mm, p.box_qty == null ? null : String(p.box_qty), ...p.specs.map((s) => s.value)];
      assert.ok(printed.includes(prop.value), `${p.id}: ${prop.name} = ${prop.value} is not in the data`);
    }
    assert.ok(html.includes(`<link rel="canonical" href="${url}"/>`), p.id);
    assert.ok(html.includes(`href="../#p-${p.id}"`), `${p.id} opens in the catalogue`);
    assert.ok(html.includes("This is not the official GROZ website"), p.id);
    assert.ok(!/noindex/.test(html), p.id);
    if (p.image) assert.ok(existsSync(site(p.image.src)), `missing site/${p.image.src}`);
  }
});

test("the sitemap lists the catalogue, the product list and every product page", () => {
  const xml = readFileSync(site("sitemap.xml"), "utf8");
  const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  assert.equal(locs.length, data.products.length + 3);
  assert.equal(new Set(locs).size, locs.length);
  for (const u of [BASE, `${BASE}flipbook.html`, `${BASE}p/`]) assert.ok(locs.includes(u), u);
  for (const p of data.products) assert.ok(locs.includes(`${BASE}p/${p.id}.html`), p.id);
  const list = readFileSync(site("p/index.html"), "utf8");
  for (const p of data.products) assert.ok(list.includes(`href="${p.id}.html"`), `${p.id} is not on the list`);
});
