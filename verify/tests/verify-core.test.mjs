// Unit tests for the verification tool's logic.  Run:  node --test "verify/tests/*.test.mjs"
import { test } from "node:test";
import assert from "node:assert/strict";
import * as vc from "../verify-core.mjs";

const R = (id, o = {}) => ({ id, cat_nr: o.cat ?? id.toUpperCase(), ord_nr: o.ord ?? null, title: o.title ?? "", pdf: o.pdf ?? "a.pdf",
  catalogue: "A", category: "Cat", decision: o.decision ?? null });
const done = (state) => ({ state, status: state === "stale" ? "verified" : state, reviewer: "Asha", at: "2026-10-14T09:00:00+00:00", comment: "Box qty is 100", fields: [] });
const LIST = [
  R("a", { cat: "LED/621", ord: "55044", title: "Worklight" }),
  R("b", { decision: done("verified") }),
  R("c", { decision: done("flagged"), pdf: "b.pdf" }),
  R("d", { decision: done("stale"), title: "Vee Blocks Cast Iron" }),
];
const ids = (l) => l.map((r) => r.id);

test("a changed-since-checked product is back in the to-check list", () => {
  assert.deepEqual(LIST.map(vc.stateOf), ["to_check", "verified", "flagged", "to_check"]);
  assert.deepEqual(ids(vc.filterQueue(LIST, { filter: "to_check" })), ["a", "d"]);
  assert.deepEqual(vc.counts(LIST), { to_check: 2, flagged: 1, verified: 1, stale: 1, total: 4 });
});

test("filters combine state, catalogue and search (codes in any spelling)", () => {
  assert.deepEqual(ids(vc.filterQueue(LIST, { filter: "all", catalogue: "b.pdf" })), ["c"]);
  for (const q of ["led 621", "LED-621", "55044"]) assert.deepEqual(ids(vc.filterQueue(LIST, { filter: "all", query: q })), ["a"], q);
  assert.deepEqual(ids(vc.filterQueue(LIST, { filter: "to_check", query: "vee blocks" })), ["d"]);
});

test("moving through the list and choosing what comes after a decision", () => {
  assert.equal(vc.step(LIST, "a", 1), "b");
  assert.equal(vc.step(LIST, "a", -1), null);
  assert.equal(vc.step(LIST, "zz", 1), "a");
  const before = [R("a"), R("b"), R("c")];
  assert.equal(vc.afterDecision(before, [R("a"), R("c")], "b"), "c");  // decided item left the list
  assert.equal(vc.afterDecision(before, [R("a"), R("b")], "c"), "b");  // last one: go back
  assert.equal(vc.afterDecision([R("a")], [], "a"), null);
});

test("highlight boxes are placed in percent of the rendered area", () => {
  assert.deepEqual(vc.boxStyle([110, 220, 160, 230], [100, 200, 300, 300]), { left: "5%", top: "20%", width: "25%", height: "10%" });
});

test("a decision needs a name; a flag also needs fields and a comment", () => {
  assert.ok(vc.decisionErrors({ status: "verified", reviewer: " " }).reviewer);
  assert.deepEqual(vc.decisionErrors({ status: "verified", reviewer: "Asha" }), {});
  assert.deepEqual(Object.keys(vc.decisionErrors({ status: "flagged", reviewer: "Asha", comment: "", fields: [] })).sort(), ["comment", "fields"]);
  assert.deepEqual(vc.decisionErrors({ status: "flagged", reviewer: "Asha", comment: "Wrong ORD", fields: ["ORD NR"] }), {});
});

test("the decision line says who decided, when, and if values changed since", () => {
  assert.equal(vc.decisionText(LIST[0]).text, "Not checked yet");
  assert.equal(vc.decisionText(LIST[1]).text, "Verified by Asha on 2026-10-14");
  assert.equal(vc.decisionText(LIST[2]).text, "Flagged by Asha on 2026-10-14: Box qty is 100");
  assert.match(vc.decisionText(LIST[3]).text, /changed since Asha verified it on 2026-10-14/);
});
