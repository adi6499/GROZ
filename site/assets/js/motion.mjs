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
export function flyTo(src, target, onLand, { bare = false } = {}) {
  const a = src?.getBoundingClientRect(), b = target?.getBoundingClientRect();
  if (!split || !motionOK() || !a || !b || !onScreen(a) || !b.width) { onLand?.(); return; }
  const card = document.createElement("div");
  card.className = bare ? "fx-fly bare" : "fx-fly";
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

/** Where the cards on screen are now, by product id, for `cascade(..., { from })`. */
export function positions(cards) {
  const map = new Map();
  if (!motionOK()) return map;
  for (const c of cards) {
    const r = c.getBoundingClientRect();
    if (onScreen(r)) map.set(c.dataset.id, r);
  }
  return map;
}

function glide(el, prev, now, i) {
  const dx = prev.left - now.left, dy = prev.top - now.top;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
  el.animate([{ transform: `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px)` }, { transform: "none" }],
    { duration: 560, delay: Math.min(i, 12) * 18, easing: EASE, fill: "backwards" });
}

/** Freshly shown cards come in: those on screen rise one after another; those further down wait,
 *  hidden, and rise as they are scrolled into view. `fresh` (a new result list) forgets cards still
 *  waiting from the previous list. `quick` (results changing while someone types) only fades. */
export function cascade(cards, { fresh = true, quick = false, from = null } = {}) {
  if (fresh) revealer?.disconnect();
  if (!cards.length || !motionOK()) return;
  if (quick) {
    for (const c of cards) if (onScreen(c.getBoundingClientRect())) c.animate({ opacity: [0.35, 1] }, { duration: 200, easing: "ease-out" });
    return;
  }
  const below = [];
  let i = 0, g = 0;
  for (const c of cards) {
    const r = c.getBoundingClientRect();
    const prev = from?.get(c.dataset.id);
    // A card that was on screen before glides from where it was (sorting looks like a shuffle).
    if (prev && Math.abs(prev.top - r.top) < innerHeight * 1.5) { glide(c, prev, r, g++); continue; }
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

// ---------------------------------------------------------------- smooth following
/** Moves a set of numbers toward their targets on every display frame (60, 120 or 144 Hz alike), with
 *  frame-rate independent easing, and stops once they have settled. `apply(values)` writes them;
 *  `speed` is per second (a number, or one per value). Used for everything that follows the mouse:
 *  the browser's own transitions restart on every pointer event and lag or judder. */
function follower(apply, speed, start) {
  let cur = { ...start }, target = { ...start }, raf = 0, last = 0, onRest = null;
  const step = (now) => {
    const dt = Math.min(0.064, Math.max(0.001, (now - last) / 1000));
    last = now;
    let moving = false;
    for (const k in target) {
      const d = target[k] - cur[k];
      if (Math.abs(d) > 0.004) {
        cur[k] += d * (1 - Math.exp(-(typeof speed === "number" ? speed : speed[k] ?? 12) * dt));
        moving = true;
      } else cur[k] = target[k];
    }
    apply(cur);
    if (moving) { raf = requestAnimationFrame(step); return; }
    raf = 0;
    const done = onRest;
    onRest = null;
    done?.();
  };
  return {
    /** Heads for `values`; `rest` runs once they are reached (unless a new target comes first). */
    to(values, rest = null) {
      target = { ...target, ...values };
      onRest = rest;
      if (!raf) { last = performance.now(); raf = requestAnimationFrame(step); }
    },
    /** Moves straight to `values` (no easing), e.g. to start the glare under the pointer. */
    jump(values) { cur = { ...cur, ...values }; },
    get value() { return cur; },
  };
}

// ---------------------------------------------------------------- gliding highlight
/** A highlight glides to whichever item in `container` the mouse is over (or keyboard focus is on), and
 *  fades out when the pointer leaves: an orange underline under the header links (`underline`), a soft
 *  row in the Categories menu. Only its transform and opacity change, eased on every display frame
 *  (follower), so it keeps up at any refresh rate. Mouse only; the container's content may be rebuilt
 *  (the highlight puts itself back). */
export function glider(container, selector, { cls = "fx-glide", underline = false } = {}) {
  if (!container || !motionOK() || !finePointer.matches) return;
  const bar = document.createElement("span");
  bar.className = cls;
  bar.setAttribute("aria-hidden", "true");
  container.classList.add("has-glide");
  let shown = false;
  const f = follower((v) => { bar.style.transform = `translate(${v.x}px, ${v.y}px) scale(${v.sx}, ${v.sy})`; },
    18, { x: 0, y: 0, sx: 1, sy: 1 });
  const go = (item) => {
    if (!bar.isConnected) container.prepend(bar);
    const c = container.getBoundingClientRect();
    const r = item.getBoundingClientRect();
    if (!underline && !bar.dataset.sized) { // a row: the same size as the items, so it is never stretched
      bar.style.width = `${r.width}px`;
      bar.style.height = `${r.height}px`;
      bar.dataset.sized = "1";
    }
    const x = r.left - c.left - container.clientLeft;
    const y = underline ? r.bottom - c.top - container.clientTop - 9 : r.top - c.top - container.clientTop;
    const v = { x, y, sx: r.width / (bar.offsetWidth || 1), sy: underline ? 1 : r.height / (bar.offsetHeight || 1) };
    if (!shown) {
      f.jump(v); // appears where it is needed, then glides from item to item
      shown = true;
      bar.classList.add("on");
    }
    f.to(v);
  };
  const hide = () => {
    shown = false;
    bar.classList.remove("on");
  };
  container.addEventListener("pointerover", (e) => {
    if (e.pointerType !== "mouse") return;
    const item = e.target.closest(selector);
    if (item && container.contains(item)) go(item);
  });
  container.addEventListener("pointerleave", hide);
  container.addEventListener("focusin", (e) => {
    const item = e.target.closest(selector);
    if (item && container.contains(item) && e.target.matches(":focus-visible")) go(item);
  });
  container.addEventListener("focusout", (e) => { if (!container.contains(e.relatedTarget)) hide(); });
}

// ---------------------------------------------------------------- tilt
/** Cards in `container` lean toward the mouse, with a soft glare under the pointer and the product
 *  picture drifting the other way. Mouse only; the card eases back when the pointer leaves. Each card
 *  is smoothed on every display frame (follower) and is its own compositor layer while it moves. */
export function tilt(container, selector, { max = 7, lift = -3 } = {}) {
  if (!container || !finePointer.matches) return;
  const REST = { rx: 0, ry: 0, lift: 0, gx: 0, gy: 0, g: 0, px: 0, py: 0 };
  const SPEED = { rx: 12, ry: 12, lift: 12, gx: 20, gy: 20, g: 9, px: 8, py: 8 };
  const cards = new WeakMap();
  let card = null, box = null, sy = 0;
  const stateOf = (c) => {
    let s = cards.get(c);
    if (s) return s;
    const glare = document.createElement("span");
    glare.className = "fx-glare";
    glare.setAttribute("aria-hidden", "true");
    const pic = c.querySelector(".product-image > img");
    s = { glare, pic };
    s.f = follower((v) => {
      c.style.transform = `perspective(900px) translateY(${v.lift.toFixed(2)}px) rotateX(${v.rx.toFixed(2)}deg) rotateY(${v.ry.toFixed(2)}deg)`;
      glare.style.transform = `translate(${v.gx.toFixed(1)}px, ${v.gy.toFixed(1)}px)`;
      glare.style.opacity = v.g.toFixed(3);
      if (pic && split) pic.style.translate = `${v.px.toFixed(2)}px ${v.py.toFixed(2)}px`;
    }, SPEED, REST);
    cards.set(c, s);
    return s;
  };
  const rest = (c) => {
    const s = cards.get(c);
    if (!s) return;
    s.f.to(REST, () => {
      c.style.transform = "";
      if (s.pic) s.pic.style.translate = "";
      s.glare.remove();
      c.classList.remove("tilting");
    });
  };
  const onLeave = (e) => {
    const c = e.currentTarget;
    c.removeEventListener("pointerleave", onLeave);
    rest(c);
    if (card === c) card = null;
  };
  container.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || !motionOK()) { if (card) { rest(card); card = null; } return; }
    const c = e.target.closest(selector);
    if (c !== card) {
      if (card) rest(card);
      card = c && container.contains(c) ? c : null;
      if (!card) return;
      box = card.getBoundingClientRect();
      sy = scrollY;
      const s = stateOf(card);
      if (!s.glare.isConnected) card.appendChild(s.glare);
      card.classList.add("tilting");
      s.f.jump({ gx: e.clientX - box.left, gy: e.clientY - box.top });
      card.addEventListener("pointerleave", onLeave);
    }
    const x = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width));
    const y = Math.min(1, Math.max(0, (e.clientY - (box.top + sy - scrollY)) / box.height));
    stateOf(card).f.to({ rx: (0.5 - y) * max, ry: (x - 0.5) * max * 1.3, lift, gx: x * box.width, gy: y * box.height, g: 1, px: (0.5 - x) * 10, py: (0.5 - y) * 7 });
  }, { passive: true });
  // A click opens a dialog over the card: let it settle back.
  container.addEventListener("click", () => { if (card) { card.removeEventListener("pointerleave", onLeave); rest(card); card = null; } });
}

