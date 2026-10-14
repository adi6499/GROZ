"""Field-by-field record of what rules 2.2.0 changed in output_v2.

Run from the project root: python make_all_changes.py <output_v2 dataset before, saved from git show 36bc63a:output_v2/extracted_products.json> <this folder>
"""
import collections
import csv
import json
import sys

before_path, out_dir = sys.argv[1], sys.argv[2]
old = json.load(open(before_path, encoding="utf-8"))
new = json.load(open("output_v2/extracted_products.json", encoding="utf-8"))
key = lambda r: (r["source_pdf"], r["physical_page_number"], r.get("cat_nr"), r.get("ord_nr"))
o, n = {key(r): r for r in old}, {key(r): r for r in new}
assert len(o) == len(old) == len(n) == len(new) and set(o) == set(n), "record sets differ"

FIELD_DECISION = {
    "sub_title": "F", "specifications.table_caption": "F", "specifications.table_description": "F",
    "specifications.variant_label": "F", "specifications.diameter": "A", "dimensions_inch": "A", "dimensions_mm": "A",
    "specifications.beam_angle": "E", "specifications.net_weight": "E",
    "specifications.drawer_load_capacity": "E", "specifications.overall_load_capacity": "E",
    "confidence": "derived (score recomputed from the new specifications)",
}


def note_decision(cat):
    return "B" if cat.startswith("EMLTT") else "D" if cat.startswith("TCHL") else "A" if cat.startswith("LED/800") else "?"


def text(v):
    return "" if v is None else v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


rows = []
for k in sorted(o, key=lambda x: (x[0], x[1], str(x[2]), str(x[3]))):
    a, b = o[k], n[k]
    diffs = []
    for f in sorted(set(a) | set(b)):
        if f in ("specifications", "editorial_notes"):
            continue
        if a.get(f) != b.get(f):
            diffs.append((f, a.get(f), b.get(f)))
    sa, sb = a.get("specifications") or {}, b.get("specifications") or {}
    for s in sorted(set(sa) | set(sb)):
        if sa.get(s) != sb.get(s):
            diffs.append((f"specifications.{s}", sa.get(s), sb.get(s)))
    na = [{k2: x.get(k2) for k2 in ("field_name", "published_value", "suspected_issue")} for x in a.get("editorial_notes") or []]
    nb = [{k2: x.get(k2) for k2 in ("field_name", "published_value", "suspected_issue")} for x in b.get("editorial_notes") or []]
    if na != nb:
        diffs.append(("editorial_notes", na, nb))
    for f, before, after in diffs:
        decision = FIELD_DECISION.get(f) or (note_decision(k[2] or "") if f == "editorial_notes" else "?")
        rows.append({"source_pdf": k[0], "pdf_page": k[1], "cat_nr": k[2] or "", "ord_nr": k[3] or "", "decision": decision,
                     "field": f, "before": text(before), "after": text(after)})

with open(f"{out_dir}/all_changes.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

by = collections.Counter((r["decision"], r["field"]) for r in rows)
recs = collections.Counter(r["decision"] for r in {(r["source_pdf"], r["pdf_page"], r["cat_nr"], r["ord_nr"], r["decision"]): r for r in rows}.values())
print(f"{len(rows)} field changes in {len({(r['source_pdf'], r['pdf_page'], r['cat_nr'], r['ord_nr']) for r in rows})} records")
for (d, f), c in sorted(by.items()):
    print(f"  {d}  {f}: {c}")
print("records per decision:", dict(sorted(recs.items())))
