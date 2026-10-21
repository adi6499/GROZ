// Checks that the Vercel deployment settings keep everything the website loads.
// Run:  node --test "site/tests/*.test.mjs"
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(`../../${rel}`, import.meta.url), "utf8");

/** Whether one .vercelignore rule (gitignore syntax, as used there) leaves out `path`. */
function excludes(rule, path) {
  const anchored = rule.startsWith("/");
  let pat = rule.replace(/^\//, "");
  const dirOnly = pat.endsWith("/");
  pat = pat.replace(/\/$/, "");
  const glob = pat.split("*").map((s) => s.replace(/[.+?^${}()|[\]\\]/g, "\\$&")).join("[^/]*");
  const re = new RegExp(`^${glob}${dirOnly ? "/" : "(/|$)"}`);
  if (anchored || pat.includes("/")) return re.test(path);
  const parts = path.split("/");
  return parts.some((_, i) => re.test(parts.slice(i).join("/")));
}

test(".vercelignore keeps the page, the data, every product picture and the linked PDFs", () => {
  const rules = read(".vercelignore").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
  // Vercel did not apply a "!" re-include rule (all pictures were left out), so none may be relied on.
  assert.deepEqual(rules.filter((r) => r.startsWith("!")), []);
  // The rule that caused it would be caught here too.
  assert.ok(excludes("/output_v2/*", "output_v2/images/a.png"));
  const data = JSON.parse(read("site/data/catalogue.json"));
  const local = (href) => href.replace(/^\.\.\//, "").split("#")[0];
  const needed = new Set(["site/index.html", "site/data/catalogue.json", "site/assets/js/app.mjs",
    ...data.products.filter((p) => p.image).map((p) => local(p.image.src)),
    ...data.catalogues.map((c) => local(c.href))]);
  assert.ok(needed.size > 200, `only ${needed.size} files to check`); // 262 distinct pictures on 17 Oct 2026
  for (const path of needed) {
    for (const rule of rules) assert.ok(!excludes(rule, path), `${rule} would leave out ${path}`);
  }
});

test(".vercelignore keeps every flipbook page, thumbnail, magnifier page and PDF, and leaves out the PNG renders", () => {
  const rules = read(".vercelignore").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
  const js = read("site/assets/js/flipbook.mjs");
  const books = [...js.matchAll(/href: "\.\.\/([^"]+)",\s+folder: "([^"]+)",\s+pageCount: (\d+)/g)];
  assert.equal(books.length, 5, "five catalogues in the flipbook");
  const needed = new Set(["site/flipbook.html", "site/assets/flipbook.css", "site/assets/js/flipbook.mjs"]);
  for (const [, pdf, folder, pages] of books) {
    needed.add(pdf);
    for (let n = 1; n <= Number(pages); n++) {
      const name = `page-${String(n).padStart(2, "0")}.webp`;
      needed.add(`site/${folder}/${name}`);
      needed.add(`site/${folder}/thumbs/${name}`);
      needed.add(`site/${folder}/hires/${name}`);
      // the files the page asks for are really there (tools/build_flipbook_webp.py)
      for (const sub of ["", "thumbs/", "hires/"]) {
        assert.ok(existsSync(new URL(`../${folder}/${sub}${name}`, import.meta.url)), `missing site/${folder}/${sub}${name}`);
      }
    }
  }
  for (const path of needed) {
    for (const rule of rules) assert.ok(!excludes(rule, path), `${rule} would leave out ${path}`);
  }
  assert.ok(rules.some((r) => excludes(r, "site/assets/flipbook/lighting/page-01.png")), "PNG renders stay out of the deployment");
});