// ---------------------------------------------------------------- numbers and dialogs
/** Counts the number shown in `el` to `to`; the final value is always set, even without frames. */
export function countTo(el, to, ms = 480) {
  const from = Number(el.textContent);
  el.dataset.to = String(to);
  if (!motionOK() || !Number.isFinite(from) || from === to) { el.textContent = String(to); return; }
  const start = performance.now();
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
 *  and the rings drifting the other way, each smoothed on every display frame. Mouse only. */
export function heroFollow(hero, { tool, orbit } = {}) {
  if (!hero || !finePointer.matches || !split) return;
  const glow = document.createElement("span");
  glow.className = "hero-glow";
  glow.setAttribute("aria-hidden", "true");
  hero.prepend(glow);
  const REST = { gx: 0, gy: 0, tx: 0, ty: 0, rot: 0, ox: 0, oy: 0 };
  const f = follower((v) => {
    glow.style.transform = `translate(${v.gx.toFixed(1)}px, ${v.gy.toFixed(1)}px)`;
    if (tool) { tool.style.translate = `${v.tx.toFixed(2)}px ${v.ty.toFixed(2)}px`; tool.style.rotate = `${v.rot.toFixed(3)}deg`; }
    if (orbit) orbit.style.translate = `${v.ox.toFixed(2)}px ${v.oy.toFixed(2)}px`;
  }, { gx: 16, gy: 16, tx: 4.5, ty: 4.5, rot: 4.5, ox: 3.5, oy: 3.5 }, REST);
  let inside = false;
  hero.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || !motionOK()) return;
    const box = hero.getBoundingClientRect();
    const x = e.clientX - box.left, y = e.clientY - box.top, nx = x / box.width - 0.5, ny = y / box.height - 0.5;
    if (!inside) { inside = true; hero.classList.add("lit"); f.jump({ gx: x, gy: y }); }
    f.to({ gx: x, gy: y, tx: nx * 22, ty: ny * 16, rot: nx * 6, ox: -nx * 14, oy: -ny * 10 });
  }, { passive: true });
  hero.addEventListener("pointerleave", () => {
    inside = false;
    hero.classList.remove("lit");
    f.to({ tx: 0, ty: 0, rot: 0, ox: 0, oy: 0 }, () => {
      if (tool) tool.style.translate = tool.style.rotate = "";
      if (orbit) orbit.style.translate = "";
    });
  });
}

