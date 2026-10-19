// GROZ catalogue website: decorative motion. Every effect is optional: it runs only when motion is
// welcome (no reduced-motion request, not a low-end device) and the browser has the Web Animations
// features it uses, and nothing on the page waits for it. Only transform and opacity move, on the
// element itself or on a short-lived copy in a fixed layer, so layout never changes; each copy is
// removed when its animation ends, or by a timer if the page stops drawing frames (a hidden tab).

const root = document.documentElement;
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
// Separate translate/scale properties let an effect move an element without replacing its own transform.
const split = typeof CSS !== "undefined" && !!CSS.supports?.("translate", "1px 1px") && !!CSS.supports?.("scale", "1");
export const EASE = "cubic-bezier(.2,.8,.2,1)";

/** True when decorative motion should run. */
export function motionOK() {
  return !reduced.matches && !root.classList.contains("lite") && typeof Element.prototype.animate === "function";
}

let layer = null;
function fxLayer() {
  if (!layer?.isConnected) {
    layer = document.createElement("div");
    layer.className = "fx-layer";
    layer.setAttribute("aria-hidden", "true");
    document.body.appendChild(layer);
  }
  return layer;
}

/** Removes `el` once all `anims` have ended (or after `ms` at the latest), then calls `then` once. */
function settle(el, anims, ms, then) {
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    el?.remove();
    then?.();
  };
  const timer = setTimeout(finish, ms);
  Promise.all(anims.map((a) => a.finished)).then(finish, finish);
}

const onScreen = (r) => r.width > 0 && r.bottom > 0 && r.top < innerHeight;

/** A quick squash-and-grow, used when something lands on a button or a count changes. */
export function pop(el, k = 1.16) {
  if (!el || !split || !motionOK()) return;
  el.animate({ scale: [1, k, 0.97, 1] }, { duration: 440, easing: "ease-out" });
}

/** A number that changed slides in from below (up) or above (down). */
export function roll(el, up = true) {
  if (!el || !split || !motionOK()) return;
  el.animate({ translate: [`0 ${up ? 70 : -70}%`, "0 0"], opacity: [0, 1] }, { duration: 320, easing: EASE });
}

/** Tosses a copy of `src` (a product picture) in an arc into `target` (the Quote button), pops the
 *  target, then calls `onLand`. Without motion, or with nothing to fly, `onLand` runs at once. */
export function flyTo(src, target, onLand) {
  const a = src?.getBoundingClientRect(), b = target?.getBoundingClientRect();
  if (!split || !motionOK() || !a || !b || !onScreen(a) || !b.width) { onLand?.(); return; }
  const card = document.createElement("div");
  card.className = "fx-fly";
  card.style.cssText = `left:${a.left}px;top:${a.top}px;width:${a.width}px;height:${a.height}px`;
  if (src.tagName === "IMG") {
    const img = new Image();
    img.alt = "";
    img.src = src.currentSrc || src.src;
    card.appendChild(img);
  } else card.appendChild(src.cloneNode(true));
  fxLayer().appendChild(card);
  const dx = b.left + b.width / 2 - (a.left + a.width / 2), dy = b.top + b.height / 2 - (a.top + a.height / 2);
  const end = Math.max(0.08, Math.min(0.5, 30 / Math.max(a.width, a.height)));
  const ms = 760;
  // Across and up follow different curves, so the picture is tossed in an arc rather than slid.
  const anims = [
    card.animate({ translate: ["0px 0px", `${dx}px 0px`] }, { duration: ms, easing: "cubic-bezier(.5,0,.75,.9)", fill: "forwards" }),
    card.animate([
      { transform: "translateY(0px) scale(1) rotate(0deg)", opacity: 1 },
      { transform: `translateY(${-Math.max(28, Math.abs(dy) * 0.12)}px) scale(1.08) rotate(-5deg)`, opacity: 1, offset: 0.24 },
      { transform: `translateY(${dy}px) scale(${end}) rotate(-14deg)`, opacity: 0.85 },
    ], { duration: ms, easing: "cubic-bezier(.3,.4,.5,1)", fill: "forwards" }),
  ];
  settle(card, anims, ms + 500, () => { onLand?.(); pop(target); });
}

