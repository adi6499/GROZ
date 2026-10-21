// GROZ Interactive 3D Flipbook Controller
// Realistic 3D page flip transitions, Web Audio API sound synthesis,
// scroll-triggered spec reveals, hover micro-interactions, embedded SVG tool animations,
// downloadable PDFs, and full responsive desktop/mobile support.

import * as core from "./core.mjs";
import { art } from "./art.mjs";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---------------------------------------------------------------- Catalogues Configuration
const CATALOGUES = {
  "GROZ_LIGHTING_GL-10_1.pdf": {
    id: "lighting",
    title: "GROZ Lighting GL-10",
    pdf: "GROZ_LIGHTING_GL-10_1.pdf",
    href: "../GROZ_LIGHTING_GL-10_1.pdf",
    folder: "assets/flipbook/lighting",
    pageCount: 48,
    size: "5.0 MB",
    art: "light",
    companionText: "Lighting Technology",
  },
  "tools_storage.pdf": {
    id: "storage",
    title: "GROZ Tool Storage",
    pdf: "tools_storage.pdf",
    href: "../tools_storage.pdf",
    folder: "assets/flipbook/storage",
    pageCount: 35,
    size: "14.7 MB",
    art: "storage",
    companionText: "Mechanic's Storage",
  },
  "Estwing_Hammer_E-03_Interactive_1.pdf": {
    id: "estwing",
    title: "Estwing Hammers E-03",
    pdf: "Estwing_Hammer_E-03_Interactive_1.pdf",
    href: "../Estwing_Hammer_E-03_Interactive_1.pdf",
    folder: "assets/flipbook/estwing",
    pageCount: 20,
    size: "5.4 MB",
    art: "sledge",
    companionText: "Solid Steel Striking",
  },
  "Precision_Catalogue_CA_03.pdf": {
    id: "precision",
    title: "GROZ Precision CA-03",
    pdf: "Precision_Catalogue_CA_03.pdf",
    href: "../Precision_Catalogue_CA_03.pdf",
    folder: "assets/flipbook/precision",
    pageCount: 88,
    size: "11.4 MB",
    art: "measure",
    companionText: "Precision Engineering",
  },
  "groz-lubrication-equipments.pdf": {
    id: "lubrication",
    title: "GROZ Lubrication Equipment",
    pdf: "groz-lubrication-equipments.pdf",
    href: "../groz-lubrication-equipments.pdf",
    folder: "assets/flipbook/lubrication",
    pageCount: 48,
    size: "10.3 MB",
    art: "grease",
    companionText: "Lubrication & Fuel Tech",
  },
};

// ---------------------------------------------------------------- Audio Synthesis (Web Audio API)
let audioCtx = null; // created on the first sound, after a click (browsers block audio before one)
// Page sounds play only after the visitor turns them on; the choice is shared with the catalogue page.
let sfxEnabled = (() => { try { return localStorage.getItem("groz.sound") === "on"; } catch { return false; } })();
let ambientEnabled = false;
let ambient = null; // { osc, lfo, gain } while the hum plays

function getAudioContext() {
  if (!audioCtx && typeof window !== "undefined") {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) audioCtx = new AudioContext();
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

/** Synthesizes authentic paper rustle and swoosh on page turn. */
export function playPageFlipSound() {
  if (!sfxEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const dur = 0.28;

    // Buffer of white noise for paper friction
    const bufSize = ctx.sampleRate * dur;
    const buffer = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufSize; i++) {
      data[i] = Math.random() * 2 - 1;
    }

    const noise = ctx.createBufferSource();
    noise.buffer = buffer;

    // Swept bandpass filter mimicking page movement
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.setValueAtTime(1200, now);
    filter.frequency.exponentialRampToValueAtTime(350, now + dur);
    filter.Q.setValueAtTime(2.4, now);

    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.001, now);
    gain.gain.exponentialRampToValueAtTime(0.3, now + 0.05);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + dur);

    noise.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);

    noise.start(now);
    noise.stop(now + dur);
  } catch (e) {}
}

let lastClinkTimestamp = 0;

/** Synthesizes metallic tool drop/click sound with debounce. */
export function playToolClink() {
  if (!sfxEnabled) return;
  const perfNow = typeof performance !== "undefined" ? performance.now() : Date.now();
  if (perfNow - lastClinkTimestamp < 350) return; // Prevent repetitive spamming
  lastClinkTimestamp = perfNow;

  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(1200, now);
    osc.frequency.exponentialRampToValueAtTime(380, now + 0.1);
    gain.gain.setValueAtTime(0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.13);
  } catch (e) {}
}

/** Toggles atmospheric background ambient hum. */
export function toggleAmbientAudio() {
  const ctx = getAudioContext();
  if (!ctx) return false;

  ambientEnabled = !ambientEnabled;
  const now = ctx.currentTime;
  if (ambientEnabled) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(110, now); // Low harmonic drone

    const lfo = ctx.createOscillator();
    lfo.type = "sine";
    lfo.frequency.setValueAtTime(0.2, now);
    const lfoGain = ctx.createGain();
    lfoGain.gain.setValueAtTime(4, now);
    lfo.connect(lfoGain);
    lfoGain.connect(osc.frequency);

    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.045, now + 1.2);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    lfo.start(now);
    ambient = { osc, lfo, gain };
  } else if (ambient) {
    // Fade out from where the hum is now, then stop both oscillators: the slow wobble one used to keep
    // running, and a quick off-on stopped the new hum instead of the old one.
    const { osc, lfo, gain } = ambient;
    ambient = null;
    gain.gain.cancelScheduledValues(now);
    gain.gain.setValueAtTime(Math.max(gain.gain.value, 0.0001), now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.6);
    osc.stop(now + 0.65);
    lfo.stop(now + 0.65);
  }

  const btn = $("#ambientToggle");
  if (btn) {
    btn.classList.toggle("active", ambientEnabled);
    btn.setAttribute("aria-pressed", String(ambientEnabled));
    btn.setAttribute("title", `Ambient Background Audio: ${ambientEnabled ? "On" : "Off"}`);
  }
  return ambientEnabled;
}

// ---------------------------------------------------------------- Flipbook State
export const state = {
  data: null,
  activeCatalogueKey: "GROZ_LIGHTING_GL-10_1.pdf",
  currentSpread: 1, // Desktop displays spreads (Spread 1 = Page 1 / Page 2)
  isTurning: false,
  turn: null, // the GSAP timeline of the page turn playing
  turnToken: 0, // a new number cancels a turn still waiting for its pages to decode
  zoomLevel: 1,
  singlePageMode: false,
  productsByPage: new Map(),
  artByCategory: new Map(),
};

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
/** Pages turn with motion only when GSAP is loaded and the visitor has not asked for less motion. */
const animate = () => !!window.gsap && !reduceMotion.matches;

/** The visitor's quote, shared with the catalogue page (localStorage "groz.quote": [[id, quantity], ...]). */
function readQuote() {
  try { return new Map(JSON.parse(localStorage.getItem("groz.quote") || "[]")); } catch { return new Map(); }
}
function writeQuote(quote) {
  try { localStorage.setItem("groz.quote", JSON.stringify([...quote])); return true; } catch { return false; }
}

/** Says something to screen readers (page changes, quote additions). */
function announce(text) {
  const live = $("#fbLive");
  if (live) live.textContent = text;
}

const artFor = (p) => state.artByCategory.get(p.category) || getActiveCatalogue().art;

// ---------------------------------------------------------------- Page Helpers
function getActiveCatalogue() {
  return CATALOGUES[state.activeCatalogueKey] || CATALOGUES["GROZ_LIGHTING_GL-10_1.pdf"];
}

// Pages are WebP copies of the rendered PNGs, a fifth of the size; the filmstrip uses 96 px thumbnails
// (tools/build_flipbook_webp.py makes both).
function getPageImgUrl(pageNum) {
  const cat = getActiveCatalogue();
  if (cat.folder && pageNum >= 1 && pageNum <= cat.pageCount) {
    const pad = String(pageNum).padStart(2, "0");
    return `${cat.folder}/page-${pad}.webp`;
  }
  return null;
}

function getThumbUrl(pageNum) {
  const cat = getActiveCatalogue();
  if (!cat.folder || !(pageNum >= 1 && pageNum <= cat.pageCount)) return null;
  return `${cat.folder}/thumbs/page-${String(pageNum).padStart(2, "0")}.webp`;
}

// Pages near the open spread are fetched and decoded ahead, so a turn never shows a blank page.
const warmed = new Map(); // url -> Image, most recent last (a few kept, so they stay decoded)
function warm(url) {
  let im = warmed.get(url);
  if (im) warmed.delete(url);
  else {
    im = new Image();
    im.decoding = "async";
    im.src = url;
  }
  warmed.set(url, im);
  if (warmed.size > 16) warmed.delete(warmed.keys().next().value);
  return im;
}

