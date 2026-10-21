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
let audioCtx = null;
let sfxEnabled = true;
let ambientEnabled = false;
let ambientOsc = null;
let ambientGain = null;

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
  if (ambientEnabled) {
    const now = ctx.currentTime;
    ambientOsc = ctx.createOscillator();
    ambientGain = ctx.createGain();
    ambientOsc.type = "sine";
    ambientOsc.frequency.setValueAtTime(110, now); // Low harmonic drone

    const lfo = ctx.createOscillator();
    lfo.type = "sine";
    lfo.frequency.setValueAtTime(0.2, now);
    const lfoGain = ctx.createGain();
    lfoGain.gain.setValueAtTime(4, now);
    lfo.connect(lfoGain);
    lfoGain.connect(ambientOsc.frequency);

    ambientGain.gain.setValueAtTime(0.0001, now);
    ambientGain.gain.exponentialRampToValueAtTime(0.045, now + 1.2);

    ambientOsc.connect(ambientGain);
    ambientGain.connect(ctx.destination);
    ambientOsc.start(now);
    lfo.start(now);
  } else if (ambientGain) {
    ambientGain.gain.exponentialRampToValueAtTime(0.00001, ctx.currentTime + 0.6);
    setTimeout(() => {
      ambientOsc?.stop();
      ambientOsc = null;
    }, 700);
  }

  const btn = $("#ambientToggle");
  if (btn) {
    btn.classList.toggle("active", ambientEnabled);
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
  zoomLevel: 1,
  singlePageMode: false,
  productsByPage: new Map(),
  quote: new Set(),
};

// ---------------------------------------------------------------- Page Helpers
function getActiveCatalogue() {
  return CATALOGUES[state.activeCatalogueKey] || CATALOGUES["GROZ_LIGHTING_GL-10_1.pdf"];
}

function getPageImgUrl(pageNum) {
  const cat = getActiveCatalogue();
  if (cat.folder && pageNum >= 1 && pageNum <= cat.pageCount) {
    const pad = String(pageNum).padStart(2, "0");
    return `${cat.folder}/page-${pad}.png`;
  }
  return null;
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

  // Update thumbnail filmstrip selection
  $$(".fb-thumb-item").forEach((thumb, i) => {
    thumb.classList.toggle("active", i + 1 === state.currentSpread);
  });

  // Update Embedded Tool Companion Icon & Text
  const companionIcon = $("#companionIcon");
  const companionText = $("#companionText");
  if (companionIcon) companionIcon.innerHTML = art(cat.art);
  if (companionText) companionText.textContent = cat.companionText;

  // Render Product Specs in Drawer for the active pages
  renderDrawerSpecs([left, right].filter(Boolean));
}

