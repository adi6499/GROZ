"""Field-by-field record of what rules 2.3.1 (decision H) changed in output_v2.

Run from the project root: python make_all_changes.py <output_v2 dataset before, saved from git show 210af37:output_v2/extracted_products.json> <this folder>
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

SHOWN = ("direct_product", "product_family")


def picture(r):
    im = (r.get("images") or [None])[0]
    if not im:
        return "none", ""
    return im["association_type"], f'{im["association_type"]} {im["file_path"]} | {im["evidence"]} | strength {im["confidence"]}'


def change_kind(a, b):
    (ta, va), (tb, vb) = picture(a), picture(b)
    file_a, file_b = va.split(" | ")[0].split(" ")[-1], vb.split(" | ")[0].split(" ")[-1]
    if ta not in SHOWN and tb in SHOWN:
        return "picture added"
    if ta in SHOWN and tb not in SHOWN:
        return "picture withdrawn (labelled for another product)"
    if file_a != file_b:
        return "picture replaced" if ta in SHOWN else "candidate changed"
    if ta != tb:
        return f"same picture, evidence type {ta} -> {tb}"
    return "evidence restated (same picture)"


rows = []
for k in sorted(o, key=lambda x: (x[0], x[1], str(x[2]), str(x[3]))):
    a, b = o[k], n[k]
    for f in sorted(set(a) | set(b)):
        if a.get(f) == b.get(f):
            continue
        if f == "images":
            kind, before, after = change_kind(a, b), picture(a)[1], picture(b)[1]
        elif f == "confidence":
            kind, before, after = "derived (image evidence bonus, validator/confidence.py)", a.get(f), b.get(f)
        elif f == "sub_title":
            kind, before, after = "printed title over the product's own column (CAT NR tie-break)", a.get(f), b.get(f)
        else:
            raise SystemExit(f"unexpected field change {f} for {k}")
        rows.append({"source_pdf": k[0], "pdf_page": k[1], "cat_nr": k[2] or "", "ord_nr": k[3] or "", "decision": "H",
                     "field": f, "change": kind, "before": "" if before is None else str(before), "after": "" if after is None else str(after)})

with open(f"{out_dir}/all_changes.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

print(f"{len(rows)} field changes in {len({(r['source_pdf'], r['pdf_page'], r['cat_nr'], r['ord_nr']) for r in rows})} records")
for (f, c), m in sorted(collections.Counter((r["field"], r["change"]) for r in rows).items()):
    print(f"  {f} / {c}: {m}")