/** Saving: the heart squashes and springs back, a ring and sparks burst out. Unsaving: a small shrink. */
export function burst(el, on) {
  if (!el || !split || !motionOK()) return;
  el.animate({ scale: on ? [1, 0.7, 1.3, 0.94, 1] : [1, 0.8, 1] }, { duration: on ? 560 : 260, easing: "ease-out" });
  const r = el.getBoundingClientRect();
  if (!on || !onScreen(r)) return;
  const host = document.createElement("div");
  host.className = "fx-burst";
  host.style.cssText = `left:${r.left + r.width / 2}px;top:${r.top + r.height / 2}px`;
  host.innerHTML = `<i></i>${"<b></b>".repeat(8)}`;
  fxLayer().appendChild(host);
  const anims = [host.firstElementChild.animate({ scale: [0.35, 1.9], opacity: [0.75, 0] }, { duration: 520, easing: EASE, fill: "forwards" })];
  host.querySelectorAll("b").forEach((dot, i) => {
    const angle = (i / 8) * Math.PI * 2 + 0.25, dist = 22 + (i % 2) * 9;
    anims.push(dot.animate({
      translate: ["0px 0px", `${(Math.cos(angle) * dist).toFixed(1)}px ${(Math.sin(angle) * dist).toFixed(1)}px`],
      scale: [1, 0.2], opacity: [1, 0],
    }, { duration: 560, delay: 70, easing: "cubic-bezier(.15,.8,.3,1)", fill: "both" }));
  });
  settle(host, anims, 1300);
}

/** "Added": the button springs and its check mark draws itself. */
export function drawCheck(btn) {
  if (!btn || !split || !motionOK()) return;
  btn.animate({ scale: [0.92, 1.05, 1] }, { duration: 420, easing: "ease-out" });
  const path = btn.querySelector("svg path");
  if (!path) return;
  path.setAttribute("pathLength", "1");
  path.animate({ strokeDasharray: ["1 1", "1 1"], strokeDashoffset: [1, 0] }, { duration: 380, delay: 90, easing: "ease-out", fill: "backwards" });
}

// ---------------------------------------------------------------- cards coming in
let revealer = null;
function reveal(el, delay) {
  el.classList.remove("fx-wait");
  if (!motionOK()) return;
  el.animate([{ opacity: 0, transform: "translateY(22px) scale(.98)" }, { opacity: 1, transform: "none" }],
    { duration: 500, delay, easing: EASE, fill: "backwards" });
}

/** Freshly shown cards come in: those on screen rise one after another; those further down wait,
 *  hidden, and rise as they are scrolled into view. `fresh` (a new result list) forgets cards still
 *  waiting from the previous list. `quick` (results changing while someone types) only fades. */
export function cascade(cards, { fresh = true, quick = false } = {}) {
  if (fresh) revealer?.disconnect();
  if (!cards.length || !motionOK()) return;
  if (quick) {
    for (const c of cards) if (onScreen(c.getBoundingClientRect())) c.animate({ opacity: [0.35, 1] }, { duration: 200, easing: "ease-out" });
    return;
  }
  const below = [];
  let i = 0;
  for (const c of cards) {
    const r = c.getBoundingClientRect();
    if (onScreen(r)) reveal(c, Math.min(i++, 12) * 45);
    else if (r.top >= innerHeight) below.push(c);
  }
  if (!below.length || !("IntersectionObserver" in window)) return;
  revealer ??= new IntersectionObserver((entries) => {
    let n = 0;
    for (const en of entries) {
      if (!en.isIntersecting) continue;
      revealer.unobserve(en.target);
      reveal(en.target, Math.min(n++, 6) * 60);
    }
  }, { rootMargin: "0px 0px -30px 0px" });
  for (const c of below) { c.classList.add("fx-wait"); revealer.observe(c); }
}