// ---------------------------------------------------------------- Hotspots & Floating Cards
function renderHotspots(container, pageNum) {
  container.innerHTML = "";
  const products = state.productsByPage.get(pageNum) || [];
  if (!products.length) return;

  products.forEach((p, idx) => {
    // Generate well-distributed positions across the page for products
    const col = idx % 2;
    const row = Math.floor(idx / 2);
    const top = 22 + row * 24 + (idx % 3) * 3;
    const left = col === 0 ? 28 + (idx % 2) * 8 : 72 - (idx % 2) * 8;
    const pinNumber = idx + 1;

    const el = document.createElement("div");
    el.className = "fb-hotspot";
    el.style.top = `${Math.min(88, top)}%`;
    el.style.left = `${Math.min(88, left)}%`;
    el.dataset.id = p.id;
    el.dataset.pin = String(pinNumber);
    el.innerHTML = `
      <div class="fb-hotspot-pulse"></div>
      <div class="fb-hotspot-pin">${pinNumber}</div>
    `;

    el.addEventListener("pointerenter", (e) => {
      cancelHideQuickCard();
      showQuickCard(p, e, pinNumber);
    });
    el.addEventListener("pointerleave", () => scheduleHideQuickCard(160));
    el.addEventListener("click", () => {
      openDrawer();
      highlightDrawerProduct(p.id);
    });

    container.appendChild(el);
  });
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

function showQuickCard(p, e, pinNumber = 1) {
  clearTimeout(hideCardTimer);
  if (!quickCard) return;

  // If already displaying this product and the card is visible, don't restart animation
  if (activeCardProductId === p.id && quickCard.classList.contains("active")) {
    return;
  }
  activeCardProductId = p.id;

  const rect = e.currentTarget.getBoundingClientRect();
  const specs = (p.specs || []).slice(0, 3).map((s) => `<b>${esc(s.label)}:</b> ${esc(s.value)}`).join("<br/>");
  const imgSrc = p.image?.src || "";

  quickCard.innerHTML = `
    <div class="fb-quick-header">
      <span class="fb-quick-badge">Pin #${pinNumber} · Page ${p.page || ""}</span>
      <button class="fb-quick-close" id="quickCardCloseBtn" type="button" aria-label="Close card">✕</button>
    </div>
    <div class="fb-quick-body">
      ${imgSrc ? `<div class="fb-quick-thumb"><img src="${esc(imgSrc)}" alt="${esc(p.cat_nr)}" loading="lazy"/></div>` : ""}
      <div class="fb-quick-info">
        <div class="fb-quick-code">${esc(p.cat_nr)}</div>
        <div class="fb-quick-title">${esc(p.heading || p.title || "GROZ Industrial Tool")}</div>
      </div>
    </div>
    <div class="fb-quick-specs">${specs || "Precision engineered for heavy industrial use."}</div>
    <button class="fb-quick-add-btn" type="button" data-add-quote="${esc(p.id)}">Add to Shortlist Quote ✳</button>
  `;

  // Close button on card
  $("#quickCardCloseBtn")?.addEventListener("click", (evt) => {
    evt.stopPropagation();
    hideQuickCardImmediately();
  });

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
      <div style="padding: 30px; text-align: center; color: var(--fb-text-muted);">
        <p>No individual item codes listed on this page spread.</p>
        <small>Browse neighbouring pages or check the catalogue overview.</small>
      </div>`;
    return;
  }

  body.innerHTML = products.map((p) => {
    const specsHtml = (p.specs || []).map((s) => `
      <tr><td class="label">${esc(s.label)}</td><td class="val">${esc(s.value)}</td></tr>
    `).join("");
    const imgSrc = p.image ? p.image.src : "../output_v2/images/placeholder.png";

    return `
      <div class="fb-spec-card" id="spec-${esc(p.id)}" data-product-id="${esc(p.id)}">
        <div class="fb-spec-card-head">
          <img class="fb-spec-thumb" src="${esc(imgSrc)}" alt="${esc(p.cat_nr)}" loading="lazy"/>
          <div class="fb-spec-details">
            <div class="fb-spec-cat">${esc(p.cat_nr)}</div>
            <div class="fb-spec-title">${esc(p.heading || p.title || "Industrial Tool")}</div>
          </div>
        </div>
        <table class="fb-spec-table">
          <tbody>
            <tr><td class="label">ORD NR</td><td class="val">${esc(p.ord_nr || "—")}</td></tr>
            ${p.dimensions_mm ? `<tr><td class="label">Dimensions</td><td class="val">${esc(p.dimensions_mm)} mm</td></tr>` : ""}
            ${p.box_qty ? `<tr><td class="label">Box Quantity</td><td class="val">${esc(p.box_qty)}</td></tr>` : ""}
            ${specsHtml}
          </tbody>
        </table>
        <button class="fb-quick-add-btn" type="button" data-add-quote="${esc(p.id)}">Add to Shortlist Quote</button>
      </div>`;
  }).join("");

  // Scroll-triggered staggered reveal of cards
  const cards = $$(".fb-spec-card", body);
  if (window.gsap) {
    window.gsap.fromTo(cards,
      { opacity: 0, y: 18 },
      { opacity: 1, y: 0, duration: 0.38, stagger: 0.05, ease: "power2.out" }
    );
  } else {
    cards.forEach((c) => c.classList.add("revealed"));
  }
}

export function openDrawer() {
  $("#specsDrawer")?.classList.add("open");
  $("#openSpecsBtn")?.classList.add("active");
}

export function closeDrawer() {
  $("#specsDrawer")?.classList.remove("open");
  $("#openSpecsBtn")?.classList.remove("active");
}

function highlightDrawerProduct(id) {
  const card = document.getElementById(`spec-${id}`);
  if (card) {
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    if (window.gsap) {
      window.gsap.fromTo(card,
        { scale: 0.95, borderColor: "var(--fb-orange)" },
        { scale: 1, borderColor: "var(--fb-line)", duration: 0.6, ease: "elastic.out(1, 0.4)" }
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

    if (window.gsap && rightPanel) {
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

  if (frontImg) frontImg.src = getPageImgUrl(currentRight) || "";
  if (backImg) backImg.src = getPageImgUrl(nextLeft || nextRight) || "";
  // Underneath the lifting page, the next right-hand page is already there (or the end).
  const rightImg = $("#rightPageImg");
  const underRight = getPageImgUrl(nextRight);
  if (rightImg) rightImg.src = underRight || END_PAGE;
  $("#rightHotspots")?.replaceChildren();

  leaf.style.display = "block";

  if (window.gsap) {
    // Multi-phase physical curved turn:
    // 1. Initial corner peel: corner lifts & paper flexes
    // 2. High curved arch: translateZ lifts up into 3D space, casting sweeping shadow
    // 3. Roll-down settle: rolls onto left spread with natural deceleration
    const tl = window.gsap.timeline({
      onComplete: () => {
        // Clear only what the turn set: "all" would also wipe the inline display:none and leave the
        // finished leaf lying over the new right-hand page.
        resetLeaf(leaf);
        state.currentSpread = nextSpread;
        renderActiveSpread();
        state.isTurning = false;
      },
    });
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
  } else {
    state.currentSpread = nextSpread;
    renderActiveSpread();
    leaf.style.display = "none";
    state.isTurning = false;
  }
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

    if (window.gsap && rightPanel) {
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
  const { right: prevRight } = getPagesForSpread(prevSpread);
  const { left: currentLeft } = getPagesForSpread(state.currentSpread);

  if (frontImg) frontImg.src = getPageImgUrl(prevRight) || "";
  if (backImg) backImg.src = getPageImgUrl(currentLeft) || "";
  // Underneath the lifting page, the previous left-hand page is already there (or the cover side).
  const { left: prevLeft } = getPagesForSpread(prevSpread);
  const leftImg = $("#leftPageImg");
  if (leftImg) leftImg.src = getPageImgUrl(prevLeft) || COVER_SIDE;
  $("#leftHotspots")?.replaceChildren();

  leaf.style.display = "block";

  if (window.gsap) {
    const tl = window.gsap.timeline({
      onComplete: () => {
        resetLeaf(leaf);
        state.currentSpread = prevSpread;
        renderActiveSpread();
        state.isTurning = false;
      },
    });
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
  } else {
    state.currentSpread = prevSpread;
    renderActiveSpread();
    leaf.style.display = "none";
    state.isTurning = false;
  }
}

export function jumpToSpread(spreadIdx) {
  if (spreadIdx < 1 || spreadIdx > getMaxSpreads() || spreadIdx === state.currentSpread) return;
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
    const imgUrl = getPageImgUrl(right) || getPageImgUrl(left) || "";
    const label = state.singlePageMode ? `Page ${right}` : (!left ? "Cover" : right > cat.pageCount ? `Page ${left}` : `Pages ${left}–${right}`);
    items.push(`
      <div class="fb-thumb-item${s === state.currentSpread ? " active" : ""}" data-spread="${s}" data-label="${label}">
        <img src="${esc(imgUrl)}" alt="${label}" loading="lazy"/>
      </div>`);
  }

  filmstrip.innerHTML = items.join("");

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

  renderFilmstrip();
  renderActiveSpread();
}

// ---------------------------------------------------------------- Magnifier Zoom & Pan
let isZoomed = false;

export function toggleZoom(force) {
  const next = typeof force === "boolean" ? force : !isZoomed;
  if (next === isZoomed) return;
  isZoomed = next;

  const stage = $(".fb-stage");
  const wrap = $("#bookWrap");
  const badge = $("#zoomBadge");
  const btn = $("#zoomToggleBtn");

  stage?.classList.toggle("zoomed", isZoomed);
  btn?.classList.toggle("active", isZoomed);
  if (badge) badge.style.display = isZoomed ? "flex" : "none";

  hideQuickCardImmediately();

  if (isZoomed) {
    if (window.gsap && wrap) {
      window.gsap.to(wrap, { scale: 2.15, x: 0, y: 0, duration: 0.32, ease: "power2.out" });
    }
  } else {
    if (window.gsap && wrap) {
      window.gsap.to(wrap, { scale: 1, x: 0, y: 0, duration: 0.28, ease: "power2.out" });
    }
  }
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
    // Preserve the current viewed page when switching between dual spread and single page
    const currentPage = state.singlePageMode ? state.currentSpread : (state.currentSpread - 1) * 2 + 1;
    state.singlePageMode = isMobile;
    const newSpread = isMobile ? currentPage : Math.floor(currentPage / 2) + 1;
    state.currentSpread = Math.max(1, Math.min(newSpread, getMaxSpreads()));
    renderFilmstrip();
    renderActiveSpread();
  }
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
    if (!state.singlePageMode || state.isTurning) return;
    if (e.button !== 0 && e.pointerType === "mouse") return;
    if (e.target.closest(".fb-hotspot") || e.target.closest("#quickCard") || e.target.closest("button")) return;

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
          if (url && deckUnderlayImg.src !== url) deckUnderlayImg.src = url;
          deckUnderlay.style.display = "flex";
        }
      } else if (effectiveDx > 0 && state.currentSpread > 1) {
        const prevPage = state.currentSpread - 1;
        const url = getPageImgUrl(prevPage);
        if (url && deckUnderlayImg.src !== url) deckUnderlayImg.src = url;
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

      if (window.gsap) {
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

      if (window.gsap) {
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
    rebuildProductsByPage();
  } catch (err) {
    console.warn("Could not load catalogue JSON data:", err);
  }

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
    if (e.target.matches("input, textarea, select")) return;
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
    if (e.key === "Escape") {
      closeDrawer();
      toggleZoom(false);
      hideQuickCardImmediately();
      $("#jumpPopover")?.style.setProperty("display", "none");
    }
  });

  // Touch Swipe for Dual-Spread Mode (Tablets/Desktops)
  let touchStartX = 0;
  window.addEventListener("touchstart", (e) => {
    if (state.singlePageMode) return;
    touchStartX = e.touches[0].clientX;
  }, { passive: true });
  window.addEventListener("touchend", (e) => {
    if (state.singlePageMode) return;
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
    if (e.target.closest(".fb-hotspot")) return;
    toggleZoom();
  });

  // Smooth Pan when in Magnifier Zoom mode
  const stage = $(".fb-stage");
  stage?.addEventListener("mousemove", (e) => {
    if (!isZoomed) return;
    const wrap = $("#bookWrap");
    if (!wrap) return;
    const rx = (e.clientX / window.innerWidth) - 0.5;
    const ry = (e.clientY / window.innerHeight) - 0.5;
    const panX = -rx * 460;
    const panY = -ry * 340;
    if (window.gsap) {
      window.gsap.to(wrap, { x: panX, y: panY, duration: 0.22, ease: "power1.out", overwrite: "auto" });
    }
  });

  // Zoom Button Controls
  $("#zoomToggleBtn")?.addEventListener("click", () => toggleZoom());
  $("#zoomResetBtn")?.addEventListener("click", () => toggleZoom(false));

  // Dismiss quickCard immediately when hovering empty page areas (where numbers are missing)
  const bookEl = $("#book");
  bookEl?.addEventListener("pointermove", (e) => {
    if (!e.target.closest(".fb-hotspot") && !e.target.closest("#quickCard")) {
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
    if (!isShowing && jumpInput) {
      jumpInput.value = "";
      jumpInput.focus();
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
    if (jumpPopover && !jumpPopover.contains(e.target) && e.target !== counterBtn) {
      jumpPopover.style.display = "none";
    }
  });

  // Audio Toggles
  $("#soundToggle")?.addEventListener("click", () => {
    sfxEnabled = !sfxEnabled;
    $("#soundToggle")?.classList.toggle("active", sfxEnabled);
    $("#soundToggle")?.setAttribute("title", `Page Sound Effects: ${sfxEnabled ? "On" : "Off"}`);
  });
  $("#ambientToggle")?.addEventListener("click", toggleAmbientAudio);

  // Hover bridge for quickCard
  quickCard?.addEventListener("pointerenter", cancelHideQuickCard);
  quickCard?.addEventListener("pointerleave", () => scheduleHideQuickCard(120));

  // Add to Quote from Drawer or Quick Card
  document.body.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-add-quote]");
    if (btn) {
      const id = btn.dataset.addQuote;
      state.quote.add(id);
      playToolClink();
      btn.textContent = "Added to Shortlist ✓";
      btn.style.background = "#1f7a49";
    }
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

// Auto-run if on flipbook page
if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", initFlipbook);
}
