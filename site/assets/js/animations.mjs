// GROZ Unified Immersive Animation System
// Powered by GSAP timelines, ScrollTrigger, Web Audio API synthesis, and custom easings.
// Rules: Entry logo assembly, Hero kinetic typography, Parallax depth, Card tilt & sparks,
// Category elastic accordions & tool-drop sound, Quote spring drawer & progress bar,
// Section scroll-triggered WOW effects, Dynamic gradient scroll bar, and Exit disassembly.

const root = document.documentElement;
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

/** True when animations should run. */
export function animOK() {
  return !reducedMotion.matches && !root.classList.contains("lite");
}

/** Access GSAP and ScrollTrigger instances. */
function getGsap() {
  if (typeof window !== "undefined" && window.gsap) {
    if (window.ScrollTrigger && !getGsap._registered) {
      window.gsap.registerPlugin(window.ScrollTrigger);
      getGsap._registered = true;
    }
    return window.gsap;
  }
  return null;
}

// ---------------------------------------------------------------- Sound Synthesis (Web Audio API)
let audioCtx = null;
// Sound plays only after the visitor turns it on (remembered in this browser, shared with the
// flipbook): browsers block audio before a click anyway, and a catalogue should not surprise anyone.
let soundEnabled = (() => { try { return localStorage.getItem("groz.sound") === "on"; } catch { return false; } })();

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

export function isSoundEnabled() {
  return soundEnabled;
}

export function toggleSound(force) {
  soundEnabled = typeof force === "boolean" ? force : !soundEnabled;
  try { localStorage.setItem("groz.sound", soundEnabled ? "on" : "off"); } catch { /* storage unavailable */ }
  const toggleBtn = document.querySelector("#soundToggle");
  if (toggleBtn) {
    toggleBtn.setAttribute("aria-pressed", String(soundEnabled));
    toggleBtn.setAttribute("title", `Tool Sound Effects: ${soundEnabled ? "On" : "Off"}`);
    const onIcon = toggleBtn.querySelector(".sound-on");
    const offIcon = toggleBtn.querySelector(".sound-off");
    if (onIcon) onIcon.style.display = soundEnabled ? "block" : "none";
    if (offIcon) offIcon.style.display = soundEnabled ? "none" : "block";
  }
  return soundEnabled;
}

/**
 * Synthesizes a crisp, metallic "tool-drop / impact" sound effect via Web Audio API.
 * Zero external MP3 files needed; instantaneous response with metallic harmonics.
 */
export function playToolDropSound(pitchMult = 1) {
  if (!soundEnabled || !animOK()) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;

    // 1. Primary metallic fundamental strike
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(840 * pitchMult, now);
    osc1.frequency.exponentialRampToValueAtTime(260 * pitchMult, now + 0.08);

    gain1.gain.setValueAtTime(0.24, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.12);

    // 2. High metallic ring (anvil overtone)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "triangle";
    osc2.frequency.setValueAtTime(2240 * pitchMult, now);
    osc2.frequency.exponentialRampToValueAtTime(1100 * pitchMult, now + 0.16);

    gain2.gain.setValueAtTime(0.15, now);
    gain2.gain.exponentialRampToValueAtTime(0.0001, now + 0.2);

    // 3. Bandpass filter for authentic tool resonance
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.setValueAtTime(1600 * pitchMult, now);
    filter.Q.setValueAtTime(3.2, now);

    osc1.connect(gain1);
    osc2.connect(gain2);
    gain1.connect(filter);
    gain2.connect(filter);
    filter.connect(ctx.destination);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + 0.14);
    osc2.stop(now + 0.22);
  } catch (e) {
    // AudioContext autoplay restrictions are handled gracefully
  }
}

// ---------------------------------------------------------------- 1. Entry Animation (Page Load)
// The intro overlay is hidden by default (site.css). A small script in the page head adds the class
// "intro" to <html> only when the intro may play: motion allowed, not a low-end device, and not yet
// shown in this browser session. Then the overlay covers the page until startIntro() ends it, and a
// CSS failsafe hides it after a few seconds whatever happens (a script that fails to load, a data
// error), so no visitor is ever left on a black screen.

let introResolve = null;
/** Resolves when the intro is finishing (or at once when there is none): start the hero then. */
export const introDone = new Promise((resolve) => { introResolve = resolve; });

/** Removes the intro overlay and lets the page continue. Safe to call more than once. */
export function endIntro() {
  introResolve?.();
  document.querySelector("#introOverlay")?.remove();
  root.classList.remove("intro");
}