/** List rows in a dialog rise in one after another. */
export function stagger(items) {
  if (!motionOK()) return;
  items.slice(0, 12).forEach((el, i) => el.animate([{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "none" }],
    { duration: 380, delay: 40 + i * 40, easing: EASE, fill: "backwards" }));
}

// ---------------------------------------------------------------- tilt
/** Cards in `container` lean toward the mouse, with a soft glare under the pointer and the product
 *  picture drifting the other way. Mouse only; the card returns smoothly when the pointer leaves. */
export function tilt(container, selector, { max = 7, lift = -3 } = {}) {
  if (!container || !finePointer.matches) return;
  const glare = document.createElement("span");
  glare.className = "fx-glare";
  glare.setAttribute("aria-hidden", "true");
  let card = null, pic = null, box = null, sy = 0, px = 0, py = 0, raf = 0;
  const paint = () => {
    raf = 0;
    if (!card?.isConnected) return;
    const x = Math.min(1, Math.max(0, (px - box.left) / box.width));
    const y = Math.min(1, Math.max(0, (py - (box.top + sy - scrollY)) / box.height));
    card.style.transform = `perspective(900px) translateY(${lift}px) rotateX(${((0.5 - y) * max).toFixed(2)}deg) rotateY(${((x - 0.5) * max * 1.3).toFixed(2)}deg)`;
    glare.style.transform = `translate(${(x * box.width).toFixed(1)}px, ${(y * box.height).toFixed(1)}px)`;
    if (pic && split) pic.style.translate = `${((0.5 - x) * 10).toFixed(1)}px ${((0.5 - y) * 7).toFixed(1)}px`;
  };
  const leave = () => {
    if (!card) return;
    card.removeEventListener("pointerleave", leave);
    card.style.transform = "";
    if (pic) pic.style.translate = "";
    glare.remove();
    card = pic = null;
  };
  container.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || !motionOK()) { leave(); return; }
    const c = e.target.closest(selector);
    if (c !== card) {
      leave();
      if (!c || !container.contains(c)) return;
      card = c;
      box = c.getBoundingClientRect();
      sy = scrollY;
      pic = c.querySelector(".product-image > img");
      c.appendChild(glare);
      c.addEventListener("pointerleave", leave);
    }
    px = e.clientX;
    py = e.clientY;
    raf ||= requestAnimationFrame(paint);
  }, { passive: true });
  // A click opens a dialog over the card: let it settle back.
  container.addEventListener("click", leave);
}

// ---------------------------------------------------------------- numbers and dialogs
/** Counts the number shown in `el` to `to`; the final value is always set, even without frames. */
export function countTo(el, to) {
  const from = Number(el.textContent);
  el.dataset.to = String(to);
  if (!motionOK() || !Number.isFinite(from) || from === to) { el.textContent = String(to); return; }
  const start = performance.now(), ms = 480;
  const step = (now) => {
    if (el.dataset.to !== String(to)) return; // a newer count took over
    const k = Math.min(1, (now - start) / ms);
    el.textContent = String(Math.round(from + (to - from) * (1 - (1 - k) ** 3)));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
  setTimeout(() => { if (el.dataset.to === String(to)) el.textContent = String(to); }, ms + 250);
}

/** Previous/Next in the product details: the old picture swings out one side of its tile while the
 *  new one swings in from the other, and the text fades up. `oldPic` is the previous picture
 *  element (already taken out of the page); the tile clips both, so nothing overflows the dialog. */
export function carousel(stage, oldPic, dir, texts = []) {
  if (!stage || !motionOK()) return;
  const pic = stage.querySelector(":scope > img, :scope > svg");
  const side = (k) => `perspective(800px) translateX(${k * 55}%) rotateY(${-k * 24}deg) scale(.86)`;
  const rest = "perspective(800px) translateX(0%) rotateY(0deg) scale(1)";
  if (oldPic) {
    oldPic.classList.add("fx-out");
    oldPic.setAttribute("aria-hidden", "true");
    oldPic.removeAttribute("alt");
    stage.prepend(oldPic);
    const out = oldPic.animate([{ transform: rest, opacity: 1 }, { transform: side(-dir), opacity: 0 }],
      { duration: 320, easing: "cubic-bezier(.4,0,.7,.4)", fill: "forwards" });
    settle(oldPic, [out], 900);
  }
  pic?.animate([{ transform: side(dir), opacity: 0 }, { transform: rest, opacity: 1 }],
    { duration: 560, delay: 120, easing: "cubic-bezier(.2,.85,.25,1)", fill: "backwards" });
  texts.filter(Boolean).forEach((el, i) => el.animate([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }],
    { duration: 340, delay: 80 + i * 50, easing: EASE, fill: "backwards" }));
}

