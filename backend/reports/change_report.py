"""Compare a re-extracted dataset with the legacy dataset, field by field, and check new values in the PDFs.

Matching (legacy -> new), in order:
  1. same catalogue, page, CAT NR and ORD NR;
  2. same catalogue, page and ORD NR (catches corrected CAT NRs);
  3. same catalogue, page and CAT NR for records without an ORD NR.
Unmatched legacy records are reported as missing; unmatched new records as added.
"""

import csv
import json
import os
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymupdf

from .summary import record_key

CORE_FIELDS = ("cat_nr", "ord_nr", "box_qty", "dimensions_inch", "dimensions_mm", "verification_status",
               "catalog_page_label")
LEGACY_ASSOC = {"direct_hero": "direct_hero (legacy)", "product_family": "product_family", "secondary": "secondary (legacy)",
                "unverified": "unverified (legacy)"}


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s).replace("Î", "×").replace("Ð", "×")).strip()


class PdfEvidence:
    """Looks values up in the printed page they were extracted from."""

    def __init__(self, pdf_root: str = "."):
        self.root, self.docs, self.cache = pdf_root, {}, {}

    def page(self, pdf: str, pno: int) -> Tuple[set, str]:
        if (pdf, pno) not in self.cache:
            doc = self.docs.setdefault(pdf, pymupdf.open(os.path.join(self.root, pdf)))
            pg = doc[pno - 1]
            words = {re.sub(r"^[^A-Za-z0-9]+", "", w[4]).rstrip(".,;:)") for w in pg.get_text("words")}
            self.cache[(pdf, pno)] = (words, _norm(pg.get_text("text")))
        return self.cache[(pdf, pno)]

    def check(self, r: Dict[str, Any], field: str) -> str:
        words, text = self.page(r["source_pdf"], r["physical_page_number"])
        v = r.get(field)
        if v in (None, ""):
            return "n/a (empty)"
        if field == "cat_nr":
            return "printed as a word" if v in words else "NOT printed as a word"
        if field == "ord_nr":
            return "printed on page" if v in words else "NOT printed on page"
        if field == "box_qty":
            row = (r.get("source_row_text") or "").split()
            return "in product's table row" if str(v) in [t.strip(".,") for t in row] else "NOT in product's table row"
        if field in ("dimensions_inch", "dimensions_mm"):
            return "printed verbatim" if _norm(v) in text else "NOT printed verbatim"
        return "printed on page" if _norm(v) in text else "not found verbatim"

    def close(self) -> None:
        for d in self.docs.values():
            d.close()


def match_records(legacy: Sequence[Dict[str, Any]], new: Sequence[Dict[str, Any]]):
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any], str]] = []
    left = list(range(len(legacy)))
    right = set(range(len(new)))

    def run(keyfn, how):
        nonlocal left
        index = defaultdict(list)
        for j in sorted(right):
            k = keyfn(new[j])
            if k is not None:
                index[k].append(j)
        still = []
        for i in left:
            k = keyfn(legacy[i])
            cands = [j for j in index.get(k, []) if j in right] if k is not None else []
            if cands:
                j = cands[0]
                right.discard(j)
                pairs.append((legacy[i], new[j], how))
            else:
                still.append(i)
        left = still

    run(lambda r: (r["source_pdf"], r["physical_page_number"], r.get("cat_nr"), r.get("ord_nr")), "same CAT+ORD")
    run(lambda r: (r["source_pdf"], r["physical_page_number"], r["ord_nr"]) if r.get("ord_nr") else None, "same ORD")
    run(lambda r: (r["source_pdf"], r["physical_page_number"], r.get("cat_nr")) if not r.get("ord_nr") else None, "same CAT, no ORD")
    return pairs, [legacy[i] for i in left], [new[j] for j in sorted(right)]


def _img_sig(im: Dict[str, Any]) -> Tuple:
    b = im["bounding_box"]
    return (im["source_pdf"], im["physical_page_number"], round(b["x0"]), round(b["y0"]), round(b["x1"]), round(b["y1"]))


