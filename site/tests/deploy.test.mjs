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
  const local = (href) => decodeURIComponent(new URL(href, "https://site.test/site/index.html").pathname.slice(1)); // from the page
  const needed = new Set(["site/index.html", "site/data/catalogue.json", "site/assets/js/app.mjs",
    ...data.products.filter((p) => p.image).flatMap((p) => [local(p.image.src), local(p.image.thumb)]),
    ...data.catalogues.map((c) => local(c.href))]);
  // every picture is one of the clear WebP copies (tools/build_display_images.py), and it exists
  for (const p of data.products.filter((x) => x.image)) {
    assert.match(p.image.src, /^img\/full\/.+\.webp$/, p.id);
    assert.match(p.image.thumb, /^img\/thumb\/.+\.webp$/, p.id);
    for (const f of [p.image.src, p.image.thumb]) assert.ok(existsSync(new URL(`../${f}`, import.meta.url)), `missing site/${f}`);
  }
  assert.ok(needed.size > 200, `only ${needed.size} files to check`); // 262 distinct pictures on 17 Oct 2026
  for (const path of needed) {
    for (const rule of rules) assert.ok(!excludes(rule, path), `${rule} would leave out ${path}`);
  }
});

test(".vercelignore keeps every flipbook page, thumbnail, magnifier page and PDF, and leaves out the PNG renders", () => {
  const rules = read(".vercelignore").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
  const js = read("site/assets/js/flipbook.mjs");
  const books = [...js.matchAll(/href: "\.\.\/([^"]+)",\s+folder: "([^"]+)",\s+pageCount: (\d+)/g)];
  assert.equal(books.length, 7, "seven catalogues in the flipbook");
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

test("Vercel serves the site as static files, never as a Python app", () => {
  // A new Vercel project took requirements.txt for a Python app and failed (PYTHON_ENTRYPOINT_NOT_FOUND).
  const config = JSON.parse(read("vercel.json"));
  assert.ok("framework" in config && config.framework === null, 'vercel.json must set "framework": null (Other)');
  assert.ok(!config.functions && !config.builds, "no serverless functions or legacy builds");
  const rules = read(".vercelignore").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
  for (const path of ["requirements.txt", "requirements-lock.txt", "build_site_data.py", "backend/site/catalogue_export.py"]) {
    assert.ok(rules.some((rule) => excludes(rule, path)), `${path} must not be deployed`);
  }
});