// ---------------------------------------------------------------- hero
/** A short downward knock, as when something lands hard. */
export function nudge(el, px = 3) {
  if (!el || !split || !motionOK()) return;
  el.animate({ translate: ["0 0", `0 ${px}px`, "0 0"] }, { duration: 200, easing: "ease-out" });
}

/** The hero follows the mouse: an orange spotlight under the pointer, the hammer leaning toward it
 *  and the rings drifting the other way (CSS transitions smooth the movement). Mouse only. */
export function heroFollow(hero, { tool, orbit } = {}) {
  if (!hero || !finePointer.matches || !split) return;
  const glow = document.createElement("span");
  glow.className = "hero-glow";
  glow.setAttribute("aria-hidden", "true");
  hero.prepend(glow);
  let raf = 0, px = 0, py = 0;
  const paint = () => {
    raf = 0;
    if (!hero.classList.contains("lit")) return;
    const box = hero.getBoundingClientRect();
    const x = px - box.left, y = py - box.top, nx = x / box.width - 0.5, ny = y / box.height - 0.5;
    glow.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
    if (tool) { tool.style.translate = `${(nx * 22).toFixed(1)}px ${(ny * 16).toFixed(1)}px`; tool.style.rotate = `${(nx * 6).toFixed(2)}deg`; }
    if (orbit) orbit.style.translate = `${(-nx * 14).toFixed(1)}px ${(-ny * 10).toFixed(1)}px`;
  };
  const leave = () => {
    hero.classList.remove("lit");
    if (tool) tool.style.translate = tool.style.rotate = "";
    if (orbit) orbit.style.translate = "";
  };
  hero.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || !motionOK()) { leave(); return; }
    hero.classList.add("lit");
    px = e.clientX;
    py = e.clientY;
    raf ||= requestAnimationFrame(paint);
  }, { passive: true });
  hero.addEventListener("pointerleave", leave);
}

let striking = false;
/** The hero hammer winds up and strikes, pivoting at its grip; at the moment of impact sparks fly
 *  from its face with a shockwave, and `onImpact` runs. One strike at a time. */
export function strike(svg, { onImpact } = {}) {
  const swing = svg?.querySelector(".swing"), face = svg?.querySelector(".strike-point");
  if (!swing || !face || striking || !motionOK()) return;
  striking = true;
  const ms = 820, impact = 0.55;
  const a = swing.animate([
    { transform: "rotate(0deg)", easing: "cubic-bezier(.2,.7,.4,1)" },
    { transform: "rotate(20deg)", offset: 0.4, easing: "cubic-bezier(.7,0,1,.6)" },
    { transform: "rotate(-12deg)", offset: impact, easing: "ease-out" },
    { transform: "rotate(-6deg)", offset: 0.66, easing: "cubic-bezier(.3,.6,.4,1)" },
    { transform: "rotate(0deg)" },
  ], { duration: ms });
  const t = setTimeout(() => {
    const r = face.getBoundingClientRect();
    if (onScreen(r)) sparks(r.left + r.width / 2, r.top + r.height / 2);
    onImpact?.();
  }, ms * impact);
  const done = () => { striking = false; };
  a.finished.then(done, () => { clearTimeout(t); done(); });
  setTimeout(done, ms + 400);
}