/** Resolves when these pages are decoded, or after `ms` at most (a slow page never holds a turn). */
function whenDecoded(urls, ms = 300) {
  const jobs = urls.filter((u) => u && !u.startsWith("data:")).map((u) => warm(u).decode?.().catch(() => {}));
  return Promise.race([Promise.all(jobs), new Promise((r) => setTimeout(r, ms))]);
}

function preloadAround() {
  const urls = [];
  for (const s of [state.currentSpread + 1, state.currentSpread - 1, state.currentSpread + 2]) {
    if (s < 1 || s > getMaxSpreads()) continue;
    const { left, right } = getPagesForSpread(s);
    urls.push(getPageImgUrl(left), getPageImgUrl(right));
  }
  const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 200));
  idle(() => urls.filter(Boolean).forEach((u) => warm(u).decode?.().catch(() => {})));
}

function getPagesForSpread(spreadIdx) {
  if (state.singlePageMode) {
    return { left: null, right: spreadIdx };
  }
  const leftPage = (spreadIdx - 1) * 2;
  const rightPage = leftPage + 1;
  return { left: leftPage > 0 ? leftPage : null, right: rightPage };
}

function getMaxSpreads() {
  const cat = getActiveCatalogue();
  // Spreads are (cover), (2,3), (4,5) ...: the last page always has a spread of its own.
  return state.singlePageMode ? cat.pageCount : Math.floor(cat.pageCount / 2) + 1;
}

/** A turn has played: the leaf goes, the new spread is drawn. */
function finishTurn(spread) {
  const leaf = $("#flipLeaf");
  if (leaf) resetLeaf(leaf);
  state.turn = null;
  state.currentSpread = spread;
  renderActiveSpread();
  state.isTurning = false;
}

/** Ends a turn at once (a jump, a catalogue switch or a resize while it plays); the caller redraws. */
function stopTurn() {
  state.turnToken += 1;
  if (!state.isTurning) return;
  state.turn?.kill();
  state.turn = null;
  const leaf = $("#flipLeaf");
  if (leaf) resetLeaf(leaf);
  const panel = $("#rightPanel");
  if (window.gsap && panel) {
    window.gsap.killTweensOf([panel, $("#deckUnderlay"), $("#tinderBadgeNext"), $("#tinderBadgePrev")].filter(Boolean));
    window.gsap.set(panel, { clearProps: "transform,opacity" });
  }
  state.isTurning = false;
}

/** Turning leaf back at rest: hidden, with no transform or shading left on it. */
function resetLeaf(leaf) {
  if (window.gsap) window.gsap.set(leaf, { clearProps: "transform" });
  leaf.style.display = "none";
  for (const id of ["#leafShadow", "#leafBackShadow", "#leafFrontGlare", "#leafBackGlare"]) {
    const el = $(id);
    if (el) el.style.opacity = "0";
  }
}

// ---------------------------------------------------------------- Render Functions
const COVER_SIDE = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='800' fill='%2314161a'%3E%3Crect width='100%25' height='100%25' fill='%2316181d'/%3E%3Ctext x='50%25' y='50%25' fill='%23555' font-family='sans-serif' font-size='18' text-anchor='middle'%3EGROZ Product Catalogue%3C/text%3E%3C/svg%3E";
const END_PAGE = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='800' fill='%2314161a'%3E%3Crect width='100%25' height='100%25' fill='%2316181d'/%3E%3Ctext x='50%25' y='50%25' fill='%23555' font-family='sans-serif' font-size='18' text-anchor='middle'%3EEnd of Catalogue%3C/text%3E%3C/svg%3E";

export function renderActiveSpread() {
  const cat = getActiveCatalogue();
  const { left, right } = getPagesForSpread(state.currentSpread);
  const leftPanel = $("#leftPanel");
  const rightPanel = $("#rightPanel");
  const leftImg = $("#leftPageImg");
  const rightImg = $("#rightPageImg");
  const leftHotspots = $("#leftHotspots");
  const rightHotspots = $("#rightHotspots");

  // Left page
  if (left && getPageImgUrl(left)) {
    leftPanel.style.display = "";
    leftImg.src = getPageImgUrl(left);
    leftImg.alt = `${cat.title} — Page ${left}`;
    renderHotspots(leftHotspots, left);
  } else {
    leftPanel.style.display = state.singlePageMode ? "none" : "";
    leftImg.src = COVER_SIDE;
    leftHotspots.innerHTML = "";
  }

  // Right page
  if (right && getPageImgUrl(right)) {
    rightPanel.style.display = "";
    rightImg.src = getPageImgUrl(right);
    rightImg.alt = `${cat.title} — Page ${right}`;
    renderHotspots(rightHotspots, right);
    if (state.singlePageMode) {
      const applyRatio = () => {
        if (rightImg.naturalWidth && rightImg.naturalHeight) {
          rightPanel.style.aspectRatio = `${rightImg.naturalWidth} / ${rightImg.naturalHeight}`;
        }
        fitDeck();
      };
      if (rightImg.complete && rightImg.naturalWidth) applyRatio();
      else rightImg.onload = applyRatio;
    } else {
      rightPanel.style.aspectRatio = "";
    }
  } else {
    rightImg.src = END_PAGE;
    rightHotspots.innerHTML = "";
    rightPanel.style.aspectRatio = "";
  }

  // Mobile Tinder Stack Deck Underlay & Stamp Badge Reset
  const deckUnderlay = $("#deckUnderlay");
  const deckUnderlayImg = $("#deckUnderlayImg");
  const badgeNext = $("#tinderBadgeNext");
  const badgePrev = $("#tinderBadgePrev");

  if (state.singlePageMode) {
    if (badgeNext) badgeNext.style.opacity = "0";
    if (badgePrev) badgePrev.style.opacity = "0";
    if (deckUnderlay && deckUnderlayImg) {
      const nextCardPage = Math.min(right + 1, cat.pageCount);
      if (right < cat.pageCount && getPageImgUrl(nextCardPage)) {
        deckUnderlay.style.display = "flex";
        deckUnderlayImg.src = getPageImgUrl(nextCardPage);
        deckUnderlayImg.alt = `${cat.title} — Page ${nextCardPage}`;
      } else {
        deckUnderlay.style.display = "none";
      }
      if (window.gsap) {
        window.gsap.set(deckUnderlay, { scale: 0.95, y: 10, opacity: 0.75, clearProps: "rotation" });
      } else {
        deckUnderlay.style.transform = "scale(0.95) translateY(10px)";
        deckUnderlay.style.opacity = "0.75";
      }
    }
    if (window.gsap && rightPanel) {
      window.gsap.set(rightPanel, { clearProps: "transform,opacity" });
    }
  } else if (deckUnderlay) {
    deckUnderlay.style.display = "none";
  }

  // Update Page Indicator
  const maxSpreads = getMaxSpreads();
  const counter = $("#pageCounter");
  if (counter) {
    if (state.singlePageMode) {
      counter.textContent = `Page ${right} of ${cat.pageCount}`;
    } else {
      const p1 = left || 1;
      const p2 = Math.min(right, cat.pageCount);
      counter.textContent = p1 === p2 ? `Page ${p1} of ${cat.pageCount}` : `Pages ${p1}–${p2} of ${cat.pageCount}`;
    }
  }

  // Update navigation button states
  const prevDisabled = state.currentSpread <= 1;
  const nextDisabled = state.currentSpread >= maxSpreads;
  if ($("#prevBtn")) $("#prevBtn").disabled = prevDisabled;
  if ($("#nextBtn")) $("#nextBtn").disabled = nextDisabled;
  if ($("#footerPrevBtn")) $("#footerPrevBtn").disabled = prevDisabled;
  if ($("#footerNextBtn")) $("#footerNextBtn").disabled = nextDisabled;

  // Update thumbnail filmstrip selection (and keep the active one in view, scrolling the strip only)
  const filmstrip = $("#filmstrip");
  $$(".fb-thumb-item").forEach((thumb, i) => {
    const on = i + 1 === state.currentSpread;
    thumb.classList.toggle("active", on);
    if (on) thumb.setAttribute("aria-current", "true");
    else thumb.removeAttribute("aria-current");
    if (on && filmstrip) {
      const strip = filmstrip.getBoundingClientRect();
      const box = thumb.getBoundingClientRect();
      if (box.left < strip.left || box.right > strip.right) {
        filmstrip.scrollBy({ left: box.left - strip.left - (strip.width - box.width) / 2, behavior: animate() ? "smooth" : "auto" });
      }
    }
  });
  if (counter) announce(counter.textContent);
  preloadAround();
  if (LENS.shown) requestLens();

  // Update Embedded Tool Companion Icon & Text
  const companionIcon = $("#companionIcon");
  const companionText = $("#companionText");
  if (companionIcon) companionIcon.innerHTML = art(cat.art);
  if (companionText) companionText.textContent = cat.companionText;

  // Render Product Specs in Drawer for the active pages
  renderDrawerSpecs([left, right].filter(Boolean));
}