/** Puts the hammer's pivot at its grip (the `.grip-point` marker), measured while it is at rest; the
 *  lean and the strike then both turn about the grip. */
export function hammerPivot(wrap) {
  const grip = wrap?.querySelector(".grip-point");
  if (!grip) return;
  const set = () => {
    if (wrap.style.rotate || striking) return; // only while at rest
    const wr = wrap.getBoundingClientRect(), gr = grip.getBoundingClientRect();
    if (!wr.width) return;
    wrap.style.transformOrigin = `${(gr.left + gr.width / 2 - wr.left).toFixed(1)}px ${(gr.top + gr.height / 2 - wr.top).toFixed(1)}px`;
  };
  set();
  let t = 0;
  addEventListener("resize", () => { clearTimeout(t); t = setTimeout(set, 200); }, { passive: true });
}

let striking = false;
/** The hero hammer winds up and strikes, pivoting at its grip; at the moment of impact sparks fly
 *  from its face with a shockwave, and `onImpact` runs. One strike at a time. The whole drawing turns
 *  as one compositor layer, so nothing is redrawn while it swings. */
export function strike(wrap, { onImpact } = {}) {
  const face = wrap?.querySelector(".strike-point");
  if (!face || striking || !motionOK()) return;
  striking = true;
  const ms = 820, impact = 0.55;
  const a = wrap.animate([
    { transform: "rotate(0deg)", easing: "cubic-bezier(.2,.7,.4,1)" },
    { transform: "rotate(20deg)", offset: 0.4, easing: "cubic-bezier(.7,0,1,.6)" },
    { transform: "rotate(-12deg)", offset: impact, easing: "ease-out" },
    { transform: "rotate(-6deg)", offset: 0.66, easing: "cubic-bezier(.3,.6,.4,1)" },
    { transform: "rotate(0deg)" },
  ], { duration: ms });
  // Sparks at the moment of impact, timed by the strike itself (not a separate timer).
  const hit = wrap.animate({ opacity: [1, 1] }, { duration: ms * impact });
  let sparked = false;
  const spark = () => {
    if (sparked) return;
    sparked = true;
    const r = face.getBoundingClientRect();
    if (onScreen(r)) sparks(r.left + r.width / 2, r.top + r.height / 2);
    onImpact?.();
  };
  hit.finished.then(spark, () => {});
  const done = () => { striking = false; };
  a.finished.then(done, done);
  setTimeout(done, ms + 600);
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
export function wordsIn(headings, { after = null } = {}) {
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
  }
  // Hidden at once; they start rising once `after` (e.g. the intro) is done.
  Promise.resolve(after).then(() => headings.forEach((h) => io.observe(h)));
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
  // ...and confetti bursts from the stamp.
  if (stamp) setTimeout(() => {
    if (!stamp.isConnected) return;
    const r = stamp.getBoundingClientRect();
    confetti(r.left + r.width / 2, r.top + r.height / 2);
  }, 1480);
}
// ---------------------------------------------------------------- wave 3: small delights
/** A soft ripple spreads from where a button was pressed, clipped to the button's own shape. */
export function ripple(btn, x, y) {
  if (!btn?.isConnected || !motionOK()) return;
  const r = btn.getBoundingClientRect();
  if (!onScreen(r)) return;
  if (!x && !y) { x = r.left + r.width / 2; y = r.top + r.height / 2; } // keyboard: from the centre
  const size = 2 * Math.hypot(Math.max(x - r.left, r.right - x), Math.max(y - r.top, r.bottom - y));
  const clip = document.createElement("span");
  clip.className = "fx-rip";
  clip.setAttribute("aria-hidden", "true");
  const dot = document.createElement("i");
  dot.style.cssText = `left:${x - r.left - size / 2}px;top:${y - r.top - size / 2}px;width:${size}px;height:${size}px`;
  clip.appendChild(dot);
  btn.appendChild(clip);
  const a = dot.animate([{ transform: "scale(0)", opacity: 0.3 }, { transform: "scale(1)", opacity: 0 }],
    { duration: 600, easing: "cubic-bezier(.2,.6,.3,1)", fill: "forwards" });
  settle(clip, [a], 1000);
}