def compare(legacy: Sequence[Dict[str, Any]], new: Sequence[Dict[str, Any]], pdf_root: str = ".") -> Dict[str, Any]:
    ev = PdfEvidence(pdf_root)
    pairs, missing, added = match_records(legacy, new)
    rows: List[Dict[str, Any]] = []   # one row per field change (CSV)
    changed_keys: Dict[str, List[str]] = {}
    spec_changes = Counter()
    image_transitions = Counter()
    status_changes = []

    def add(kind, old, newr, field, ov, nv, check=""):
        ref = newr or old
        rows.append({
            "change": kind, "source_pdf": ref["source_pdf"], "page": ref["physical_page_number"],
            "cat_nr": (newr or {}).get("cat_nr") if newr else old.get("cat_nr"),
            "ord_nr": (newr or {}).get("ord_nr") if newr else old.get("ord_nr"),
            "legacy_cat_nr": old.get("cat_nr") if old else "", "field": field,
            "legacy_value": "" if ov is None else json.dumps(ov, ensure_ascii=False) if not isinstance(ov, str) else ov,
            "new_value": "" if nv is None else json.dumps(nv, ensure_ascii=False) if not isinstance(nv, str) else nv,
            "pdf_check": check,
        })

    for old, nr, how in pairs:
        fields = []
        for f in CORE_FIELDS:
            if old.get(f) != nr.get(f):
                fields.append(f)
                add("changed", old, nr, f, old.get(f), nr.get(f), ev.check(nr, f) if f in ("cat_nr", "ord_nr", "box_qty", "dimensions_inch", "dimensions_mm") else "")
                if f == "verification_status":
                    status_changes.append((nr["source_pdf"], nr["physical_page_number"], nr.get("cat_nr"), old.get(f), nr.get(f)))
        os_, ns = old.get("specifications") or {}, nr.get("specifications") or {}
        for k in sorted(set(os_) | set(ns)):
            if os_.get(k) != ns.get(k):
                kind = "spec removed" if k not in ns else ("spec added" if k not in os_ else "spec changed")
                spec_changes[(kind, k)] += 1
                fields.append(f"spec:{k}")
                add(kind, old, nr, f"specifications.{k}", os_.get(k), ns.get(k),
                    ev.check({**nr, "_v": ns.get(k)}, "_v") if k in ns else "")
        oi = old.get("images") or []
        ni = nr.get("images") or []
        o_t = oi[0]["association_type"] if oi else "none"
        n_t = ni[0]["association_type"] if ni else "none"
        same_crop = bool(oi and ni and _img_sig(oi[0]) == _img_sig(ni[0]))
        image_transitions[(o_t, n_t, "same crop" if same_crop else ("different crop" if oi and ni else "-"))] += 1
        if (oi or ni) and (not same_crop or o_t != n_t):
            fields.append("image")
            add("image", old, nr, "images[0]",
                f"{o_t} {oi[0]['file_path']}" if oi else None,
                f"{n_t} {ni[0]['file_path']} | {ni[0].get('evidence')}" if ni else None)
        if len(old.get("editorial_notes") or []) != len(nr.get("editorial_notes") or []):
            fields.append("editorial_notes")
            add("changed", old, nr, "editorial_notes", len(old.get("editorial_notes") or []), len(nr.get("editorial_notes") or []))
        text_changes = [f for f in ("description", "sub_title", "features") if old.get(f) != nr.get(f)]
        if text_changes:
            fields.append("text:" + "/".join(text_changes))
        if fields:
            changed_keys[record_key(nr)] = fields

    for r in added:
        changed_keys[record_key(r)] = ["new record"]
        add("added", None, r, "record", None, f"{r.get('cat_nr')} / {r.get('ord_nr')}",
            f"CAT {ev.check(r, 'cat_nr')}; ORD {ev.check(r, 'ord_nr')}")
    for r in missing:
        add("missing", r, None, "record", f"{r.get('cat_nr')} / {r.get('ord_nr')}", None)

    # Evidence checks on every new-dataset value of the core fields (not only changed ones)
    evidence = Counter()
    evidence_fail = []
    for r in new:
        for f in ("cat_nr", "ord_nr", "box_qty", "dimensions_inch", "dimensions_mm"):
            res = ev.check(r, f)
            evidence[(f, res)] += 1
            if res.startswith("NOT"):
                evidence_fail.append((r["source_pdf"], r["physical_page_number"], r.get("cat_nr"), f, r.get(f), res))
    ev.close()
    return {
        "pairs": len(pairs), "match_methods": Counter(h for _, _, h in pairs), "added": added, "missing": missing,
        "rows": rows, "changed_keys": changed_keys, "spec_changes": spec_changes, "image_transitions": image_transitions,
        "status_changes": status_changes, "evidence": evidence, "evidence_fail": evidence_fail,
        "legacy_by_pdf": Counter(r["source_pdf"] for r in legacy), "new_by_pdf": Counter(r["source_pdf"] for r in new),
    }


def _md_table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |" for r in rows]
    return "\n".join(out)