// ---------------------------------------------------------------- Hotspots & Floating Cards
/** A page's products: one button on the page that lists them. The catalogue data records the page each
 *  product is printed on, not where on the page, so nothing is pinned to a made-up spot. */
function renderHotspots(container, pageNum) {
  container.replaceChildren();
  const products = state.productsByPage.get(pageNum) || [];
  if (!products.length) return;
  const count = products.length === 1 ? "1 product" : `${products.length} products`;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "fb-page-products";
  btn.dataset.page = String(pageNum);
  btn.setAttribute("aria-label", `${count} on page ${pageNum}: show codes and specifications`);
  btn.innerHTML = `<span class="fb-page-products-dot" aria-hidden="true"></span>${count} on this page`;
  btn.addEventListener("pointerenter", (e) => {
    if (e.pointerType !== "mouse") return;
    cancelHideQuickCard();
    showQuickCard(pageNum, btn);
  });
  btn.addEventListener("pointerleave", () => scheduleHideQuickCard(160));
  btn.addEventListener("click", () => {
    hideQuickCardImmediately();
    openDrawer();
    highlightDrawerProduct(products[0].id);
  });
  container.appendChild(btn);
}

const quickCard = $("#quickCard");
let activeCardProductId = null;
let hideCardTimer = null;

export function hideQuickCardImmediately() {
  clearTimeout(hideCardTimer);
  if (!quickCard) return;
  if (window.gsap) window.gsap.killTweensOf(quickCard);
  quickCard.classList.remove("active");
  quickCard.style.opacity = "0";
  quickCard.style.pointerEvents = "none";
  activeCardProductId = null;
}

function showQuickCard(pageNum, anchor) {
  clearTimeout(hideCardTimer);
  if (!quickCard) return;
  const products = state.productsByPage.get(pageNum) || [];
  if (!products.length) return;

  // If already displaying this page's card and it is visible, don't restart the animation
  const key = `page-${pageNum}`;
  if (activeCardProductId === key && quickCard.classList.contains("active")) {
    return;
  }
  activeCardProductId = key;

  const rect = anchor.getBoundingClientRect();
  const shown = products.slice(0, 4);
  const more = products.length - shown.length;
  quickCard.innerHTML = `
    <div class="fb-quick-header">
      <span class="fb-quick-badge">Page ${pageNum} · ${products.length === 1 ? "1 product" : `${products.length} products`}</span>
      <button class="fb-quick-close" type="button" aria-label="Close card">✕</button>
    </div>
    <ul class="fb-quick-list">${shown.map((p) => `
      <li><button class="fb-quick-item" type="button" data-show-product="${esc(p.id)}">
        <span class="fb-quick-thumb">${p.image?.src ? `<img src="${esc(p.image.src)}" alt="" loading="lazy"/>` : art(artFor(p))}</span>
        <span class="fb-quick-info"><span class="fb-quick-code">${esc(p.cat_nr)}</span>${p.title || p.heading ? `<span class="fb-quick-title">${esc(p.title || p.heading)}</span>` : ""}</span>
      </button></li>`).join("")}
    </ul>
    ${more > 0 ? `<div class="fb-quick-more">and ${more} more</div>` : ""}
    <button class="fb-quick-add-btn" type="button" data-open-drawer>Codes &amp; specifications</button>
  `;

  // Handle mobile bottom card positioning vs desktop anchored positioning
  const isMobile = state.singlePageMode || window.innerWidth <= 600;
  quickCard.classList.add("active");
  quickCard.style.pointerEvents = "auto";

  if (isMobile) {
    quickCard.style.left = "50%";
    quickCard.style.top = "auto";
    quickCard.style.bottom = "68px";

    if (window.gsap) {
      window.gsap.killTweensOf(quickCard);
      window.gsap.set(quickCard, { xPercent: -50, yPercent: 0 });
      window.gsap.fromTo(
        quickCard,
        { opacity: 0, scale: 0.9, y: 24 },
        { opacity: 1, scale: 1, y: 0, duration: 0.25, ease: "back.out(1.5)" }
      );
    } else {
      quickCard.style.opacity = "1";
      quickCard.style.transform = "translate(-50%, 0) scale(1)";
    }
  } else {
    // Desktop anchored position
    const cardWidth = 280;
    const pinCenterX = rect.left + rect.width / 2;
    const clampedX = Math.max(cardWidth / 2 + 16, Math.min(window.innerWidth - cardWidth / 2 - 16, pinCenterX));
    quickCard.style.left = `${clampedX}px`;
    quickCard.style.bottom = "auto";

    const isBelow = rect.top < 250;
    const targetYPercent = isBelow ? 0 : -100;
    quickCard.style.top = isBelow ? `${rect.bottom + 12}px` : `${rect.top - 12}px`;

    // ANIMATE THAT CARD WHILE SHOWING (smooth spring reveal)
    if (window.gsap) {
      window.gsap.killTweensOf(quickCard);
      window.gsap.set(quickCard, { xPercent: -50 });
      window.gsap.fromTo(
        quickCard,
        {
          opacity: 0,
          scale: 0.85,
          yPercent: targetYPercent,
          y: isBelow ? -12 : 12,
        },
        {
          opacity: 1,
          scale: 1,
          yPercent: targetYPercent,
          y: 0,
          duration: 0.28,
          ease: "back.out(1.8)",
        }
      );
    } else {
      quickCard.style.opacity = "1";
      quickCard.style.transform = `translate(-50%, ${targetYPercent}%) scale(1)`;
    }
  }

  playToolClink();
}

function scheduleHideQuickCard(delay = 140) {
  clearTimeout(hideCardTimer);
  hideCardTimer = setTimeout(() => {
    if (!quickCard || !quickCard.classList.contains("active")) return;
    if (window.gsap) {
      window.gsap.to(quickCard, {
        opacity: 0,
        scale: 0.92,
        duration: 0.16,
        ease: "power2.in",
        onComplete: () => {
          quickCard.classList.remove("active");
          quickCard.style.pointerEvents = "none";
          activeCardProductId = null;
        },
      });
    } else {
      quickCard.classList.remove("active");
      quickCard.style.pointerEvents = "none";
      activeCardProductId = null;
    }
  }, delay);
}

function cancelHideQuickCard() {
  clearTimeout(hideCardTimer);
}

// ---------------------------------------------------------------- Product Specs Drawer
function renderDrawerSpecs(pageNumbers) {
  const body = $("#drawerBody");
  if (!body) return;

  const products = [];
  pageNumbers.forEach((num) => {
    const list = state.productsByPage.get(num) || [];
    products.push(...list);
  });

  if (!products.length) {
    body.innerHTML = `
      <div class="fb-drawer-empty">
        <p>No products from ${pageNumbers.length > 1 ? "these pages" : "this page"} are in the website's product list yet.</p>
        <small>Pages with products show a “products on this page” button.</small>
      </div>`;
    return;
  }

  // Everything shown comes from the catalogue data, as on the catalogue page: no filler text, the
  // product's check status, where its picture and its row come from, and the real quote.
  const quote = readQuote();
  const cat = getActiveCatalogue();
  body.innerHTML = products.map((p) => {
    const rows = [
      ["ORD NR", p.ord_nr || "—"],
      p.dimensions_mm ? ["Dimensions", `${p.dimensions_mm} mm`] : null,
      p.box_qty ? ["Box quantity", p.box_qty] : null,
      ...(p.specs || []).map((s) => [s.label, s.value]),
    ].filter(Boolean);
    const inQuote = quote.has(p.id);
    const where = p.printed_page ? `catalogue page ${p.printed_page} (PDF page ${p.page})` : `PDF page ${p.page}`;

    return `
      <article class="fb-spec-card" id="spec-${esc(p.id)}" data-product-id="${esc(p.id)}">
        <div class="fb-spec-card-head">
          ${p.image?.src
            ? `<img class="fb-spec-thumb" src="${esc(p.image.src)}" alt="${esc(p.cat_nr)}" loading="lazy"/>`
            : `<span class="fb-spec-thumb art" aria-hidden="true">${art(artFor(p))}</span>`}
          <div class="fb-spec-details">
            <div class="fb-spec-cat">${esc(p.cat_nr)}</div>
            ${p.title || p.heading ? `<div class="fb-spec-title">${esc(p.title || p.heading)}</div>` : ""}
            <span class="fb-spec-status ${esc(p.status || "unverified")}">${esc(p.status_label || "Not yet verified")}</span>
          </div>
        </div>
        <table class="fb-spec-table">
          <tbody>${rows.map(([label, value]) => `<tr><td class="label">${esc(label)}</td><td class="val">${esc(value)}</td></tr>`).join("")}</tbody>
        </table>
        <p class="fb-spec-evidence">${p.image?.evidence_label ? `Picture: ${esc(p.image.evidence_label)}. ` : "No catalogue picture confirmed. "}Printed on ${esc(where)} ·
          <a href="${esc(p.catalogue?.href || cat.href)}" target="_blank" rel="noopener">open the PDF<span class="sr-only"> (opens in a new tab)</span></a></p>
        <button class="fb-quick-add-btn${inQuote ? " added" : ""}" type="button" data-add-quote="${esc(p.id)}"${inQuote ? " disabled" : ""}>${inQuote ? "In your quote ✓" : "Add to quote"}</button>
      </article>`;
  }).join("");

  // Staggered reveal of the cards (they are visible without it)
  const cards = $$(".fb-spec-card", body);
  if (animate()) {
    window.gsap.fromTo(cards,
      { opacity: 0, y: 18 },
      { opacity: 1, y: 0, duration: 0.38, stagger: 0.05, ease: "power2.out", clearProps: "opacity,transform" }
    );
  }
}

