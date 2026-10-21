// Tests for GROZ Interactive Flipbook configuration and assets
// Run: node --test "site/tests/*.test.mjs"

import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";

test("flipbook HTML and CSS assets exist and contain 3D flipbook structures", () => {
  assert.ok(existsSync("site/flipbook.html"), "flipbook.html should exist");
  assert.ok(existsSync("site/assets/flipbook.css"), "flipbook.css should exist");
  assert.ok(existsSync("site/assets/js/flipbook.mjs"), "flipbook.mjs should exist");

  const html = readFileSync("site/flipbook.html", "utf8");
  assert.ok(html.includes('id="bookWrap"'), "flipbook.html should contain book wrapper");
  assert.ok(html.includes('id="catalogueSelect"'), "flipbook.html should contain catalogue selector");
  assert.ok(html.includes('id="soundToggle"'), "flipbook.html should contain sound toggle");
  assert.ok(html.includes('id="ambientToggle"'), "flipbook.html should contain ambient audio toggle");
  assert.ok(html.includes('id="downloadPdfBtn"'), "flipbook.html should contain PDF download link");
  assert.ok(html.includes('id="specsDrawer"'), "flipbook.html should contain specs drawer");

  const css = readFileSync("site/assets/flipbook.css", "utf8");
  assert.ok(css.includes("perspective"), "flipbook.css should specify 3D perspective");
  assert.ok(css.includes("rotateY"), "flipbook.css should contain 3D rotateY transform rules");
  assert.ok(css.includes("preserve-3d"), "flipbook.css should preserve 3D styling");
});

test("all 4 catalogues have high-res rendered spreads available", () => {
  const catalogues = [
    { folder: "site/assets/flipbook/lighting", minPages: 40 },
    { folder: "site/assets/flipbook/storage", minPages: 30 },
    { folder: "site/assets/flipbook/estwing", minPages: 18 },
    { folder: "site/assets/flipbook/precision", minPages: 80 },
  ];

  for (const cat of catalogues) {
    assert.ok(existsSync(cat.folder), `Folder ${cat.folder} should exist`);
    const files = readdirSync(cat.folder).filter((f) => f.endsWith(".png"));
    assert.ok(files.length >= cat.minPages, `${cat.folder} has ${files.length} pages (expected >= ${cat.minPages})`);
    assert.ok(existsSync(`${cat.folder}/page-01.png`), `${cat.folder}/page-01.png must exist`);
  }
});

test("modal styling preserves uniform corner radius with custom inset scrollbars", () => {
  const css = readFileSync("site/assets/site.css", "utf8");
  assert.ok(css.includes(".modal{"), "modal style rule must exist");
  assert.ok(css.includes("overflow:hidden"), "modal must clip with overflow:hidden so all 4 corners match");
  assert.ok(css.includes("border-radius:24px"), "modal must specify 24px border radius");
  assert.ok(css.includes(".modal-body{"), "modal-body scroll container must exist");
  assert.ok(css.includes(".modal-body::-webkit-scrollbar"), "custom webkit scrollbar must be configured");
  assert.ok(css.includes("margin:12px 4px"), "scrollbar track must have margin inset so it never touches corners");
});

test("flipbook link does not produce undefined page number", () => {
  const js = readFileSync("site/assets/js/app.mjs", "utf8");
  assert.ok(!js.includes("page=${p.catalogue.page}"), "Must not use undefined p.catalogue.page");
  assert.ok(js.includes("p.page || p.catalogue?.page || 1"), "Must fallback to p.page safely");
});

test("flipbook viewer has zoom, jump to page and catalogue product isolation", () => {
  const flipJs = readFileSync("site/assets/js/flipbook.mjs", "utf8");
  assert.ok(flipJs.includes("rebuildProductsByPage"), "Must rebuild productsByPage per catalogue");
  assert.ok(flipJs.includes("toggleZoom"), "Must provide magnifier zoom functionality");
  assert.ok(flipJs.includes("jumpToPage"), "Must provide direct page-to-spread jumper");
  assert.ok(flipJs.includes("hideQuickCardImmediately"), "Must provide immediate card cleanup");
  assert.ok(flipJs.includes("back.out"), "Must animate quickCard showing with spring easing");

  const flipHtml = readFileSync("site/flipbook.html", "utf8");
  assert.ok(flipHtml.includes('id="zoomToggleBtn"'), "Must have zoom button in toolbar");
  assert.ok(flipHtml.includes('id="zoomBadge"'), "Must have zoom floating indicator");
  assert.ok(flipHtml.includes('id="jumpPopover"'), "Must have page jump popover");
  assert.ok(flipHtml.includes('id="thumbTooltip"'), "Must have thumbnail preview tooltip");
});