/** Primary buttons lean toward the mouse while it is over them (magnetic), smoothed on every display
 *  frame, and ease back when it leaves. Mouse only. */
export function magnetic(selector, { pull = 0.3, max = 7 } = {}) {
  if (!finePointer.matches || !split) return;
  const buttons = new WeakMap();
  let btn = null;
  const followerOf = (b) => {
    let f = buttons.get(b);
    if (!f) {
      f = follower((v) => { b.style.translate = `${v.x.toFixed(2)}px ${v.y.toFixed(2)}px`; }, 15, { x: 0, y: 0 });
      buttons.set(b, f);
    }
    return f;
  };
  const release = () => {
    if (!btn) return;
    const b = btn;
    btn = null;
    followerOf(b).to({ x: 0, y: 0 }, () => { b.style.translate = ""; });
  };
  const clamp = (v) => Math.max(-max, Math.min(max, v));
  document.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || !motionOK()) { release(); return; }
    const b = e.target.closest?.(selector) || null;
    if (b !== btn) { release(); btn = b; }
    if (!btn) return;
    const f = followerOf(btn), r = btn.getBoundingClientRect();
    // The measured box includes the current lean: measure from the button's resting centre.
    const cx = r.left + r.width / 2 - f.value.x, cy = r.top + r.height / 2 - f.value.y;
    f.to({ x: clamp((e.clientX - cx) * pull), y: clamp((e.clientY - cy) * pull) });
  }, { passive: true });
  root.addEventListener("pointerleave", release);
}

/** The search box types example searches into its placeholder, one after another, while it is on
 *  screen, empty and not focused; otherwise its own placeholder is shown. */