let drawerReturn = null; // where focus goes back to when the drawer closes

export function openDrawer() {
  const drawer = $("#specsDrawer");
  if (!drawer || drawer.classList.contains("open")) return;
  drawerReturn = document.activeElement;
  drawer.classList.add("open");
  drawer.inert = false; // closed, it is inert: off screen and out of the tab order
  const btn = $("#openSpecsBtn");
  btn?.classList.add("active");
  btn?.setAttribute("aria-expanded", "true");
  $("#drawerClose")?.focus({ preventScroll: true });
}

export function closeDrawer() {
  const drawer = $("#specsDrawer");
  if (!drawer || !drawer.classList.contains("open")) return;
  const hadFocus = drawer.contains(document.activeElement);
  drawer.classList.remove("open");
  drawer.inert = true;
  const btn = $("#openSpecsBtn");
  btn?.classList.remove("active");
  btn?.setAttribute("aria-expanded", "false");
  const back = drawerReturn && drawerReturn !== document.body && document.contains(drawerReturn) ? drawerReturn : btn;
  if (hadFocus) back?.focus({ preventScroll: true });
}

function highlightDrawerProduct(id) {
  const card = document.getElementById(`spec-${id}`);
  const body = $("#drawerBody");
  if (card && body) {
    // Scroll the drawer's own list only. scrollIntoView also scrolled the stage sideways (the drawer is
    // still sliding in from off screen), which pushed the whole book out of view.
    const top = card.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop - 8;
    body.scrollTo({ top, behavior: animate() ? "smooth" : "auto" });
    if (animate()) {
      card.animate(
        [{ transform: "scale(0.97)", boxShadow: "0 0 0 2px #f4511e" }, { transform: "none", boxShadow: "0 0 0 2px #f4511e00" }],
        { duration: 700, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" }
      );
    }
  }
}

// ---------------------------------------------------------------- 3D Page Flip Engine (Real Curved Physical Turn)
export function flipToNext() {
  if (state.isTurning) return;
  const maxSpreads = getMaxSpreads();
  if (state.currentSpread >= maxSpreads) return;

  state.isTurning = true;
  playPageFlipSound();

  if (state.singlePageMode) {
    const nextSpread = state.currentSpread + 1;
    hideQuickCardImmediately();
    const rightPanel = $("#rightPanel");
    const deckUnderlay = $("#deckUnderlay");
    const badgeNext = $("#tinderBadgeNext");

    if (animate() && rightPanel) {
      if (badgeNext) {
        window.gsap.to(badgeNext, { opacity: 1, duration: 0.1 });
      }
      if (deckUnderlay) {
        window.gsap.to(deckUnderlay, { scale: 1, y: 0, opacity: 1, duration: 0.28, ease: "power2.out" });
      }
      window.gsap.to(rightPanel, {
        x: -window.innerWidth * 1.25,
        y: 35,
        rotation: -22,
        opacity: 0,
        duration: 0.28,
        ease: "power2.in",
        onComplete: () => {
          state.currentSpread = nextSpread;
          renderActiveSpread();
          window.gsap.set(rightPanel, { clearProps: "transform,opacity" });
          if (badgeNext) badgeNext.style.opacity = "0";
          state.isTurning = false;
        },
      });
    } else {
      state.currentSpread = nextSpread;
      renderActiveSpread();
      state.isTurning = false;
    }
    return;
  }

  const leaf = $("#flipLeaf");
  const frontImg = $("#leafFrontImg");
  const backImg = $("#leafBackImg");
  const shadow = $("#leafShadow");
  const frontGlare = $("#leafFrontGlare");
  const backGlare = $("#leafBackGlare");

  // Configure leaf images
  const { right: currentRight } = getPagesForSpread(state.currentSpread);
  const nextSpread = state.currentSpread + 1;
  const { left: nextLeft, right: nextRight } = getPagesForSpread(nextSpread);
  hideQuickCardImmediately();
  if (!animate()) { finishTurn(nextSpread); return; } // less motion: the next spread at once

  const frontUrl = getPageImgUrl(currentRight) || END_PAGE;
  const backUrl = getPageImgUrl(nextLeft || nextRight) || COVER_SIDE;
  const underUrl = getPageImgUrl(nextRight) || END_PAGE;
  const token = state.turnToken;
  // The turn starts once its three pages are decoded (they usually are: preloadAround), so the
  // turning page is never blank; then they are swapped in together, in one frame.
  whenDecoded([frontUrl, backUrl, underUrl]).then(() => {
    if (token !== state.turnToken) return; // stopped meanwhile (stopTurn)
    if (frontImg) frontImg.src = frontUrl;
    if (backImg) backImg.src = backUrl;
    // Underneath the lifting page, the next right-hand page is already there (or the end).
    const rightImg = $("#rightPageImg");
    if (rightImg) rightImg.src = underUrl;
    $("#rightHotspots")?.replaceChildren();
    leaf.style.display = "block";
    turnForward(leaf, nextSpread, shadow, frontGlare, backGlare);
  });
}

function turnForward(leaf, nextSpread, shadow, frontGlare, backGlare) {
  // Multi-phase physical curved turn:
  // 1. Initial corner peel: corner lifts & paper flexes
  // 2. High curved arch: translateZ lifts up into 3D space, casting sweeping shadow
  // 3. Roll-down settle: rolls onto left spread with natural deceleration
  // finishTurn clears only what the turn set: clearProps "all" also wiped the inline display:none and
  // left the finished leaf lying over the new right-hand page.
  const tl = window.gsap.timeline({ onComplete: () => finishTurn(nextSpread) });
  state.turn = tl;

  // No CSS filter on the leaf: a filter flattens its 3D faces (the back page never showed) and a
  // blurred drop-shadow is repainted on every frame. The shadow layer below does the shading.
  window.gsap.set(leaf, { rotateY: 0, rotateZ: 0, skewY: 0, translateZ: 0 });

  tl.to(leaf, {
    rotateY: -90,
    translateZ: 85, // Authentic curved 3D arch
    rotateZ: -3.5, // Diagonal corner lift
    skewY: 4.5, // Paper flex & curl drag
    duration: 0.32,
    ease: "power2.in",
    onUpdate: function () {
      const p = this.progress();
      if (shadow) shadow.style.opacity = String(p * 0.85);
      if (frontGlare) frontGlare.style.opacity = String(p * 0.75);
    },
  }).to(leaf, {
    rotateY: -180,
    translateZ: 0,
    rotateZ: 0,
    skewY: 0,
    duration: 0.34,
    ease: "power2.out",
    onUpdate: function () {
      const p = this.progress();
      if (shadow) shadow.style.opacity = String((1 - p) * 0.85);
      if (backGlare) backGlare.style.opacity = String((1 - p) * 0.75);
    },
  });
}

export function flipToPrev() {
  if (state.isTurning || state.currentSpread <= 1) return;

  state.isTurning = true;
  playPageFlipSound();

  if (state.singlePageMode) {
    const prevSpread = state.currentSpread - 1;
    hideQuickCardImmediately();
    const rightPanel = $("#rightPanel");
    const deckUnderlay = $("#deckUnderlay");
    const deckUnderlayImg = $("#deckUnderlayImg");
    const badgePrev = $("#tinderBadgePrev");

    if (deckUnderlay && deckUnderlayImg) {
      const prevUrl = getPageImgUrl(prevSpread);
      if (prevUrl) {
        deckUnderlayImg.src = prevUrl;
        deckUnderlay.style.display = "flex";
      }
    }

    if (animate() && rightPanel) {
      if (badgePrev) {
        window.gsap.to(badgePrev, { opacity: 1, duration: 0.1 });
      }
      if (deckUnderlay) {
        window.gsap.to(deckUnderlay, { scale: 1, y: 0, opacity: 1, duration: 0.28, ease: "power2.out" });
      }
      window.gsap.to(rightPanel, {
        x: window.innerWidth * 1.25,
        y: 35,
        rotation: 22,
        opacity: 0,
        duration: 0.28,
        ease: "power2.in",
        onComplete: () => {
          state.currentSpread = prevSpread;
          renderActiveSpread();
          window.gsap.set(rightPanel, { clearProps: "transform,opacity" });
          if (badgePrev) badgePrev.style.opacity = "0";
          state.isTurning = false;
        },
      });
    } else {
      state.currentSpread = prevSpread;
      renderActiveSpread();
      state.isTurning = false;
    }
    return;
  }

  const leaf = $("#flipLeaf");
  const frontImg = $("#leafFrontImg");
  const backImg = $("#leafBackImg");
  const shadow = $("#leafShadow");
  const frontGlare = $("#leafFrontGlare");
  const backGlare = $("#leafBackGlare");

  const prevSpread = state.currentSpread - 1;
  const { left: prevLeft, right: prevRight } = getPagesForSpread(prevSpread);
  const { left: currentLeft } = getPagesForSpread(state.currentSpread);
  hideQuickCardImmediately();
  if (!animate()) { finishTurn(prevSpread); return; } // less motion: the previous spread at once

  const frontUrl = getPageImgUrl(prevRight) || END_PAGE;
  const backUrl = getPageImgUrl(currentLeft) || COVER_SIDE;
  const underUrl = getPageImgUrl(prevLeft) || COVER_SIDE;
  const token = state.turnToken;
  whenDecoded([frontUrl, backUrl, underUrl]).then(() => {
    if (token !== state.turnToken) return; // stopped meanwhile (stopTurn)
    if (frontImg) frontImg.src = frontUrl;
    if (backImg) backImg.src = backUrl;
    // Underneath the lifting page, the previous left-hand page is already there (or the cover side).
    const leftImg = $("#leftPageImg");
    if (leftImg) leftImg.src = underUrl;
    $("#leftHotspots")?.replaceChildren();
    leaf.style.display = "block";
    turnBackward(leaf, prevSpread, shadow, frontGlare, backGlare);
  });
}

function turnBackward(leaf, prevSpread, shadow, frontGlare, backGlare) {
  const tl = window.gsap.timeline({ onComplete: () => finishTurn(prevSpread) });
  state.turn = tl;

  window.gsap.set(leaf, { rotateY: -180, rotateZ: 0, skewY: 0, translateZ: 0 });

  tl.to(leaf, {
    rotateY: -90,
    translateZ: 85, // Curved 3D arch lift
    rotateZ: 3.5, // Natural backward corner flex
    skewY: -4.5,
    duration: 0.32,
    ease: "power2.in",
    onUpdate: function () {
      const p = this.progress();
      if (shadow) shadow.style.opacity = String(p * 0.85);
      if (backGlare) backGlare.style.opacity = String(p * 0.75);
    },
  }).to(leaf, {
    rotateY: 0,
    translateZ: 0,
    rotateZ: 0,
    skewY: 0,
    duration: 0.34,
    ease: "power2.out",
    onUpdate: function () {
      const p = this.progress();
      if (shadow) shadow.style.opacity = String((1 - p) * 0.85);
      if (frontGlare) frontGlare.style.opacity = String((1 - p) * 0.75);
    },
  });
}

export function jumpToSpread(spreadIdx) {
  if (spreadIdx < 1 || spreadIdx > getMaxSpreads()) return;
  const wasTurning = state.isTurning;
  stopTurn(); // a turn still playing would otherwise land on its own spread after the jump
  if (spreadIdx === state.currentSpread && !wasTurning) return;
  hideQuickCardImmediately();
  state.currentSpread = spreadIdx;
  playPageFlipSound();
  renderActiveSpread();
}

export function jumpToPage(pageNum) {
  const cat = getActiveCatalogue();
  const page = Math.max(1, Math.min(pageNum, cat.pageCount));
  const targetSpread = state.singlePageMode ? page : Math.floor(page / 2) + 1;
  jumpToSpread(targetSpread);
}

// ---------------------------------------------------------------- Filter Catalogue Products
function rebuildProductsByPage() {
  state.productsByPage.clear();
  if (!state.data || !state.data.products) return;

  for (const p of state.data.products) {
    // Strictly isolate products to the currently selected catalogue PDF!
    if (p.catalogue?.pdf !== state.activeCatalogueKey) continue;
    const page = p.page;
    if (!page) continue;
    const list = state.productsByPage.get(page) || [];
    list.push(p);
    state.productsByPage.set(page, list);
  }
}

// ---------------------------------------------------------------- Thumbnail Filmstrip
function renderFilmstrip() {
  const filmstrip = $("#filmstrip");
  if (!filmstrip) return;

  const cat = getActiveCatalogue();
  const maxSpreads = getMaxSpreads();
  const items = [];
  const tooltip = $("#thumbTooltip");

  for (let s = 1; s <= maxSpreads; s++) {
    const { left, right } = getPagesForSpread(s);
    const imgUrl = getThumbUrl(right) || getThumbUrl(left) || "";
    const label = state.singlePageMode ? `Page ${right}` : (!left ? "Cover" : right > cat.pageCount ? `Page ${left}` : `Pages ${left}–${right}`);
    items.push(`
      <button type="button" class="fb-thumb-item${s === state.currentSpread ? " active" : ""}" data-spread="${s}" data-label="${label}" aria-label="${label}">
        <img src="${esc(imgUrl)}" alt="" loading="lazy" decoding="async"/>
      </button>`);
  }

  filmstrip.innerHTML = items.join("");
}

/** The filmstrip's listeners, added once (renderFilmstrip runs again for every catalogue and resize). */
function bindFilmstrip() {
  const filmstrip = $("#filmstrip");
  const tooltip = $("#thumbTooltip");
  if (!filmstrip) return;

  filmstrip.addEventListener("click", (e) => {
    const item = e.target.closest("[data-spread]");
    if (item) jumpToSpread(Number(item.dataset.spread));
  });

  // Thumbnail hover tooltip
  filmstrip.addEventListener("pointermove", (e) => {
    const item = e.target.closest("[data-spread]");
    if (item && tooltip) {
      tooltip.textContent = item.dataset.label || "";
      tooltip.style.left = `${e.clientX}px`;
      tooltip.style.top = `${e.clientY}px`;
      tooltip.style.display = "block";
    } else if (tooltip) {
      tooltip.style.display = "none";
    }
  });

  filmstrip.addEventListener("pointerleave", () => {
    if (tooltip) tooltip.style.display = "none";
  });
}

// ---------------------------------------------------------------- Catalogue Switcher
export function switchCatalogue(pdfKey) {
  if (!CATALOGUES[pdfKey]) return;
  stopTurn();
  hideQuickCardImmediately();
  toggleZoom(false);
  state.activeCatalogueKey = pdfKey;
  state.currentSpread = 1;

  rebuildProductsByPage();

  const cat = CATALOGUES[pdfKey];
  const downloadLink = $("#downloadPdfBtn");
  if (downloadLink) {
    downloadLink.href = cat.href;
    downloadLink.setAttribute("download", cat.pdf);
    const label = $("#downloadPdfLabel");
    if (label) {
      label.textContent = `Download PDF (${cat.size})`;
    } else {
      downloadLink.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4v12m-5-5l5 5 5-5M4 20h16"/></svg><span class="fb-btn-label" id="downloadPdfLabel">Download PDF (${cat.size})</span><span class="fb-btn-label-mobile">PDF</span>`;
    }
  }

  const select = $("#catalogueSelect");
  if (select && select.value !== pdfKey) {
    select.value = pdfKey;
  }
  $("#jumpPageInput")?.setAttribute("max", String(cat.pageCount));

  renderFilmstrip();
  renderActiveSpread();
}

// ---------------------------------------------------------------- Magnifier Zoom & Pan
let isZoomed = false;

export function toggleZoom(force) {
  const next = typeof force === "boolean" ? force : !isZoomed;
  if (next === isZoomed) return;
  isZoomed = next;
  if (isZoomed) toggleLens(false);

  const stage = $(".fb-stage");
  const wrap = $("#bookWrap");
  const badge = $("#zoomBadge");
  const btn = $("#zoomToggleBtn");

  stage?.classList.toggle("zoomed", isZoomed);
  btn?.classList.toggle("active", isZoomed);
  if (badge) badge.style.display = isZoomed ? "flex" : "none";

  hideQuickCardImmediately();

  // Exactly the 2x the button says. (No CSS transition on the wrapper: it re-timed these tweens.)
  if (wrap) {
    const to = { scale: isZoomed ? ZOOM : 1, x: 0, y: 0, overwrite: "auto" };
    if (animate()) window.gsap.to(wrap, { ...to, duration: isZoomed ? 0.32 : 0.28, ease: "power2.out" });
    else if (window.gsap) window.gsap.set(wrap, to);
    else wrap.style.transform = isZoomed ? `scale(${ZOOM})` : "";
  }
}

const ZOOM = 2;

/** Zoomed in, the pointer's place over the stage chooses which part of the page is in view: from one
 *  edge of the enlarged page to the other, wherever the pointer is. */
function panZoomed(e) {
  if (!isZoomed || !window.gsap) return;
  const wrap = $("#bookWrap");
  const stage = $(".fb-stage");
  if (!wrap || !stage) return;
  const box = stage.getBoundingClientRect();
  const rx = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width)) - 0.5;
  const ry = Math.min(1, Math.max(0, (e.clientY - box.top) / box.height)) - 0.5;
  const maxX = Math.max(0, (wrap.offsetWidth * ZOOM - box.width) / 2);
  const maxY = Math.max(0, (wrap.offsetHeight * ZOOM - box.height) / 2);
  window.gsap.to(wrap, { x: -rx * 2 * maxX, y: -ry * 2 * maxY, duration: animate() ? 0.35 : 0, ease: "power3.out", overwrite: "auto" });
}