/**
 * Full-screen entry sequence where the GROZ logo assembles like precision tools snapping together.
 * Runs from page load (it does not wait for the catalogue data); Skip or Escape ends it at once.
 */
export function startIntro() {
  const overlay = document.querySelector("#introOverlay");
  const gsap = getGsap();
  if (!overlay || !root.classList.contains("intro") || !animOK() || !gsap) { endIntro(); return; }

  let finished = false;
  const finish = (fast = false) => {
    if (finished) return;
    finished = true;
    introResolve?.(); // the hero starts while the overlay fades away
    removeEventListener("keydown", onKey);
    if (fast) { endIntro(); return; }
    gsap.to(overlay, { opacity: 0, scale: 1.04, duration: 0.5, ease: "power2.inOut", onComplete: endIntro });
  };
  const onKey = (e) => { if (e.key === "Escape") finish(true); };
  overlay.querySelector("#introSkipBtn")?.addEventListener("click", () => finish(true));
  addEventListener("keydown", onKey);
  setTimeout(() => finish(true), 6000); // a stalled timeline never holds the page

  const part = (id) => overlay.querySelector(id);
  const partWrench = part("#partWrench"), partHammer = part("#partHammer"), partCaliper = part("#partCaliper");
  const partBracket = part("#partBracket"), partDiamond = part("#partDiamond"), partInnerDiamond = part("#partInnerDiamond");
  const partLetterG = part("#partLetterG"), partGlowRing = part("#partGlowRing");
  const brandName = part("#introBrandName"), tagline = part("#introTagline");

  // Tool parts start scattered outside the frame (they are already invisible: site.css).
  gsap.set(partWrench, { y: -160, x: -80, rotate: -40, opacity: 0, transformOrigin: "center center" });
  gsap.set(partHammer, { y: -80, x: 180, rotate: 45, opacity: 0, transformOrigin: "center center" });
  gsap.set(partCaliper, { y: 160, x: 80, rotate: -30, opacity: 0, transformOrigin: "center center" });
  gsap.set(partBracket, { y: 80, x: -180, rotate: 35, opacity: 0, transformOrigin: "center center" });
  gsap.set([partDiamond, partInnerDiamond], { scale: 0.2, rotate: 180, opacity: 0, transformOrigin: "center center" });
  gsap.set(partLetterG, { scale: 0, opacity: 0, transformOrigin: "center center" });
  gsap.set([brandName, tagline], { opacity: 0, y: 16 });

  gsap.timeline({ defaults: { ease: "power2.out" }, onComplete: () => finish() })
    // Step 1: Diamond core expands into view
    .to([partDiamond, partInnerDiamond], { scale: 1, rotate: 0, opacity: 1, duration: 0.55, ease: "back.out(1.6)" }, 0.1)
    // Step 2: Tool parts fly in and snap together with elastic precision
    .to(partWrench, { y: 0, x: 0, rotate: 0, opacity: 1, duration: 0.45, ease: "elastic.out(1, 0.6)" }, 0.25)
    .to(partHammer, { y: 0, x: 0, rotate: 0, opacity: 1, duration: 0.45, ease: "elastic.out(1, 0.6)" }, 0.3)
    .to(partCaliper, { y: 0, x: 0, rotate: 0, opacity: 1, duration: 0.45, ease: "elastic.out(1, 0.6)" }, 0.35)
    .to(partBracket, { y: 0, x: 0, rotate: 0, opacity: 1, duration: 0.45, ease: "elastic.out(1, 0.6)" }, 0.4)
    // Step 3: Mechanical strike sound & core G reveal
    .call(() => playToolDropSound(1.1), null, 0.45)
    .to(partLetterG, { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(2)" }, 0.45)
    .to(partGlowRing, { scale: 3.2, opacity: 0.9, duration: 0.3, ease: "power2.out" }, 0.48)
    .to(partGlowRing, { opacity: 0, duration: 0.2 }, 0.7)
    // Step 4: Kinetic brand typography reveals
    .to(brandName, { opacity: 1, y: 0, letterSpacing: "0.22em", duration: 0.4, ease: "power2.out" }, 0.65)
    .to(tagline, { opacity: 0.85, y: 0, letterSpacing: "0.28em", duration: 0.35, ease: "power2.out" }, 0.75)
    // Hold momentarily for cinematic impact
    .to({}, { duration: 0.4 });
}

/**
 * Slide in subtle tool silhouettes from the sides and animate hero parallax depth.
 */
export function initHeroParallax() {
  const gsap = getGsap();
  if (!animOK() || !gsap || !window.ScrollTrigger) return;
  const hero = document.querySelector(".hero");
  if (!hero || hero.dataset.parallaxReady) return;
  hero.dataset.parallaxReady = "true";

  const visual = hero.querySelector(".hero-visual");
  const copy = hero.querySelector(".hero-copy");
  const leftSilhouette = hero.querySelector(".hero-silhouette.left");
  const rightSilhouette = hero.querySelector(".hero-silhouette.right");

  // Side silhouettes slide in once the intro (if any) is over; until then they wait out of sight.
  if (leftSilhouette) gsap.set(leftSilhouette, { x: -70, opacity: 0 });
  if (rightSilhouette) gsap.set(rightSilhouette, { x: 70, opacity: 0 });
  introDone.then(() => {
    if (leftSilhouette) gsap.to(leftSilhouette, { x: 0, opacity: 0.38, duration: 0.8, ease: "power2.out", delay: 0.2 });
    if (rightSilhouette) gsap.to(rightSilhouette, { x: 0, opacity: 0.38, duration: 0.8, ease: "power2.out", delay: 0.3 });
  });

  if (leftSilhouette) {
    gsap.to(leftSilhouette, {
      y: 90,
      ease: "none",
      scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: 0.5 },
    });
  }

  if (rightSilhouette) {
    gsap.to(rightSilhouette, {
      y: 110,
      ease: "none",
      scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: 0.5 },
    });
  }

  if (visual) {
    gsap.to(visual, {
      y: 65,
      ease: "none",
      scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: 0.5 },
    });
  }
  // (No scroll tween on .orbit: its own CSS animation sets its transform, so the tween never showed.)
  if (copy) {
    gsap.to(copy, {
      y: 35,
      ease: "none",
      scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: 0.5 },
    });
  }
}

