"""Report for a batch that writes to its own folder (the Hand Tool pilot).

Everything is computed from the batch file, its manifest and the PDFs:
- every record, with missing values and ambiguity flags;
- coverage gates against the printed pages and the catalogue index (scoped to the pages processed);
- unresolved image candidates;
- counterparts: records with the same ORD NR already in the main dataset (output_v2) or the legacy
  dataset (output/), compared field by field -- never merged;
- on a re-run: additions / changes / missing records against the previous run (batches/history/).
Nothing outside `<out_dir>/reports/` and `<out_dir>/review.html` is written.
"""

import csv
import glob
import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from ..validator.coverage import coverage_problems, coverage_report
from .change_report import compare
from .summary import write_review_html

COMPARED = ("cat_nr", "dimensions_inch", "dimensions_mm", "box_qty")


def _load(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ref(r: Dict[str, Any]) -> str:
    return f'{r["source_pdf"]} p{r["physical_page_number"]} {r.get("cat_nr")}'


def counterpart_differences(rec: Dict[str, Any], other: Dict[str, Any]) -> List[str]:
    diffs = [f"{f}: {other.get(f)!r} vs {rec.get(f)!r}" for f in COMPARED if rec.get(f) != other.get(f)]
    a, b = other.get("specifications") or {}, rec.get("specifications") or {}
    diffs += [f"spec {k}: {a.get(k)!r} vs {b.get(k)!r}" for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    return diffs


def analyse(records: List[Dict[str, Any]], others: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Pure analysis (no PDFs): missing values, ambiguities, unresolved images, counterparts."""
    pilot_pdfs = {r["source_pdf"] for r in records}
    ord_count = Counter(r["ord_nr"] for r in records if r.get("ord_nr"))
    by_ord = defaultdict(list)
    by_cat = defaultdict(list)
    for label, recs in others.items():
        for o in recs:
            if o["source_pdf"] in pilot_pdfs:
                continue
            if o.get("ord_nr"):
                by_ord[o["ord_nr"]].append((label, o))
            if o.get("cat_nr"):
                by_cat[o["cat_nr"]].append((label, o))
    rows = []
    for r in records:
        missing = [f for f, v in (("ORD NR", r.get("ord_nr")), ("box qty", r.get("box_qty")),
                                   ("dimensions", r.get("dimensions_inch") or r.get("dimensions_mm")),
                                   ("image", r.get("images"))) if not v]
        ambiguous = []
        if r.get("ord_nr") and ord_count[r["ord_nr"]] > 1:
            ambiguous.append(f"ORD {r['ord_nr']} printed for {ord_count[r['ord_nr']]} pilot records")
        cps = by_ord.get(r.get("ord_nr"), [])
        if cps:
            ambiguous.append("same ORD in " + "; ".join(f"{lab}: {_ref(o)}" for lab, o in cps))
        cat_elsewhere = [(lab, o) for lab, o in by_cat.get(r.get("cat_nr"), []) if o.get("ord_nr") != r.get("ord_nr")]
        if cat_elsewhere:
            ambiguous.append("same CAT NR with another ORD in " + "; ".join(f"{lab}: {_ref(o)} ORD {o.get('ord_nr')}"
                                                                           for lab, o in cat_elsewhere))
        im = (r.get("images") or [None])[0]
        rows.append({
            "record": r,
            "missing": missing,
            "ambiguous": ambiguous,
            "image": im["association_type"] if im else "none",
            "counterparts": [(lab, o, counterpart_differences(r, o)) for lab, o in cps],
        })
    return {
        "rows": rows,
        "unresolved_images": [x for x in rows if x["image"] == "unresolved"],
        "missing_counts": Counter(m for x in rows for m in x["missing"]),
        "ambiguous": [x for x in rows if x["ambiguous"]],
        "with_counterpart": [x for x in rows if x["counterparts"]],
    }


def _previous_run(out_dir: str, name: str) -> Optional[str]:
    runs = sorted(p for p in glob.glob(os.path.join(out_dir, "batches", "history", f"{name}.*.json"))
                  if not p.endswith(".manifest.json"))
    return runs[-1] if runs else None


def write_pilot_report(out_dir: str, name: str, main_dataset: str = os.path.join("output_v2", "extracted_products.json"),
                       legacy_dataset: str = os.path.join("output", "extracted_products.json"),
                       pdf_root: str = ".") -> Dict[str, Any]:
    records = _load(os.path.join(out_dir, "batches", f"{name}.json"))
    with open(os.path.join(out_dir, "batches", f"{name}.manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    cov = coverage_report(records, manifest["pages_processed"], pdf_root)
    problems = coverage_problems(cov)
    res = analyse(records, {"output_v2": _load(main_dataset), "legacy output": _load(legacy_dataset)})
    prev_path = _previous_run(out_dir, name)
    prev = compare(_load(prev_path), records, pdf_root) if prev_path else None

    rep = os.path.join(out_dir, "reports")
    os.makedirs(rep, exist_ok=True)
    with open(os.path.join(rep, f"{name}_records.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_pdf", "physical_page", "printed_page", "cat_nr", "ord_nr", "variant_label", "box_qty",
                    "dimensions_inch", "dimensions_mm", "image_evidence", "verification_status", "missing", "ambiguous",
                    "counterpart_differences", "source_row_text"])
        for x in res["rows"]:
            r = x["record"]
            w.writerow([r["source_pdf"], r["physical_page_number"], r.get("catalog_page_label"), r.get("cat_nr"),
                        r.get("ord_nr"), (r.get("specifications") or {}).get("variant_label"), r.get("box_qty"),
                        r.get("dimensions_inch"), r.get("dimensions_mm"), x["image"], r["verification_status"],
                        "; ".join(x["missing"]), " | ".join(x["ambiguous"]),
                        " | ".join(f"{lab} {_ref(o)}: {'; '.join(d) or 'identical'}" for lab, o, d in x["counterparts"]),
                        r.get("source_row_text")])
    write_review_html(os.path.join(out_dir, "review.html"), records)

    L = [f"# Pilot report: {name}", "",
         f"- Batch file: `{out_dir}/batches/{name}.json` — {len(records)} records. Every number below is computed.",
         f"- Pipeline {manifest.get('pipeline_version')} at commit `{manifest.get('code_version')}`, "
         f"generated {manifest.get('generated_at')}, approved={manifest.get('approved')}.",
         "- Source PDFs: " + "; ".join(f"`{p}` pages {s['pages']} (sha256 {s['sha256'][:12]}…)"
                                       for p, s in manifest.get("source_pdfs", {}).items()), "",
         "## Records per page", "", "| PDF | Physical page | Printed page | Records |", "| --- | --- | --- | --- |"]
    per_page = Counter((r["source_pdf"], r["physical_page_number"], r.get("catalog_page_label")) for r in records)
    for pdf, pages in manifest["pages_processed"].items():
        for p in pages:
            n = sum(v for (a, b, _), v in per_page.items() if a == pdf and b == p)
            lab = next((c for (a, b, c) in per_page if a == pdf and b == p), "—")
            L.append(f"| {pdf} | {p} | {lab} | {n} |")
    L += ["", f"## Gates against the printed pages ({len(problems)} findings)", ""]
    for pdf, c in cov.items():
        idx = c["index"]
        L.append(f"- {pdf}: printed ORDs {c['printed_ord_tokens']}, extracted {c['extracted_ords']}; "
                 f"printed-not-extracted {sum(len(v) for v in c['printed_not_extracted'].values())}; "
                 f"extracted-not-printed {sum(len(v) for v in c['extracted_not_printed'].values())}; "
                 f"CAT NR not a printed word {len(c['cat_nr_not_printed_as_word'])}"
                 + (f"; index check ({idx['scope']}): {idx['expected_in_scope']} expected, "
                    f"{len(idx['missing_from_dataset'])} missing" if idx else ""))
    L += [f"  - {p}" for p in problems] or ["  - all gates pass"]
    mc = res["missing_counts"]
    L += ["", "## Missing values", "", f"- Records without: " + (", ".join(f"{k} {v}" for k, v in sorted(mc.items())) or "none"),
          "", "## Ambiguous matches (kept as separate records; for review)", ""]
    L += [f"- {_ref(x['record'])} ORD {x['record'].get('ord_nr')}: " + " | ".join(x["ambiguous"]) for x in res["ambiguous"]] or ["None."]
    L += ["", f"## Unresolved image candidates ({len(res['unresolved_images'])})", ""]
    L += [f"- {_ref(x['record'])}: {(x['record']['images'][0]).get('file_path')}" for x in res["unresolved_images"]] or ["None."]
    L += ["", f"## Counterparts in other datasets ({len(res['with_counterpart'])} records)", "",
          "Same ORD NR already extracted from another catalogue. Both records are kept; differences are listed (other → pilot).", ""]
    for x in res["with_counterpart"]:
        for lab, o, d in x["counterparts"]:
            L.append(f"- {_ref(x['record'])} ↔ {lab}: {_ref(o)} — " + ("; ".join(d) if d else "identical compared fields"))
    if not res["with_counterpart"]:
        L.append("None.")
    L += ["", "## Changes since the previous run", ""]
    if prev:
        L.append(f"Compared with `{os.path.relpath(prev_path)}`: {prev['pairs']} matched, {len(prev['added'])} added, "
                 f"{len(prev['missing'])} missing, {len(prev['rows'])} field changes.")
        L += [f"- {r['change']} {r['source_pdf']} p{r['page']} {r['cat_nr']}: {r['field']} {r['legacy_value']!r} → {r['new_value']!r}"
              for r in prev["rows"][:300]]
    else:
        L.append("First run: every record is an addition.")
    with open(os.path.join(rep, f"{name}_report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    return {"records": len(records), "problems": problems, **res}