def write_change_report(out_dir: str, legacy_path: str, new_path: str, pdf_root: str = ".",
                        coverage_problems: Optional[List[str]] = None) -> Dict[str, Any]:
    with open(legacy_path, encoding="utf-8") as f:
        legacy = json.load(f)
    with open(new_path, encoding="utf-8") as f:
        new = json.load(f)
    res = compare(legacy, new, pdf_root)
    rep = os.path.join(out_dir, "reports")
    os.makedirs(rep, exist_ok=True)

    with open(os.path.join(rep, "change_report.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res["rows"][0].keys()) if res["rows"] else ["change"])
        w.writeheader()
        w.writerows(res["rows"])
    with open(os.path.join(rep, "change_report.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"changed_keys": res["changed_keys"]}, f, indent=1, ensure_ascii=False)

    by_field = defaultdict(list)
    for r in res["rows"]:
        by_field[(r["change"], r["field"])].append(r)

    L = ["# Change report: legacy dataset vs corrected re-extraction", "",
         f"- Legacy: `{os.path.relpath(legacy_path)}` ({len(legacy)} records). New: `{os.path.relpath(new_path)}` ({len(new)} records).",
         f"- Matched {res['pairs']} records ({', '.join(f'{k}: {v}' for k, v in res['match_methods'].items())}); "
         f"**{len(res['added'])} added**, **{len(res['missing'])} missing**.",
         "- Full row-by-row list: `change_report.csv` (opens in Excel). Every number below is computed.", ""]
    L += ["## 1. Records per catalogue", "",
          _md_table([[p, res["legacy_by_pdf"].get(p, 0), res["new_by_pdf"].get(p, 0),
                      res["new_by_pdf"].get(p, 0) - res["legacy_by_pdf"].get(p, 0)]
                     for p in sorted(set(res["legacy_by_pdf"]) | set(res["new_by_pdf"]))],
                    ["Catalogue", "Legacy", "New", "Difference"]), ""]
    added_by_page = Counter((r["source_pdf"], r["physical_page_number"]) for r in res["added"])
    L += ["## 2. Added records", "",
          _md_table([[p, pg, n, ", ".join(f"{r['cat_nr']}/{r['ord_nr']}" for r in res["added"]
                                         if (r["source_pdf"], r["physical_page_number"]) == (p, pg))[:160]]
                     for (p, pg), n in sorted(added_by_page.items())], ["Catalogue", "Page", "Added", "CAT/ORD (first few)"]), ""]
    L += ["## 3. Missing records (in legacy, not in new)", ""]
    L += [_md_table([[r["source_pdf"], r["physical_page_number"], r.get("cat_nr"), r.get("ord_nr")] for r in res["missing"]],
                    ["Catalogue", "Page", "CAT NR", "ORD NR"]) if res["missing"] else "None.", ""]
    for title, field in (("4. CAT NR changes", "cat_nr"), ("5. ORD NR changes", "ord_nr"), ("6. Box quantity changes", "box_qty"),
                         ("7a. Dimension (inch) changes", "dimensions_inch"), ("7b. Dimension (mm) changes", "dimensions_mm"),
                         ("8. Verification status changes", "verification_status"),
                         ("9. Printed page label changes", "catalog_page_label"),
                         ("10. Editorial note count changes", "editorial_notes")):
        items = by_field.get(("changed", field), [])
        L += [f"## {title} ({len(items)})", ""]
        if items:
            L.append(_md_table([[i["source_pdf"][:26], i["page"], i["cat_nr"], i["ord_nr"], i["legacy_value"] or "—",
                                 i["new_value"] or "—", i["pdf_check"]] for i in items],
                               ["Catalogue", "Page", "CAT NR", "ORD NR", "Legacy", "New", "New value in PDF"]))
        else:
            L.append("None.")
        L.append("")
    L += ["## 11. Specification changes (counts; every instance is in the CSV)", "",
          _md_table([[k, kind, n] for (kind, k), n in sorted(res["spec_changes"].items())], ["Spec key", "Change", "Records"]), ""]
    L += ["## 12. Image association changes (first image of each matched record)", "",
          _md_table([[a, b, c, n] for (a, b, c), n in sorted(res["image_transitions"].items(), key=lambda t: -t[1])],
                    ["Legacy type", "New type", "Crop", "Records"]), "",
          "Legacy types `direct_hero`/`product_family` were assigned partly by page position. New types: "
          "`direct_product` (own code printed beside the image), `product_family` (family/shared label or the single "
          "image beside the only table in that region), `unresolved` (page position only; a review candidate).", ""]
    L += ["## 13. PDF evidence for every value in the new dataset", "",
          _md_table([[f, r, n] for (f, r), n in sorted(res["evidence"].items())], ["Field", "Check", "Records"]), ""]
    if res["evidence_fail"]:
        L += ["Values not found as printed (need review):", "",
              _md_table([list(x) for x in res["evidence_fail"][:200]], ["Catalogue", "Page", "CAT NR", "Field", "Value", "Check"]), ""]
    if coverage_problems is not None:
        L += [f"## 14. Coverage gates on the new dataset ({len(coverage_problems)} findings)", ""]
        L += [f"- {p}" for p in coverage_problems[:200]] or ["All gates pass: every printed ORD on processed product pages "
                                                              "is extracted, every extracted ORD and CAT NR is printed on its page, "
                                                              "and every ORD in the Precision numerical index is in the dataset."]
    with open(os.path.join(rep, "change_report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    return res