// ---------------------------------------------------------------- Magnifying glass
// A round lens follows the pointer over a page and shows that spot enlarged (scroll, or + and -, to
// change how much). Inside it the page is drawn sharper: a 200 DPI render (hires/), fetched only for a
// page someone looks at; until it has arrived the lens shows the page already on screen. On a touch
// screen, hold a finger on the page: the lens floats above it.
const LENS = { on: false, active: false, zoom: 2.5, min: 1.5, max: 5, x: 0, y: 0, touch: false, raf: 0, shown: false, url: "" };
const sharp = new Map(); // hi-res page url -> its decoded Image, or "loading" / "failed"

function getHiresUrl(pageNum) {
  const cat = getActiveCatalogue();
  if (!cat.folder || !(pageNum >= 1 && pageNum <= cat.pageCount)) return null;
  return `${cat.folder}/hires/page-${String(pageNum).padStart(2, "0")}.webp`;
}

/** Where the page in `img` is drawn on screen (the image is fitted inside its box: object-fit contain). */
function drawnBox(img) {
  const r = img.getBoundingClientRect();
  const nw = img.naturalWidth;
  const nh = img.naturalHeight;
  if (!nw || !nh || !r.width || !r.height) return null;
  const s = Math.min(r.width / nw, r.height / nh);
  const w = nw * s;
  const h = nh * s;
  return { left: r.left + (r.width - w) / 2, top: r.top + (r.height - h) / 2, width: w, height: h };
}