/**
 * Scroll cue with gentle, natural bouncing arrow animation at the bottom of the hero.
 */
export function initScrollCue() {
  const cue = document.querySelector("#heroScrollCue");
  const gsap = getGsap();
  if (!cue || !gsap || !animOK()) return;

  // Fades in after the intro. Opacity only: its position and hover lift are CSS transforms. The arrow's
  // bob is a CSS animation (site.css), which pauses with the hero when it is off screen; an endless
  // GSAP tween would keep running on every frame.
  gsap.set(cue, { opacity: 0 });
  introDone.then(() => gsap.to(cue, { opacity: 1, duration: 0.6, delay: 0.8, ease: "power2.out", clearProps: "opacity" }));

  cue.addEventListener("click", (e) => {
    e.preventDefault();
    const target = document.querySelector("#categories");
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

// ---------------------------------------------------------------- 3. Product Cards Animations

/**
 * On load / render: cards cascade in with staggered slide-up motion and scale overshoot.
 */
export function animateCardsOnLoad(cards, { stagger = 0.038, duration = 0.46 } = {}) {
  const gsap = getGsap();
  if (!animOK() || !cards || !cards.length) return;
  const list = Array.isArray(cards) ? cards : [...cards];
  const onScreen = (r) => r.top < window.innerHeight + 80 && r.bottom > -80;
  const targets = list.filter((c) => onScreen(c.getBoundingClientRect()));
  const batch = targets.length ? targets : list.slice(0, 16);

  if (gsap) {
    gsap.fromTo(batch,
      { opacity: 0, y: 32, scale: 0.95 },
      {
        opacity: 1,
        y: 0,
        scale: 1,
        duration,
        stagger,
        ease: "back.out(1.2)",
        clearProps: "transform,opacity,scale",
      }
    );
  } else {
    batch.forEach((c, i) => {
      c.animate(
        [{ opacity: 0, transform: "translateY(32px) scale(0.95)" }, { opacity: 1, transform: "none" }],
        { duration: duration * 1000, delay: i * stagger * 1000, easing: "cubic-bezier(0.25, 0.46, 0.45, 0.94)", fill: "backwards" }
      );
    });
  }
}

/**
 * On load / render / filter in table mode: rows cascade in with staggered slide-up motion and fade in.
 */
export function animateTableRowsOnLoad(rows, { stagger = 0.03, duration = 0.38 } = {}) {
  if (!animOK() || !rows || !rows.length) return;
  const list = Array.isArray(rows) ? rows : [...rows];
  const onScreen = (r) => r.top < window.innerHeight + 80 && r.bottom > -80;
  const targets = list.filter((c) => onScreen(c.getBoundingClientRect()));
  const batch = targets.length ? targets : list.slice(0, 24);
  // Web Animations rather than GSAP: on phones the rows have a CSS transform transition, which re-timed
  // every GSAP frame and made the rows lag behind.
  batch.forEach((c, i) => {
    c.animate(
      [{ opacity: 0, transform: "translateY(18px)" }, { opacity: 1, transform: "none" }],
      { duration: duration * 1000, delay: i * stagger * 1000, easing: "cubic-bezier(0.25, 0.46, 0.45, 0.94)", fill: "backwards" }
    );
  });
}

/**
 * Micro-particle spark effects that burst and drift upward when a product card or table row is hovered.
 */
export function spawnCardSparks(cardEl) {
  if (!animOK()) return;
  const rect = cardEl.getBoundingClientRect();
  const host = document.createElement("div");
  host.className = "fx-card-sparks-host";
  host.style.cssText = `position:fixed; left:${rect.left + Math.min(rect.width / 2, 80)}px; top:${rect.top + 20}px; pointer-events:none; z-index:9999;`;
  document.body.appendChild(host);

  const colors = ["#f4511e", "#ff8051", "#ffd36b", "#ffb48a"];
  const count = 5;

  for (let i = 0; i < count; i++) {
    const spark = document.createElement("span");
    const color = colors[i % colors.length];
    const size = 3 + Math.random() * 2.5;
    spark.style.cssText = `position:absolute; width:${size}px; height:${size}px; border-radius:50%; background:${color}; box-shadow:0 0 6px ${color}; opacity:1;`;
    host.appendChild(spark);

    const angle = (Math.random() * 120 - 150) * (Math.PI / 180);
    const dist = 24 + Math.random() * 32;
    const dx = Math.cos(angle) * dist;
    const dy = Math.sin(angle) * dist;

    const gsap = getGsap();
    if (gsap) {
      gsap.to(spark, {
        x: dx,
        y: dy - 15,
        scale: 0.2,
        opacity: 0,
        duration: 0.45 + Math.random() * 0.2,
        ease: "power2.out",
        onComplete: () => {
          spark.remove();
          if (!host.children.length) host.remove();
        },
      });
    } else {
      spark.animate(
        [{ transform: "translate(0, 0) scale(1)", opacity: 1 }, { transform: `translate(${dx}px, ${dy - 15}px) scale(0.2)`, opacity: 0 }],
        { duration: 450, easing: "ease-out" }
      ).onfinish = () => {
        spark.remove();
        if (!host.children.length) host.remove();
      };
    }
  }
}

/**
 * Initializes card & table row hover listener to emit micro spark particles.
 */
export function initCardSparkListeners(container = document) {
  // pointerenter fires for every element the pointer enters; only entering the card or row itself
  // counts (moving over its picture, title or buttons used to burst sparks again each time).
  container.addEventListener("pointerenter", (e) => {
    if (e.pointerType === "mouse" && e.target.matches?.(".product, .ptable tbody tr")) spawnCardSparks(e.target);
  }, true);
}

// ---------------------------------------------------------------- 4. Category Navigation

/**
 * Smooth accordion expand/collapse with elastic easing.
 */
export function animateCategoryAccordion(element, open, { duration = 0.3, onComplete } = {}) {
  const gsap = getGsap();
  if (!element) return;
  // A new open or close replaces one still playing (its onComplete never runs).
  gsap?.killTweensOf(element);
  const done = () => {
    gsap?.set(element, { clearProps: "opacity,transform,transformOrigin" });
    onComplete?.();
  };
  if (!animOK() || !gsap) {
    element.hidden = !open;
    done();
    return;
  }
  // Transform and opacity only: animating the height re-laid out the page on every frame.
  if (open) {
    element.hidden = false;
    playToolDropSound(1.2);
    gsap.fromTo(element,
      { opacity: 0, y: -8, scaleY: 0.94, transformOrigin: "top center" },
      { opacity: 1, y: 0, scaleY: 1, duration, ease: "back.out(1.6)", onComplete: done }
    );
  } else {
    gsap.to(element, {
      opacity: 0, y: -6, scaleY: 0.96, transformOrigin: "top center", duration: 0.18, ease: "power2.in",
      onComplete: () => { element.hidden = true; done(); },
    });
  }
}

/**
 * Fade in product lists sequentially with upward motion and tool-drop sound when a category opens.
 */
export function fadeProductsSequentially(cards, { duration = 0.42, stagger = 0.038 } = {}) {
  const gsap = getGsap();
  playToolDropSound(0.95);
  if (!animOK() || !cards || !cards.length) return;
  const list = Array.isArray(cards) ? cards : [...cards];
  const targets = list.slice(0, 24);

  if (gsap) {
    const tl = gsap.timeline({ defaults: { ease: "power2.out" } });
    tl.fromTo(targets,
      { opacity: 0, y: 26, scale: 0.96 },
      {
        opacity: 1,
        y: 0,
        scale: 1,
        duration,
        stagger,
        ease: "back.out(1.2)",
        clearProps: "transform,opacity,scale",
      }
    );
    return tl;
  } else {
    targets.forEach((c, i) => {
      c.animate(
        [{ opacity: 0, transform: "translateY(26px)" }, { opacity: 1, transform: "none" }],
        { duration: duration * 1000, delay: i * stagger * 1000, easing: "cubic-bezier(0.25, 0.46, 0.45, 0.94)", fill: "backwards" }
      );
    });
  }
}

// ---------------------------------------------------------------- 5. Quote Builder Animations

/**
 * Animate the cart icon with spring bounce/pulse when items are added.
 */
export function animateCartBounce(elements) {
  playToolDropSound(1.3);
  if (!animOK() || !elements) return;
  const targets = (Array.isArray(elements) ? elements : [elements]).filter(Boolean);
  if (!targets.length) return;
  // Web Animations rather than GSAP: the buttons have CSS transform transitions, which re-timed every
  // GSAP frame (the bounce lagged).
  targets.forEach((el) => {
    el.animate(
      [
        { transform: "scale(1) rotate(0deg)" },
        { transform: "scale(1.34) rotate(-7deg)", offset: 0.3 },
        { transform: "scale(0.9) rotate(4deg)", offset: 0.6 },
        { transform: "scale(1.12) rotate(-2deg)", offset: 0.8 },
        { transform: "scale(1) rotate(0deg)" },
      ],
      { duration: 480, easing: "cubic-bezier(0.25, 0.46, 0.45, 0.94)" }
    );
  });
}

/**
 * Slide in the quote summary drawer from the right with spring physics.
 */
const drawerFrom = () => (matchMedia("(max-width: 720px)").matches ? { y: "100%" } : { x: "100%" });

export function openQuoteDrawer(modalEl, backdropEl) {
  const gsap = getGsap();
  if (!modalEl) return;
  if (!animOK() || !gsap) return;
  const parts = [modalEl, backdropEl].filter(Boolean);
  gsap.killTweensOf(parts);
  // From the side (from below on phones, where it is a bottom sheet). No overshoot: it is flush with
  // the screen edge, and bouncing past it opened a gap. Nothing is left inline afterwards.
  gsap.fromTo(modalEl,
    { ...drawerFrom(), opacity: 0.6 },
    { x: 0, y: 0, opacity: 1, duration: 0.42, ease: "power3.out", clearProps: "transform,opacity" }
  );
  if (backdropEl) {
    gsap.fromTo(backdropEl,
      { opacity: 0 },
      { opacity: 1, duration: 0.3, ease: "power2.out", clearProps: "opacity" }
    );
  }
}

/**
 * Slide out the quote summary drawer to the right with easing.
 */
export function closeQuoteDrawer(modalEl, backdropEl, onComplete) {
  const gsap = getGsap();
  if (!modalEl || !animOK() || !gsap) {
    onComplete?.();
    return;
  }

  gsap.killTweensOf([modalEl, backdropEl].filter(Boolean));
  const tl = gsap.timeline({
    onComplete: () => {
      onComplete?.(); // hidden first, then the inline styles go (no flash of the drawer back in place)
      gsap.set([modalEl, backdropEl].filter(Boolean), { clearProps: "transform,opacity" });
    },
  });
  tl.to(modalEl, { ...drawerFrom(), opacity: 0.6, duration: 0.3, ease: "power2.in" }, 0);
  if (backdropEl) {
    tl.to(backdropEl, { opacity: 0, duration: 0.32, ease: "power2.in" }, 0);
  }
  return tl;
}

/**
 * Dynamically updates the animated quote readiness progress bar based on entered details.
 */
export function updateQuoteProgress(quoteSize = 0, contact = {}) {
  const wrap = document.querySelector("#quoteProgressWrap");
  const fill = document.querySelector("#quoteProgressFill");
  const score = document.querySelector("#quoteProgressScore");
  const hint = document.querySelector("#quoteProgressHint");
  if (!wrap || !fill || !score) return;

  let percent = 0;
  if (quoteSize > 0) percent += 35;
  if (contact.name && contact.name.trim().length > 1) percent += 25;
  if (contact.email && contact.email.includes("@")) percent += 25;
  if (contact.phone || contact.location) percent += 15;
  percent = Math.min(100, Math.max(15, percent));

  score.textContent = `${percent}%`;
  if (hint) {
    if (percent < 50) hint.textContent = "Add your contact details to prepare request";
    else if (percent < 90) hint.textContent = "Almost ready — add location or phone number";
    else hint.textContent = "Ready to generate clear quotation!";
  }

  fill.style.width = `${percent}%`; // its CSS transition animates the change
}

// ---------------------------------------------------------------- 6. Scroll-Triggered WOW Effects

/**
 * Unique motion effects per major category and section:
 * - Hand Tools: hammer icon strikes with impact sparks
 * - Lighting: luminous glow blooms around products
 * - Sections fade in with upward motion
 */
export function initSectionScrollTriggers() {
  const gsap = getGsap();
  if (!animOK() || !gsap || !window.ScrollTrigger) return;

  // Sections themselves are brought in by the existing .reveal observer (app.mjs). Animating them here
  // too doubled the motion and left an inline transform on #products, which turned the fixed filter
  // sheet on phones into one positioned inside the section.

  // Hand Tools Sledge Strike trigger
  const categoriesSec = document.querySelector("#categories");
  if (categoriesSec && !categoriesSec.dataset.strikeBound) {
    categoriesSec.dataset.strikeBound = "true";
    window.ScrollTrigger.create({
      trigger: categoriesSec,
      start: "top 78%",
      once: true,
      onEnter: () => {
        const sledgeTile = document.querySelector('.cat[data-group="Hand Tools"]');
        if (sledgeTile) {
          gsap.fromTo(sledgeTile,
            { scale: 0.94 },
            {
              scale: 1,
              duration: 0.45,
              ease: "elastic.out(1, 0.5)",
              clearProps: "transform",
              onStart: () => playToolDropSound(0.9),
            }
          );
        }
      },
    });
  }

  // Lighting Section Glow effect trigger
  const productsSec = document.querySelector("#products");
  if (productsSec && !productsSec.dataset.lightingGlowBound) {
    productsSec.dataset.lightingGlowBound = "true";
    window.ScrollTrigger.create({
      trigger: productsSec,
      start: "top 70%",
      once: true,
      onEnter: () => {
        const lightTile = document.querySelector('.cat[data-group="Lighting"]');
        if (lightTile) {
          lightTile.classList.add("bloom-glow");
          setTimeout(() => lightTile.classList.remove("bloom-glow"), 1200);
        }
      },
    });
  }
}

/**
 * Top scroll progress bar with energetic dynamic gradient that animates as the user scrolls.
 */
export function initScrollProgressBar() {
  let bar = document.querySelector("#scrollProgress");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "scrollProgress";
    bar.className = "scroll-progress-bar";
    bar.setAttribute("aria-hidden", "true");
    document.body.prepend(bar);
  }

  // Where the browser supports scroll-driven animations, site.css moves the bar off the main thread.
  if (window.CSS?.supports?.("animation-timeline: scroll()")) return;
  const gsap = getGsap();
  if (animOK() && gsap && window.ScrollTrigger) {
    // Transform only: animating the gradient's position repainted the bar on every frame.
    gsap.to(bar, {
      scaleX: 1,
      ease: "none",
      scrollTrigger: {
        start: "top top",
        end: "bottom bottom",
        scrub: 0.12,
      },
    });
  } else {
    const update = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const progress = max > 0 ? window.scrollY / max : 0;
      bar.style.transform = `scaleX(${Math.min(1, Math.max(0, progress))})`;
    };
    window.addEventListener("scroll", update, { passive: true });
    update();
  }
}

// ---------------------------------------------------------------- 7. Closing Animation (Exit Sequence)

/**
 * Triggers the closing animation:
 * - GROZ logo disassembles into tool parts in reverse
 * - Fade-to-black cinematic transition with "Made for the work ahead" tagline
 * - "Return to Catalogue" button smoothly restores the view
 */
export function triggerExitSequence() {
  const overlay = document.querySelector("#exitOverlay");
  if (!overlay) return;
  overlay.hidden = false;
  overlay.style.display = "flex";

  const logoWrap = overlay.querySelector("#exitLogoWrap");
  if (logoWrap && !logoWrap.children.length) {
    logoWrap.innerHTML = `
      <svg class="exit-logo-svg" viewBox="0 0 300 300">
        <defs>
          <linearGradient id="exitOrange" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#ff7b47"/>
            <stop offset="50%" stop-color="#f4511e"/>
            <stop offset="100%" stop-color="#bf360c"/>
          </linearGradient>
          <linearGradient id="exitSteel" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#ffffff"/>
            <stop offset="50%" stop-color="#c4c9d1"/>
            <stop offset="100%" stop-color="#69717d"/>
          </linearGradient>
        </defs>
        <path id="exitPart1" class="exit-part" d="M150 20 L210 80 L185 105 L150 70 L115 105 L90 80 Z" fill="url(#exitSteel)" stroke="#515863" stroke-width="3"/>
        <path id="exitPart2" class="exit-part" d="M280 150 L220 210 L195 185 L230 150 L195 115 L220 90 Z" fill="url(#exitSteel)" stroke="#515863" stroke-width="3"/>
        <path id="exitPart3" class="exit-part" d="M150 280 L90 220 L115 195 L150 230 L185 195 L210 220 Z" fill="url(#exitSteel)" stroke="#515863" stroke-width="3"/>
        <path id="exitPart4" class="exit-part" d="M20 150 L80 90 L105 115 L70 150 L105 185 L80 210 Z" fill="url(#exitSteel)" stroke="#515863" stroke-width="3"/>
        <polygon id="exitDiamond" class="exit-part" points="150,45 255,150 150,255 45,150" fill="url(#exitOrange)" stroke="#8e2508" stroke-width="4"/>
        <text id="exitLetterG" class="exit-part" x="150" y="196" font-family="Arial, sans-serif" font-weight="900" font-size="125" text-anchor="middle" fill="#ffffff">G</text>
      </svg>`;
  }

  const gsap = getGsap();
  if (!gsap || !animOK()) {
    overlay.querySelector("#exitReturnBtn")?.addEventListener("click", () => {
      overlay.hidden = true;
      overlay.style.display = "none";
    });
    return;
  }

  const title = overlay.querySelector(".exit-title");
  const sub = overlay.querySelector(".exit-sub");
  const returnBtn = overlay.querySelector("#exitReturnBtn");

  const p1 = overlay.querySelector("#exitPart1");
  const p2 = overlay.querySelector("#exitPart2");
  const p3 = overlay.querySelector("#exitPart3");
  const p4 = overlay.querySelector("#exitPart4");
  const diamond = overlay.querySelector("#exitDiamond");
  const gLetter = overlay.querySelector("#exitLetterG");

  gsap.set(overlay, { opacity: 0 });
  gsap.set([p1, p2, p3, p4, diamond, gLetter], { x: 0, y: 0, rotate: 0, opacity: 1, scale: 1, transformOrigin: "center center" });
  gsap.set([title, sub, returnBtn], { opacity: 0, y: 18 });

  const exitTl = gsap.timeline({ defaults: { ease: "power2.out" } });

  exitTl
    .to(overlay, { opacity: 1, duration: 0.45 })
    // Disassemble tool parts outward
    .to(p1, { y: -160, x: -80, rotate: -45, opacity: 0, duration: 0.6, ease: "power2.in" }, 0.2)
    .to(p2, { y: -80, x: 180, rotate: 50, opacity: 0, duration: 0.6, ease: "power2.in" }, 0.25)
    .to(p3, { y: 160, x: 80, rotate: -35, opacity: 0, duration: 0.6, ease: "power2.in" }, 0.3)
    .to(p4, { y: 80, x: -180, rotate: 40, opacity: 0, duration: 0.6, ease: "power2.in" }, 0.35)
    .to(gLetter, { scale: 0.3, opacity: 0, duration: 0.4 }, 0.2)
    .to(diamond, { scale: 0.4, rotate: 90, opacity: 0, duration: 0.5 }, 0.3)
    // Reveal closing tagline
    .to(title, { opacity: 1, y: 0, duration: 0.5 }, 0.55)
    .to(sub, { opacity: 0.9, y: 0, duration: 0.5 }, 0.65)
    .to(returnBtn, { opacity: 1, y: 0, duration: 0.4 }, 0.8);

  const onReturn = () => {
    gsap.to(overlay, {
      opacity: 0,
      duration: 0.4,
      onComplete: () => {
        overlay.hidden = true;
        overlay.style.display = "none";
      },
    });
  };
  returnBtn?.replaceWith(returnBtn.cloneNode(true));
  overlay.querySelector("#exitReturnBtn")?.addEventListener("click", onReturn);
}

// ---------------------------------------------------------------- SVG Stroke Animations

/**
 * Tool icons and SVG paths “draw themselves” on load using stroke animation.
 */
export function animateSvgDraw(svg, { duration = 0.55, delay = 0, stagger = 0.04 } = {}) {
  const gsap = getGsap();
  if (!svg || !animOK()) return;
  const elements = svg.querySelectorAll("path, line, polyline, polygon, circle, rect");
  const stroked = [...elements].filter((el) => {
    const s = el.getAttribute("stroke") || getComputedStyle(el).stroke;
    return s && s !== "none" && s !== "transparent" && s !== "rgba(0, 0, 0, 0)";
  });
  if (!stroked.length) return;

  if (gsap) {
    const tl = gsap.timeline({ delay, defaults: { ease: "power2.out" } });
    stroked.forEach((el, i) => {
      let len = 100;
      try {
        len = el.getTotalLength ? el.getTotalLength() : 100;
      } catch {
        len = 100;
      }
      if (len <= 0) len = 100;
      gsap.set(el, { strokeDasharray: len, strokeDashoffset: len });
      tl.to(el, { strokeDashoffset: 0, duration, ease: "power2.out", clearProps: "strokeDasharray,strokeDashoffset" }, i * stagger);
    });
    return tl;
  }
}

/**
 * Category icons animate their outlines when revealed into view.
 */
let outlinesBound = false;
export function animateCategoryOutlines() {
  const gsap = getGsap();
  // Once per visit: the tiles are rebuilt on every category click, and each rebuild used to add another
  // trigger that redrew all the icons straight away.
  if (!animOK() || outlinesBound) return;
  outlinesBound = true;

  // The tiles on the page when the grid scrolls into view (not the ones that existed when this ran).
  const runDraw = () => {
    document.querySelectorAll("#categoryGrid .cat").forEach((cat, idx) => {
      const svg = cat.querySelector(".cat-art svg");
      if (svg) animateSvgDraw(svg, { duration: 0.52, delay: idx * 0.045, stagger: 0.035 });
    });
  };

  if (gsap && window.ScrollTrigger) {
    window.ScrollTrigger.create({
      trigger: "#categoryGrid",
      start: "top 86%",
      once: true,
      onEnter: runDraw,
    });
  } else {
    runDraw();
  }
}

// ---------------------------------------------------------------- Master Bootstrapper

/**
 * Initialize the full unified animation system across the site.
 */
export function initUnifiedAnimationSystem() {
  if (!animOK()) return;
  initScrollProgressBar();
  initHeroParallax();
  initScrollCue();
  initSectionScrollTriggers();
  initCardSparkListeners();

  // Tool icons draw themselves once the intro (if any) is over, not unseen underneath it.
  introDone.then(() => {
    const heroTool = document.querySelector(".hero-tool");
    if (heroTool) animateSvgDraw(heroTool, { duration: 0.6, delay: 0.2, stagger: 0.06 });
    document.querySelectorAll(".trust-icon svg").forEach((svg, i) => {
      animateSvgDraw(svg, { duration: 0.48, delay: 0.25 + i * 0.08, stagger: 0.04 });
    });
  });

  animateCategoryOutlines();

  // Ensure exit overlay is strictly hidden on startup
  const exitOverlay = document.querySelector("#exitOverlay");
  if (exitOverlay) {
    exitOverlay.hidden = true;
    exitOverlay.style.display = "none";
    document.querySelector("#exitReturnBtn")?.addEventListener("click", () => {
      exitOverlay.hidden = true;
      exitOverlay.style.display = "none";
    });
  }

  // Bind exit buttons
  document.querySelectorAll("#exitBtn, #footerExitBtn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      triggerExitSequence();
    });
  });

}

/** The header's sound button: shows the remembered choice and switches it. Works with or without
 *  motion (it is a setting, not an animation). */
export function initSound() {
  const soundBtn = document.querySelector("#soundToggle");
  if (!soundBtn) return;
  toggleSound(soundEnabled); // show the remembered state
  soundBtn.addEventListener("click", () => toggleSound());
}