export function typeHints(input, hints) {
  if (!input || !hints.length || !motionOK()) return;
  const base = input.placeholder;
  let visible = true, word = 0, n = 0, dir = 1;
  if ("IntersectionObserver" in window) new IntersectionObserver(([en]) => { visible = en.isIntersecting; }).observe(input);
  const idle = () => !visible || document.activeElement === input || input.value || document.visibilityState !== "visible" || !motionOK();
  const tick = () => {
    if (idle()) { input.placeholder = base; n = 0; dir = 1; setTimeout(tick, 700); return; }
    const text = `Try “${hints[word]}”`;
    n = Math.max(0, Math.min(text.length, n + dir));
    input.placeholder = text.slice(0, n);
    let wait = dir > 0 ? 60 : 24;
    if (dir > 0 && n >= text.length) { dir = -1; wait = 1800; }
    else if (dir < 0 && n === 0) { dir = 1; word = (word + 1) % hints.length; wait = 420; }
    setTimeout(tick, wait);
  };
  setTimeout(tick, 2200);
}

/** A magnifier over the product picture in the details (mouse only), when the picture file is
 *  meaningfully larger than it is shown. */
export function loupe(stage, { size = 170 } = {}) {
  const img = stage?.querySelector(":scope > img");
  if (!img || !finePointer.matches) return;
  let lens = null, zoom = 1, raf = 0, px = 0, py = 0;
  const paint = () => {
    raf = 0;
    if (!lens) return;
    const s = stage.getBoundingClientRect(), r = img.getBoundingClientRect();
    const x = px - r.left, y = py - r.top, h = size / 2;
    lens.style.opacity = x >= 0 && y >= 0 && x <= r.width && y <= r.height ? "1" : "0";
    lens.style.transform = `translate(${(px - s.left - h).toFixed(1)}px, ${(py - s.top - h).toFixed(1)}px)`;
    lens.style.backgroundSize = `${(r.width * zoom).toFixed(1)}px ${(r.height * zoom).toFixed(1)}px`;
    lens.style.backgroundPosition = `${(h - x * zoom).toFixed(1)}px ${(h - y * zoom).toFixed(1)}px`;
  };
  stage.addEventListener("pointerenter", (e) => {
    if (e.pointerType !== "mouse" || lens || !img.complete || !img.naturalWidth) return;
    zoom = Math.min(3, img.naturalWidth / img.getBoundingClientRect().width);
    if (zoom < 1.4) return;
    lens = document.createElement("span");
    lens.className = "fx-loupe";
    lens.setAttribute("aria-hidden", "true");
    lens.style.cssText = `width:${size}px;height:${size}px;background-image:url("${(img.currentSrc || img.src).replace(/"/g, "%22")}")`;
    stage.classList.add("zooming");
    stage.appendChild(lens);
    px = e.clientX; py = e.clientY;
    paint();
  });
  stage.addEventListener("pointermove", (e) => { px = e.clientX; py = e.clientY; raf ||= requestAnimationFrame(paint); });
  stage.addEventListener("pointerleave", () => { lens?.remove(); lens = null; stage.classList.remove("zooming"); });
}

/** Confetti bursting up from (x, y) and falling, in the site's colours. */
export function confetti(x, y, count = 40) {
  if (!motionOK() || !split) return;
  const host = document.createElement("div");
  host.className = "fx-confetti";
  host.style.cssText = `left:${x}px;top:${y}px`;
  host.innerHTML = "<i></i>".repeat(count);
  fxLayer().appendChild(host);
  const anims = [...host.children].map((c, i) => {
    const angle = (-155 + Math.random() * 130) * (Math.PI / 180), speed = 70 + Math.random() * 120;
    const dx = Math.cos(angle) * speed, dy = Math.sin(angle) * speed, spin = (Math.random() < 0.5 ? -1 : 1) * (360 + Math.random() * 540);
    c.style.setProperty("--c", ["#f4511e", "#ff9a6b", "#1f7a49", "#3d4148", "#ffd36b"][i % 5]);
    return c.animate([
      { translate: "0px 0px", rotate: "0deg", opacity: 1 },
      { translate: `${dx.toFixed(1)}px ${dy.toFixed(1)}px`, opacity: 1, offset: 0.35 },
      { translate: `${(dx * 1.4).toFixed(1)}px ${(dy + 190 + Math.random() * 90).toFixed(1)}px`, rotate: `${spin.toFixed(0)}deg`, opacity: 0 },
    ], { duration: 1300 + Math.random() * 600, delay: Math.random() * 90, easing: "cubic-bezier(.2,.6,.4,1)", fill: "both" });
  });
  settle(host, anims, 2600);
}