/** The catalogue page under a point on screen, if any. */
function pageAt(x, y) {
  const { left, right } = getPagesForSpread(state.currentSpread);
  for (const [img, page] of [[$("#rightPageImg"), right], [$("#leftPageImg"), left]]) {
    if (!img || !page || !getPageImgUrl(page) || img.offsetParent === null) continue;
    const box = drawnBox(img);
    if (box && x >= box.left && x <= box.left + box.width && y >= box.top && y <= box.top + box.height) return { page, box };
  }
  return null;
}

/** The sharp page once it is decoded; meanwhile the page already on screen (and the sharp one is fetched). */
function lensUrl(page) {
  const hi = getHiresUrl(page);
  const got = sharp.get(hi);
  if (got instanceof Image) return hi;
  if (!got && hi) {
    sharp.set(hi, "loading");
    const im = new Image();
    im.decoding = "async";
    im.src = hi;
    im.decode().then(() => {
      sharp.set(hi, im);
      for (const [url, v] of sharp) if (sharp.size > 8 && v instanceof Image && url !== hi) sharp.delete(url);
      requestLens();
    }, () => sharp.set(hi, "failed"));
  }
  return getPageImgUrl(page);
}

function requestLens() {
  if (!LENS.raf) LENS.raf = requestAnimationFrame(drawLens);
}

/** Once per display frame at most: the lens moves to the pointer and shows the spot under it. */
function drawLens() {
  LENS.raf = 0;
  const lens = $("#fbLens");
  if (!lens) return;
  const hit = LENS.on && LENS.active && !state.isTurning ? pageAt(LENS.x, LENS.y) : null;
  if (!hit) {
    showLens(lens, false);
    return;
  }
  const size = lens.offsetWidth;
  const url = lensUrl(hit.page);
  if (url !== LENS.url) {
    lens.style.backgroundImage = `url("${url}")`;
    LENS.url = url;
  }
  const bw = hit.box.width * LENS.zoom;
  const bh = hit.box.height * LENS.zoom;
  const fx = (LENS.x - hit.box.left) / hit.box.width;
  const fy = (LENS.y - hit.box.top) / hit.box.height;
  lens.style.backgroundSize = `${bw}px ${bh}px`;
  lens.style.backgroundPosition = `${size / 2 - fx * bw}px ${size / 2 - fy * bh}px`;
  // On a touch screen the lens floats above the finger, which would otherwise cover that very spot.
  const lift = LENS.touch ? size * 0.7 : 0;
  // The place goes in `translate` (applied after the CSS scale), so the lens grows in place when it appears.
  lens.style.translate = `${LENS.x - size / 2}px ${LENS.y - size / 2 - lift}px`;
  showLens(lens, true);
}

function showLens(lens, on) {
  if (LENS.shown === on) return;
  LENS.shown = on;
  lens.classList.toggle("show", on);
}

function setLensZoom(z) {
  LENS.zoom = Math.min(LENS.max, Math.max(LENS.min, z));
  const chip = $("#fbLensZoom");
  if (chip) chip.textContent = `${LENS.zoom.toFixed(1).replace(/\.0$/, "")}×`;
  requestLens();
}

/** Turns the magnifying glass on or off (it and the 2x zoom take turns). */
export function toggleLens(force) {
  const next = typeof force === "boolean" ? force : !LENS.on;
  if (next === LENS.on) return;
  LENS.on = next;
  LENS.active = false;
  if (next) {
    toggleZoom(false);
    hideQuickCardImmediately();
  }
  $(".fb-stage")?.classList.toggle("lens-on", next);
  const btn = $("#lensToggleBtn");
  btn?.classList.toggle("active", next);
  btn?.setAttribute("aria-pressed", String(next));
  const badge = $("#lensBadge");
  if (badge) badge.style.display = next ? "flex" : "none";
  announce(next ? "Magnifying glass on. Move over a page to enlarge it; scroll, or press plus and minus, to change how much." : "Magnifying glass off.");
  requestLens();
}

function initLens() {
  const wrap = $("#bookWrap");
  if (!wrap) return;
  const track = (e) => {
    LENS.x = e.clientX;
    LENS.y = e.clientY;
    LENS.touch = e.pointerType !== "mouse";
  };
  wrap.addEventListener("pointermove", (e) => {
    if (!LENS.on) return;
    if (e.pointerType === "mouse") LENS.active = true;
    else if (!LENS.active) return; // a finger shows the lens only while it is down
    track(e);
    requestLens();
  });
  wrap.addEventListener("pointerdown", (e) => {
    if (!LENS.on || e.pointerType === "mouse") return;
    LENS.active = true;
    track(e);
    requestLens();
  });
  const end = () => {
    if (!LENS.on) return;
    LENS.active = false;
    requestLens();
  };
  wrap.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") end(); });
  wrap.addEventListener("pointerup", (e) => { if (e.pointerType !== "mouse") end(); });
  wrap.addEventListener("pointercancel", end);
  // Scrolling over the lens (or pinching on a trackpad) changes how much it enlarges.
  wrap.addEventListener("wheel", (e) => {
    if (!LENS.on || !LENS.shown) return;
    e.preventDefault();
    setLensZoom(LENS.zoom * (e.deltaY < 0 ? 1.12 : 1 / 1.12));
  }, { passive: false });
  $("#lensToggleBtn")?.addEventListener("click", () => toggleLens());
  $("#lensOffBtn")?.addEventListener("click", () => toggleLens(false));
}

// ---------------------------------------------------------------- Fullscreen & Responsive
export function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

function handleResize() {
  hideQuickCardImmediately();
  const isMobile = window.matchMedia("(max-width: 860px)").matches;
  if (state.singlePageMode !== isMobile) {
    stopTurn();
    // Preserve the current viewed page when switching between dual spread and single page
    const currentPage = state.singlePageMode ? state.currentSpread : (state.currentSpread - 1) * 2 + 1;
    state.singlePageMode = isMobile;
    const newSpread = isMobile ? currentPage : Math.floor(currentPage / 2) + 1;
    state.currentSpread = Math.max(1, Math.min(newSpread, getMaxSpreads()));
    renderFilmstrip();
    renderActiveSpread();
  }
  fitDeck();
}

/** Phones: the card waiting underneath has the size and place of the page card on top (it filled the
 *  whole book area, a large grey slab around landscape pages). Layout sizes, so a swipe's transform
 *  does not change them. */
function fitDeck() {
  const deck = $("#deckUnderlay");
  const panel = $("#rightPanel");
  if (!deck || !panel || !state.singlePageMode) return;
  deck.style.inset = "auto";
  deck.style.left = `${panel.offsetLeft}px`;
  deck.style.top = `${panel.offsetTop}px`;
  deck.style.width = `${panel.offsetWidth}px`;
  deck.style.height = `${panel.offsetHeight}px`;
}