/** Sparks fanning out from (x, y) and falling, with an elliptical shockwave. */
function sparks(x, y) {
  const host = document.createElement("div");
  host.className = "fx-sparks";
  host.style.cssText = `left:${x}px;top:${y}px`;
  host.innerHTML = `<i></i>${"<b></b>".repeat(14)}`;
  fxLayer().appendChild(host);
  const anims = [host.firstElementChild.animate({ scale: ["0.2", "2.6"], opacity: [0.85, 0] }, { duration: 620, easing: EASE, fill: "forwards" })];
  host.querySelectorAll("b").forEach((b, i) => {
    // Mostly up and to the sides, a few skidding along the ground; each then falls.
    const angle = (-175 + (i / 13) * 170 + (Math.random() * 14 - 7)) * (Math.PI / 180);
    const dist = 38 + Math.random() * 62, dx = Math.cos(angle) * dist, dy = Math.sin(angle) * dist;
    const ms = 620 + Math.random() * 320;
    anims.push(b.animate([
      { translate: "0px 0px", rotate: `${(angle * 180) / Math.PI}deg`, opacity: 1, scale: "1" },
      { translate: `${(dx * 0.75).toFixed(1)}px ${(dy * 0.75).toFixed(1)}px`, opacity: 1, offset: 0.45 },
      { translate: `${dx.toFixed(1)}px ${(dy + 34).toFixed(1)}px`, rotate: `${(angle * 180) / Math.PI + 40}deg`, opacity: 0, scale: "0.4" },
    ], { duration: ms, delay: Math.random() * 60, easing: "cubic-bezier(.2,.7,.5,1)", fill: "both" }));
  });
  settle(host, anims, 1600);
}

// ---------------------------------------------------------------- headings
/** Wraps each word of `el` (text only; elements such as <em> and <br> stay) for the word reveal. */
function splitWords(el) {
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const frag = document.createDocumentFragment();
    for (const part of node.textContent.split(/(\s+)/)) {
      if (!part) continue;
      if (/^\s+$/.test(part)) { frag.append(part); continue; }
      const word = document.createElement("span");
      word.className = "fx-w";
      const inner = document.createElement("span");
      inner.textContent = part;
      word.append(inner);
      frag.append(word);
    }
    node.replaceWith(frag);
  }
}

/** Headings rise into view word by word the first time they are scrolled to. Each word is clipped
 *  by its own inline box (clip-path), so the layout is exactly that of the plain heading. */
export function wordsIn(headings) {
  if (!motionOK() || !split || !("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (!en.isIntersecting) continue;
      io.unobserve(en.target);
      en.target.classList.remove("fx-words-wait");
      if (!motionOK()) continue;
      en.target.querySelectorAll(".fx-w > span").forEach((w, i) => w.animate(
        [{ transform: "translateY(140%)" }, { transform: "none" }],
        { duration: 720, delay: 60 + i * 60, easing: EASE, fill: "backwards" }));
    }
  }, { threshold: 0.3 });
  for (const h of headings) {
    splitWords(h);
    h.classList.add("fx-words-wait");
    io.observe(h);
  }
}

// ---------------------------------------------------------------- quotation
/** The prepared request feeds out of the printer slot, then the "Ready · not sent" stamp lands. */
export function printOut(paper) {
  if (!paper || !motionOK()) return;
  const sheet = paper.querySelector(".prepared"), stamp = paper.querySelector(".stamp");
  sheet?.animate([{ clipPath: "inset(0 0 100% 0)", transform: "translateY(-16px)" }, { clipPath: "inset(0 0 0% 0)", transform: "none" }],
    { duration: 1000, delay: 120, easing: "cubic-bezier(.3,.55,.35,1)", fill: "backwards" });
  stamp?.animate([
    { opacity: 0, transform: "rotate(-8deg) scale(2.6)" },
    { opacity: 1, transform: "rotate(-8deg) scale(.9)", offset: 0.7 },
    { opacity: 1, transform: "rotate(-8deg) scale(1)" },
  ], { duration: 380, delay: 1150, easing: "cubic-bezier(.5,0,.75,0)", fill: "backwards" });
  if (sheet && split) sheet.animate({ translate: ["0 0", "0 3px", "0 0"] }, { duration: 200, delay: 1420, easing: "ease-out" });
}