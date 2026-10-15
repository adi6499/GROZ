"""List of the picture files rules 2.3.1 re-rendered in output_v2/images (pixel size before and after).

Run from the project root: python make_picture_list.py <folder with the picture files before> <this folder>
"""
import csv
import hashlib
import json
import os
import sys

before_dir, out_dir = sys.argv[1], sys.argv[2]
records = json.load(open("output_v2/extracted_products.json", encoding="utf-8"))
shown = {}
for r in records:
    if r["images"] and r["images"][0]["association_type"] in ("direct_product", "product_family"):
        shown.setdefault(r["images"][0]["file_path"].split("/")[-1], []).append(r.get("cat_nr") or "")
md5 = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
try:
    from PIL import Image
    size = lambda p: "x".join(map(str, Image.open(p).size))
except ImportError:
    size = lambda p: ""
rows = []
for f in sorted(os.listdir("output_v2/images")):
    now, before = os.path.join("output_v2/images", f), os.path.join(before_dir, f)
    if not os.path.exists(before):
        state = "new"
    elif md5(before) == md5(now):
        state = "unchanged (no longer extracted: decoration)"
    else:
        state = "re-rendered"
    rows.append({"file": f, "state": state, "size_before": size(before) if os.path.exists(before) else "",
                 "size_after": size(now), "shown_for": len(shown.get(f, [])), "example_cat_nr": (shown.get(f) or [""])[0]})
with open(os.path.join(out_dir, "pictures.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
from collections import Counter
print(len(rows), "files:", dict(Counter(r["state"] for r in rows)), "| shown:", sum(1 for r in rows if r["shown_for"]))