// ---------------------------------------------------------------- Mobile Tinder Card Swipe Engine
export function initTinderSwipe() {
  const rightPanel = $("#rightPanel");
  if (!rightPanel) return;

  let isPointerDown = false;
  let isSwiping = false;
  let startX = 0;
  let startY = 0;
  let currentX = 0;
  let currentY = 0;
  let activePointerId = null;

  const deckUnderlay = $("#deckUnderlay");
  const deckUnderlayImg = $("#deckUnderlayImg");
  const badgeNext = $("#tinderBadgeNext");
  const badgePrev = $("#tinderBadgePrev");

  function resetCardAndDeck(elastic = true) {
    elastic = elastic && animate();
    isPointerDown = false;
    isSwiping = false;
    activePointerId = null;
    rightPanel.classList.remove("swiping");

    if (window.gsap) {
      if (elastic) {
        window.gsap.to(rightPanel, {
          x: 0,
          y: 0,
          rotation: 0,
          duration: 0.46,
          ease: "elastic.out(1, 0.6)",
          overwrite: "auto",
          onComplete: () => {
            window.gsap.set(rightPanel, { clearProps: "transform" });
          },
        });
        if (deckUnderlay) {
          window.gsap.to(deckUnderlay, {
            scale: 0.95,
            y: 10,
            opacity: 0.75,
            duration: 0.32,
            ease: "power2.out",
            overwrite: "auto",
          });
        }
      } else {
        window.gsap.set(rightPanel, { clearProps: "transform,opacity" });
        if (deckUnderlay) {
          window.gsap.set(deckUnderlay, { scale: 0.95, y: 10, opacity: 0.75 });
        }
      }
      if (badgeNext) window.gsap.to(badgeNext, { opacity: 0, duration: 0.15 });
      if (badgePrev) window.gsap.to(badgePrev, { opacity: 0, duration: 0.15 });
    } else {
      rightPanel.style.transform = "";
      if (deckUnderlay) {
        deckUnderlay.style.transform = "scale(0.95) translateY(10px)";
        deckUnderlay.style.opacity = "0.75";
      }
      if (badgeNext) badgeNext.style.opacity = "0";
      if (badgePrev) badgePrev.style.opacity = "0";
    }
  }

  rightPanel.addEventListener("pointerdown", (e) => {
    if (!state.singlePageMode || state.isTurning || LENS.on) return;
    if (e.button !== 0 && e.pointerType === "mouse") return;
    if (e.target.closest(".fb-page-products") || e.target.closest("#quickCard") || e.target.closest("button")) return;

    isPointerDown = true;
    isSwiping = false;
    activePointerId = e.pointerId;
    startX = e.clientX;
    startY = e.clientY;
    currentX = e.clientX;
    currentY = e.clientY;

    if (window.gsap) {
      window.gsap.killTweensOf(rightPanel);
      if (deckUnderlay) window.gsap.killTweensOf(deckUnderlay);
    }
  });

  window.addEventListener("pointermove", (e) => {
    if (!isPointerDown || e.pointerId !== activePointerId) return;

    currentX = e.clientX;
    currentY = e.clientY;
    const dx = currentX - startX;
    const dy = currentY - startY;

    if (!isSwiping) {
      if (Math.hypot(dx, dy) < 8) return;
      if (Math.abs(dy) > Math.abs(dx) * 1.4) {
        // Scrolling vertically: cancel Tinder swiping cleanly
        isPointerDown = false;
        activePointerId = null;
        return;
      }
      isSwiping = true;
      rightPanel.classList.add("swiping");
      hideQuickCardImmediately();
    }

    const maxSpreads = getMaxSpreads();
    let effectiveDx = dx;
    if ((dx > 0 && state.currentSpread <= 1) || (dx < 0 && state.currentSpread >= maxSpreads)) {
      effectiveDx = dx * 0.28; // Rubberband resistance at edges
    }

    const rotateDeg = Math.max(-25, Math.min(25, effectiveDx * 0.08));
    const followY = dy * 0.28;

    if (window.gsap) {
      window.gsap.set(rightPanel, {
        x: effectiveDx,
        y: followY,
        rotation: rotateDeg,
      });
    } else {
      rightPanel.style.transform = `translate(${effectiveDx}px, ${followY}px) rotate(${rotateDeg}deg)`;
    }

    // Dynamic deck underlay image & scale
    const cat = getActiveCatalogue();
    if (deckUnderlay && deckUnderlayImg) {
      if (effectiveDx < 0) {
        const nextPage = Math.min(state.currentSpread + 1, cat.pageCount);
        if (state.currentSpread < cat.pageCount) {
          const url = getPageImgUrl(nextPage);
          // (the attribute: .src is the absolute URL, so comparing it re-set the picture on every move)
          if (url && deckUnderlayImg.getAttribute("src") !== url) deckUnderlayImg.src = url;
          deckUnderlay.style.display = "flex";
        }
      } else if (effectiveDx > 0 && state.currentSpread > 1) {
        const prevPage = state.currentSpread - 1;
        const url = getPageImgUrl(prevPage);
        if (url && deckUnderlayImg.getAttribute("src") !== url) deckUnderlayImg.src = url;
        deckUnderlay.style.display = "flex";
      }

      const progress = Math.min(1, Math.abs(effectiveDx) / 150);
      const underlayScale = 0.95 + progress * 0.05;
      const underlayY = 10 - progress * 10;
      const underlayOpacity = 0.75 + progress * 0.25;

      if (window.gsap) {
        window.gsap.set(deckUnderlay, {
          scale: underlayScale,
          y: underlayY,
          opacity: underlayOpacity,
        });
      }
    }

    // Dynamic Tinder Badges
    if (badgeNext) {
      if (effectiveDx < -14 && state.currentSpread < maxSpreads) {
        const nextOpacity = Math.min(1, (-effectiveDx - 14) / 60);
        badgeNext.style.opacity = String(nextOpacity);
      } else {
        badgeNext.style.opacity = "0";
      }
    }

    if (badgePrev) {
      if (effectiveDx > 14 && state.currentSpread > 1) {
        const prevOpacity = Math.min(1, (effectiveDx - 14) / 60);
        badgePrev.style.opacity = String(prevOpacity);
      } else {
        badgePrev.style.opacity = "0";
      }
    }
  });

  function handlePointerEnd(e) {
    if (!isPointerDown || (e && e.pointerId !== activePointerId)) return;
    const dx = currentX - startX;
    const dy = currentY - startY;
    const threshold = Math.min(window.innerWidth * 0.22, 68);
    const maxSpreads = getMaxSpreads();

    if (!isSwiping) {
      resetCardAndDeck(false);
      return;
    }

    if (dx < -threshold && state.currentSpread < maxSpreads) {
      // SWIPE LEFT -> NEXT PAGE
      state.isTurning = true;
      playPageFlipSound();
      const flyX = -window.innerWidth * 1.35;
      const flyRot = -25;
      if (badgeNext) badgeNext.style.opacity = "1";

      if (animate()) {
        if (deckUnderlay) {
          window.gsap.to(deckUnderlay, { scale: 1, y: 0, opacity: 1, duration: 0.26, ease: "power2.out" });
        }
        window.gsap.to(rightPanel, {
          x: flyX,
          y: dy * 0.4 + 40,
          rotation: flyRot,
          opacity: 0,
          duration: 0.26,
          ease: "power2.in",
          onComplete: () => {
            state.currentSpread += 1;
            renderActiveSpread();
            window.gsap.set(rightPanel, { clearProps: "transform,opacity" });
            resetCardAndDeck(false);
            state.isTurning = false;
          },
        });
      } else {
        state.currentSpread += 1;
        renderActiveSpread();
        resetCardAndDeck(false);
        state.isTurning = false;
      }
    } else if (dx > threshold && state.currentSpread > 1) {
      // SWIPE RIGHT -> PREV PAGE
      state.isTurning = true;
      playPageFlipSound();
      const flyX = window.innerWidth * 1.35;
      const flyRot = 25;
      if (badgePrev) badgePrev.style.opacity = "1";

      if (animate()) {
        if (deckUnderlay) {
          window.gsap.to(deckUnderlay, { scale: 1, y: 0, opacity: 1, duration: 0.26, ease: "power2.out" });
        }
        window.gsap.to(rightPanel, {
          x: flyX,
          y: dy * 0.4 + 40,
          rotation: flyRot,
          opacity: 0,
          duration: 0.26,
          ease: "power2.in",
          onComplete: () => {
            state.currentSpread -= 1;
            renderActiveSpread();
            window.gsap.set(rightPanel, { clearProps: "transform,opacity" });
            resetCardAndDeck(false);
            state.isTurning = false;
          },
        });
      } else {
        state.currentSpread -= 1;
        renderActiveSpread();
        resetCardAndDeck(false);
        state.isTurning = false;
      }
    } else {
      // Below threshold: Elastic Snap Back!
      resetCardAndDeck(true);
    }
  }

  window.addEventListener("pointerup", handlePointerEnd);
  window.addEventListener("pointercancel", handlePointerEnd);
}