/** A "back to top" button that appears once the page is scrolled well down; pressed, it lifts off. */
export function backToTop({ onTop } = {}) {
  const btn = document.createElement("button");
  btn.className = "to-top";
  btn.type = "button";
  btn.setAttribute("aria-label", "Back to top");
  btn.innerHTML = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5.5 11.5 12 5l6.5 6.5"/></svg>';
  document.body.appendChild(btn);
  let raf = 0, launch = null;
  const update = () => {
    raf = 0;
    const on = scrollY > innerHeight * 1.2;
    btn.classList.toggle("show", on);
    // After a lift-off, the button stays out of sight until it has faded out at the top.
    if (!on && launch) { const a = launch; launch = null; setTimeout(() => { if (!btn.classList.contains("show")) a.cancel(); else launch = a; }, 320); }
  };
  addEventListener("scroll", () => { raf ||= requestAnimationFrame(update); }, { passive: true });
  update();
  btn.addEventListener("click", () => {
    if (motionOK() && split) {
      launch?.cancel();
      launch = btn.animate([{ translate: "0 0", scale: "1", opacity: 1 }, { translate: "0 8px", scale: "0.92", opacity: 1, offset: 0.2 },
        { translate: "0 -110px", scale: "0.7", opacity: 0 }], { duration: 600, easing: "cubic-bezier(.5,0,.75,0)", fill: "forwards" });
    }
    scrollTo({ top: 0, behavior: motionOK() ? "smooth" : "auto" });
    onTop?.();
  });
  return btn;
}
// ---------------------------------------------------------------- wave 4: exits and finishing touches
/** Plays a short exit on elements about to be hidden, then calls `done` (at once without motion).
 *  Returns a function that stops the exit without calling `done`, leaving the elements shown. */
export function leave(parts, done, ms = 200) {
  const live = parts.filter(([el]) => el);
  if (!motionOK() || !live.length) { done(); return () => {}; }
  const anims = live.map(([el, frames]) => el.animate(frames, { duration: ms, easing: "cubic-bezier(.4,0,.9,.6)", fill: "forwards" }));
  let over = false;
  // Hide first, then drop the exit's end state, in the same task: no frame shows the element again.
  const end = () => { if (over) return; over = true; clearTimeout(timer); done(); anims.forEach((a) => a.cancel()); };
  const timer = setTimeout(end, ms + 200);
  Promise.all(anims.map((a) => a.finished)).then(end, () => {});
  return () => { if (over) return; over = true; clearTimeout(timer); anims.forEach((a) => a.cancel()); };
}

/** Soft embers drifting up behind the hero hammer, as from a forge. CSS animates them (transform and
 *  opacity), paused while the hero is off screen. */
export function embers(container, count = 16) {
  if (!container || !motionOK()) return;
  const box = document.createElement("span");
  box.className = "embers";
  box.setAttribute("aria-hidden", "true");
  box.innerHTML = Array.from({ length: count }, () => {
    const t = 4 + Math.random() * 4;
    return `<i style="--x:${(15 + Math.random() * 70).toFixed(1)}%;--dx:${(Math.random() * 80 - 40).toFixed(0)}px;--t:${t.toFixed(2)}s;--d:-${(Math.random() * t).toFixed(2)}s;--s:${(2 + Math.random() * 2.5).toFixed(1)}px"></i>`;
  }).join("");
  container.prepend(box);
}

/** The toast springs in and its timer bar runs down over `ms`. */
export function toastIn(el, ms) {
  if (!el || !motionOK()) return;
  if (split) el.animate({ scale: ["0.9", "1.04", "1"] }, { duration: 420, easing: "ease-out" });
  el.querySelector(".toast-bar")?.animate({ transform: ["scaleX(1)", "scaleX(0)"] }, { duration: ms, easing: "linear", fill: "forwards" });
}

/** A quarter-turn spin into place (the theme button's sun or moon). */
export function spin(el) {
  if (!el || !split || !motionOK()) return;
  el.animate({ rotate: ["-120deg", "0deg"], scale: ["0.5", "1"] }, { duration: 520, easing: EASE });
}