test("catalogue view defaults to card mode and table rows animate on load", () => {
  const appJs = readFileSync("site/assets/js/app.mjs", "utf8");
  assert.ok(appJs.includes('view: "grid"'), "Catalogue must default to card/grid mode");
  assert.ok(appJs.includes("anim.animateTableRowsOnLoad"), "Table mode must animate rows on load");

  const animJs = readFileSync("site/assets/js/animations.mjs", "utf8");
  assert.ok(animJs.includes("export function animateTableRowsOnLoad"), "animateTableRowsOnLoad must be exported");
  assert.ok(animJs.includes(".ptable tbody tr"), "initCardSparkListeners must support table rows");

  const css = readFileSync("site/assets/site.css", "utf8");
  assert.ok(css.includes(".ptable{width:100%;min-width:480px"), "Table must enforce minimum readable width on mobile");
  assert.ok(css.includes(".results{min-width:0;padding-bottom:72px}"), "Results must clear floating to-top button on mobile");
});

test("flipbook is fully mobile responsive across header, stage, bottom toolbar and drawers", () => {
  const html = readFileSync("site/flipbook.html", "utf8");
  assert.ok(html.includes('id="footerPrevBtn"'), "Footer must have mobile previous button");
  assert.ok(html.includes('id="footerNextBtn"'), "Footer must have mobile next button");
  assert.ok(html.includes("fb-btn-label-mobile"), "Must have mobile-friendly button labels");
  assert.ok(html.includes("fb-back-text-mobile"), "Must have mobile-friendly back text");

  const css = readFileSync("site/assets/flipbook.css", "utf8");
  assert.ok(css.includes("@media (max-width: 860px)"), "Must have 860px responsive breakpoint");
  assert.ok(css.includes("@media (max-width: 600px)"), "Must have 600px mobile drawer and card breakpoint");
  assert.ok(css.includes(".fb-footer-nav"), "Must style footer navigation buttons");

  const js = readFileSync("site/assets/js/flipbook.mjs", "utf8");
  assert.ok(js.includes("footerPrevBtn"), "Must wire up footer prev button");
  assert.ok(js.includes("footerNextBtn"), "Must wire up footer next button");
  assert.ok(js.includes("aspectRatio"), "Must auto-fit page panel aspect ratio on mobile");
});

test("mobile flipbook supports Tinder card swipe navigation with stamp badges and deck underlay", () => {
  const html = readFileSync("site/flipbook.html", "utf8");
  assert.ok(html.includes('id="deckUnderlay"'), "Must include stacked card deck underlay");
  assert.ok(html.includes('id="deckUnderlayImg"'), "Must include deck underlay image");
  assert.ok(html.includes('id="tinderBadgeNext"'), "Must include Tinder NEXT PAGE stamp badge");
  assert.ok(html.includes('id="tinderBadgePrev"'), "Must include Tinder PREV PAGE stamp badge");

  const css = readFileSync("site/assets/flipbook.css", "utf8");
  assert.ok(css.includes(".fb-deck-underlay"), "Must style .fb-deck-underlay");
  assert.ok(css.includes(".fb-tinder-badge.next"), "Must style next stamp badge");
  assert.ok(css.includes(".fb-tinder-badge.prev"), "Must style prev stamp badge");
  assert.ok(css.includes("cursor: grab;"), "Must set grab cursor on mobile card");

  const js = readFileSync("site/assets/js/flipbook.mjs", "utf8");
  assert.ok(js.includes("export function initTinderSwipe"), "initTinderSwipe must be exported");
  assert.ok(js.includes("initTinderSwipe()"), "initTinderSwipe must be called during initialization");
  assert.ok(js.includes("elastic.out"), "Must use elastic spring physics on snap-back");
  assert.ok(js.includes("deckUnderlayImg.src"), "Must preload underlay image for seamless card deck stack");
});


test("flipbook has a magnifying glass that shows sharper pages", () => {
  const html = readFileSync("site/flipbook.html", "utf8");
  assert.ok(html.includes('id="lensToggleBtn"'), "toolbar button for the magnifier");
  assert.ok(html.includes('id="fbLens"'), "the lens element");
  assert.ok(html.includes('id="lensBadge"'), "a hint while the magnifier is on");
  const js = readFileSync("site/assets/js/flipbook.mjs", "utf8");
  assert.ok(js.includes("export function toggleLens"), "toggleLens is exported");
  assert.ok(js.includes("/hires/page-"), "the lens loads the sharper (hires) page renders");
  assert.ok(js.includes("LENS.on) return;"), "a finger moves the lens instead of swiping while it is on");
  const css = readFileSync("site/assets/flipbook.css", "utf8");
  assert.ok(css.includes(".fb-lens {"), "the lens is styled");
});