// ---------------------------------------------------------------- Initialization
export async function initFlipbook() {
  // 1. Fetch catalogue data
  try {
    const res = await fetch("data/catalogue.json");
    state.data = await res.json();
    state.artByCategory = new Map((state.data.categories || []).map((c) => [c.name, c.art]));
    rebuildProductsByPage();
  } catch (err) {
    console.warn("Could not load catalogue JSON data:", err);
  }
  bindFilmstrip();

  // 2. Responsive detection
  state.singlePageMode = window.matchMedia("(max-width: 860px)").matches;
  window.addEventListener("resize", handleResize);

  // 3. Navigation Controls
  $("#prevBtn")?.addEventListener("click", () => {
    hideQuickCardImmediately();
    flipToPrev();
  });
  $("#nextBtn")?.addEventListener("click", () => {
    hideQuickCardImmediately();
    flipToNext();
  });
  $("#footerPrevBtn")?.addEventListener("click", () => {
    hideQuickCardImmediately();
    flipToPrev();
  });
  $("#footerNextBtn")?.addEventListener("click", () => {
    hideQuickCardImmediately();
    flipToNext();
  });

  // 4. Initialize Mobile Tinder Card Swipe Controller
  initTinderSwipe();

  // Keyboard navigation (Arrow Left / Right, Spacebar, Zoom 'Z', Escape)
  window.addEventListener("keydown", (e) => {
    if (e.target.matches?.("input, textarea, select") || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === " " && e.target !== document.body) return; // Space on a button presses that button
    if (e.key === "ArrowLeft") {
      hideQuickCardImmediately();
      flipToPrev();
    }
    if (e.key === "ArrowRight" || e.key === " ") {
      e.preventDefault();
      hideQuickCardImmediately();
      flipToNext();
    }
    if (e.key.toLowerCase() === "z") {
      toggleZoom();
    }
    if (e.key.toLowerCase() === "m") {
      toggleLens();
    }
    if (LENS.on && (e.key === "+" || e.key === "=")) setLensZoom(LENS.zoom * 1.25);
    if (LENS.on && (e.key === "-" || e.key === "_")) setLensZoom(LENS.zoom / 1.25);
    if (e.key === "Escape") {
      closeDrawer();
      toggleZoom(false);
      toggleLens(false);
      hideQuickCardImmediately();
      $("#jumpPopover")?.style.setProperty("display", "none");
    }
  });

  // Touch Swipe for Dual-Spread Mode (Tablets/Desktops): on the book only, so scrolling the filmstrip
  // or the specs drawer never turns a page.
  let touchStartX = 0;
  const bookWrapEl = $("#bookWrap");
  bookWrapEl?.addEventListener("touchstart", (e) => {
    if (state.singlePageMode) return;
    touchStartX = e.touches[0].clientX;
  }, { passive: true });
  bookWrapEl?.addEventListener("touchend", (e) => {
    if (state.singlePageMode || isZoomed || LENS.on) return;
    const diff = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(diff) > 45) {
      hideQuickCardImmediately();
      diff < 0 ? flipToNext() : flipToPrev();
    }
  }, { passive: true });

  // Page Corner Click to Flip
  $("#leftCorner")?.addEventListener("click", () => {
    hideQuickCardImmediately();
    flipToPrev();
  });
  $("#rightCorner")?.addEventListener("click", () => {
    hideQuickCardImmediately();
    flipToNext();
  });

  // Double Click on Book toggles Magnifier Zoom
  $("#book")?.addEventListener("dblclick", (e) => {
    if (e.target.closest(".fb-page-products") || LENS.on) return;
    toggleZoom();
  });

  // Smooth Pan when in Magnifier Zoom mode
  $(".fb-stage")?.addEventListener("mousemove", panZoomed);

  // Zoom Button Controls
  $("#zoomToggleBtn")?.addEventListener("click", () => toggleZoom());
  $("#zoomResetBtn")?.addEventListener("click", () => toggleZoom(false));

  // Magnifying glass
  initLens();

  // Dismiss quickCard immediately when hovering empty page areas (where numbers are missing)
  const bookEl = $("#book");
  bookEl?.addEventListener("pointermove", (e) => {
    if (!e.target.closest(".fb-page-products") && !e.target.closest("#quickCard")) {
      scheduleHideQuickCard(90);
    }
  });

  // Toolbar Actions
  $("#catalogueSelect")?.addEventListener("change", (e) => switchCatalogue(e.target.value));
  $("#fullscreenBtn")?.addEventListener("click", toggleFullscreen);
  $("#openSpecsBtn")?.addEventListener("click", () => {
    const isOpen = $("#specsDrawer")?.classList.contains("open");
    isOpen ? closeDrawer() : openDrawer();
  });
  $("#drawerClose")?.addEventListener("click", closeDrawer);

  // Direct Page Jump Popover
  const counterBtn = $("#pageCounter");
  const jumpPopover = $("#jumpPopover");
  const jumpInput = $("#jumpPageInput");
  const jumpGo = $("#jumpPageGo");

  counterBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (!jumpPopover) return;
    const isShowing = jumpPopover.style.display !== "none";
    jumpPopover.style.display = isShowing ? "none" : "flex";
    counterBtn.setAttribute("aria-expanded", String(!isShowing));
    if (!isShowing && jumpInput) {
      jumpInput.value = "";
      jumpInput.focus();
    }
  });
  // It is a button for the keyboard too
  counterBtn?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      e.stopPropagation();
      counterBtn.click();
    }
  });

  const performJump = () => {
    const val = parseInt(jumpInput?.value, 10);
    if (!isNaN(val) && val >= 1) {
      jumpToPage(val);
      if (jumpPopover) jumpPopover.style.display = "none";
    }
  };

  jumpGo?.addEventListener("click", performJump);
  jumpInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") performJump();
  });

  document.addEventListener("click", (e) => {
    if (jumpPopover && jumpPopover.style.display !== "none" && !jumpPopover.contains(e.target) && e.target !== counterBtn) {
      jumpPopover.style.display = "none";
      counterBtn?.setAttribute("aria-expanded", "false");
    }
  });

  // Audio Toggles (page sounds: off until turned on, remembered with the catalogue page's choice)
  const showSfx = () => {
    const btn = $("#soundToggle");
    btn?.classList.toggle("active", sfxEnabled);
    btn?.setAttribute("aria-pressed", String(sfxEnabled));
    btn?.setAttribute("title", `Page Sound Effects: ${sfxEnabled ? "On" : "Off"}`);
  };
  showSfx();
  $("#soundToggle")?.addEventListener("click", () => {
    sfxEnabled = !sfxEnabled;
    try { localStorage.setItem("groz.sound", sfxEnabled ? "on" : "off"); } catch { /* storage unavailable */ }
    showSfx();
  });
  $("#ambientToggle")?.addEventListener("click", toggleAmbientAudio);

  // Hover bridge for quickCard, and its buttons
  quickCard?.addEventListener("pointerenter", cancelHideQuickCard);
  quickCard?.addEventListener("pointerleave", () => scheduleHideQuickCard(120));
  quickCard?.addEventListener("click", (e) => {
    if (e.target.closest(".fb-quick-close")) {
      e.stopPropagation();
      hideQuickCardImmediately();
      return;
    }
    const item = e.target.closest("[data-show-product]");
    if (item || e.target.closest("[data-open-drawer]")) {
      hideQuickCardImmediately();
      openDrawer();
      if (item) highlightDrawerProduct(item.dataset.showProduct);
    }
  });

  // Add to quote (drawer): the same quote as the catalogue page, kept in this browser
  document.body.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-add-quote]");
    if (!btn || btn.disabled) return;
    const id = btn.dataset.addQuote;
    const quote = readQuote();
    if (!quote.has(id)) quote.set(id, 1);
    if (!writeQuote(quote)) {
      btn.textContent = "Could not save: this browser blocks storage";
      return;
    }
    playToolClink();
    btn.textContent = "In your quote ✓";
    btn.disabled = true;
    btn.classList.add("added");
    const code = btn.closest("[data-product-id]")?.querySelector(".fb-spec-cat")?.textContent || "Product";
    announce(`${code} added to your quote. It is on the catalogue page's Quote.`);
  });

  // Render initial state with URL parameter deep-linking support
  try {
    const params = new URLSearchParams(window.location.search);
    const requestedPdf = params.get("pdf");
    if (requestedPdf && CATALOGUES[requestedPdf]) {
      state.activeCatalogueKey = requestedPdf;
      if ($("#catalogueSelect")) {
        $("#catalogueSelect").value = requestedPdf;
      }
    }
    const pageParam = parseInt(params.get("page"), 10);
    switchCatalogue(state.activeCatalogueKey);
    if (!isNaN(pageParam) && pageParam >= 1) {
      setTimeout(() => jumpToPage(pageParam), 150);
    }
  } catch {
    switchCatalogue(state.activeCatalogueKey);
  }
}

// Auto-run if on flipbook page (at once when the page has already finished loading)
if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initFlipbook);
  else initFlipbook();
}
