// Pure logic for the verification tool (no DOM), tested with node --test "verify/tests/*.test.mjs".

export const FILTERS = ["to_check", "flagged", "verified", "all"];

/** "to_check" (no decision, or values changed since the decision), "flagged" or "verified". */
export function stateOf(rec) {
  const s = rec?.decision?.state;
  return s === "verified" || s === "flagged" ? s : "to_check";
}

/** True when a decision exists but the product's values changed afterwards. */
export function isStale(rec) {
  return rec?.decision?.state === "stale";
}

const norm = (s) => String(s ?? "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
const codeKey = (s) => String(s ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");

export function matches(rec, query) {
  const q = norm(query).trim();
  if (!q) return true;
  const k = codeKey(query);
  if (k.length >= 2 && [rec.cat_nr, rec.ord_nr].some((c) => codeKey(c).includes(k))) return true;
  const hay = norm([rec.cat_nr, rec.ord_nr, rec.title, rec.catalogue, rec.category].join(" "));
  return q.split(/\s+/).every((t) => hay.includes(t));
}

export function filterQueue(records, { filter = "to_check", catalogue = "", query = "" } = {}) {
  return records.filter((r) =>
    (filter === "all" || stateOf(r) === filter) &&
    (!catalogue || r.pdf === catalogue) &&
    matches(r, query));
}

export function counts(records) {
  const c = { to_check: 0, flagged: 0, verified: 0, stale: 0, total: records.length };
  for (const r of records) {
    c[stateOf(r)] += 1;
    if (isStale(r)) c.stale += 1;
  }
  return c;
}

/** The id after (dir = 1) or before (dir = -1) `id` in `list`; null at either end. */
export function step(list, id, dir) {
  const i = list.findIndex((r) => r.id === id);
  if (i < 0) return list[0]?.id ?? null;
  return list[i + dir]?.id ?? null;
}

/** After a decision: the next product still in the list, else the previous one, else null. */
export function afterDecision(listBefore, listAfter, id) {
  const i = listBefore.findIndex((r) => r.id === id);
  const stillThere = new Set(listAfter.map((r) => r.id));
  for (let j = i + 1; j < listBefore.length; j++) if (stillThere.has(listBefore[j].id) && listBefore[j].id !== id) return listBefore[j].id;
  for (let j = i - 1; j >= 0; j--) if (stillThere.has(listBefore[j].id) && listBefore[j].id !== id) return listBefore[j].id;
  return listAfter.find((r) => r.id === id)?.id ?? null;
}

/** CSS position (percent of the rendered area) for a box in PDF points. */
export function boxStyle(rect, clip) {
  const w = clip[2] - clip[0], h = clip[3] - clip[1];
  const pct = (v) => `${Math.round(v * 10000) / 100}%`;
  return {
    left: pct((rect[0] - clip[0]) / w), top: pct((rect[1] - clip[1]) / h),
    width: pct((rect[2] - rect[0]) / w), height: pct((rect[3] - rect[1]) / h),
  };
}

/** Validation done before sending (the server checks again). */
export function decisionErrors({ status, reviewer, comment, fields }) {
  const errors = {};
  if (!String(reviewer ?? "").trim()) errors.reviewer = "Enter your name: every decision records who made it.";
  if (status === "flagged") {
    if (!String(comment ?? "").trim()) errors.comment = "Describe what does not match the page.";
    if (!(fields || []).length) errors.fields = "Choose at least one field (or “Other”).";
  }
  return errors;
}

export function decisionText(rec) {
  const d = rec?.decision;
  if (!d) return { tone: "none", text: "Not checked yet" };
  const when = String(d.at || "").slice(0, 10);
  if (d.state === "stale") return { tone: "stale", text: `Values changed since ${d.reviewer} ${d.status === "verified" ? "verified" : "flagged"} it on ${when} — check again` };
  if (d.state === "verified") return { tone: "verified", text: `Verified by ${d.reviewer} on ${when}` };
  return { tone: "flagged", text: `Flagged by ${d.reviewer} on ${when}: ${d.comment}` };
}
