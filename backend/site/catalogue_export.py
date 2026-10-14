"""Build the website's catalogue data from the extraction dataset.

Read-only with respect to the dataset: `output_v2/extracted_products.json` is never modified. The
output (`site/data/catalogue.json`) is a presentation view of the same records:

- Every value comes from the record. Nothing is filled in; absent fields are simply absent.
- Category and brand are catalogue-level facts (which PDF a record was extracted from).
- Only images whose association is `direct_product` or `product_family` are shown; `unresolved`
  candidates are never presented as a product's image.
- Fields that a pending, not-yet-approved extraction-rule correction would change (listed in
  `review/preview_*.csv`) are withheld and marked "under review" instead of showing a value that is
  known to be in question. Formatting-only differences (e.g. ° vs ˚) are not withheld.
- Verification status and editorial review notes are passed through unchanged.
- Each product's display title is the title printed for its ordering table, read from the PDF in the
  catalogue's title type (`backend/site/titles.py`), with the rule and page it came from. The
  extracted heading (`sub_title`) is kept alongside it, and every difference between the two is
  listed in `review/display_titles.csv`.
"""

import csv
import glob
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..review import verification
from .titles import TitleReader, relation

DATASET = os.path.join("output_v2", "extracted_products.json")
SITE_DATA = os.path.join("site", "data", "catalogue.json")
PREVIEW_GLOB = os.path.join("review", "preview_*.csv")
TITLE_REVIEW = os.path.join("review", "display_titles.csv")

# Catalogue-level facts: which category a catalogue covers and whose brand it carries.
CATALOGUES: Dict[str, Dict[str, str]] = {
    "Estwing_Hammer_E-03_Interactive_1.pdf": {
        "category": "Striking Tools", "brand": "Estwing", "title": "Estwing Hammers E-03",
        "art": "sledge", "blurb": "Sledgehammers, mallets, axes & bars"},
    "GROZ_LIGHTING_GL-10_1.pdf": {
        "category": "LED Worklights", "brand": "GROZ", "title": "GROZ Lighting GL-10",
        "art": "light", "blurb": "Worklights, floodlights & inspection lamps"},
    "Precision_Catalogue_CA_03.pdf": {
        "category": "Precision Tools", "brand": "GROZ", "title": "GROZ Precision CA-03",
        "art": "measure", "blurb": "Measuring tools & machine accessories"},
    "tools_storage.pdf": {
        "category": "Tool Storage", "brand": "GROZ", "title": "GROZ Tool Storage",
        "art": "storage", "blurb": "Cabinets, tool boxes & workbenches"},
}
CATALOGUE_ORDER = ("tools_storage.pdf", "GROZ_LIGHTING_GL-10_1.pdf", "Estwing_Hammer_E-03_Interactive_1.pdf",
                   "Precision_Catalogue_CA_03.pdf")

SPEC_LABELS: Dict[str, str] = {
    "variant_label": "Variant (printed column)",
    "table_description": "Description (printed in table)",
    "table_caption": "Table caption (printed)",
    "diameter": "Diameter",
    "lumens": "Light output (lumens)", "beam_distance": "Beam distance", "beam_angle": "Beam angle",
    "run_time": "Run time", "battery": "Battery", "led_type": "LED type", "ip_rating": "IP rating",
    "ik_rating": "IK rating", "plug_type": "Plug type", "power_source": "Power source",
    "overall_load_capacity": "Overall load capacity", "drawer_load_capacity": "Drawer load capacity",
    "net_weight": "Net weight", "steel_gauge": "Steel gauge", "series": "Series",
    "no_of_drawers": "Number of drawers", "top_options": "Top option", "colour": "Colour",
    "head_weight": "Head weight", "weight": "Weight", "overall_length": "Overall length", "length": "Length",
    "handle_length": "Handle length", "spring_steel_bars": "Spring steel bars",
}
SPEC_ORDER = list(SPEC_LABELS)

EVIDENCE_LABELS = {
    "direct_product": "Catalogue image labelled with this product's code",
    "product_family": "Product-family image (shared by related variants)",
}
STATUS_LABELS = {
    "verified": "Verified",
    "unverified": "Not yet verified",
    "needs_review": "Needs review",
}


def spec_label(key: str) -> str:
    return SPEC_LABELS.get(key, key.replace("_", " ").capitalize())


def record_id(r: Dict[str, Any]) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(r["source_pdf"])[0].lower()).strip("-")
    code = re.sub(r"[^A-Za-z0-9]+", "-", r.get("cat_nr") or "na").strip("-")
    return f"{stem}-p{r['physical_page_number']}-{code}-{r.get('ord_nr') or 'na'}"


def heading_text(r: Dict[str, Any]) -> Optional[str]:
    """The catalogue heading printed with the product, verbatim (whitespace collapsed).

    Estwing headings are followed by a bullet list on the same line ("SLEDGE HAMMERS • Forged ..."):
    only the part before the first bullet is the heading.
    """
    t = re.sub(r"\s+", " ", r.get("sub_title") or "").strip()
    if not t:
        return None
    if r["source_pdf"].startswith("Estwing"):
        t = t.split("•")[0].strip(" -–")
    return t or None


def _same_ignoring_format(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"\s+", " ", (s or "").replace("˚", "°")).strip()
    return norm(a) == norm(b)


def load_pending_corrections(pattern: str = PREVIEW_GLOB) -> Dict[Tuple[str, int, str, str], str]:
    """Fields a not-yet-applied extraction-rule correction would change: {(pdf, page, cat_nr, key): file}."""
    out = {}
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                field = row.get("field") or ""
                if not field.startswith("specifications.") or row.get("change") not in ("spec changed", "spec removed"):
                    continue
                if row["change"] == "spec changed" and _same_ignoring_format(row["legacy_value"], row["new_value"]):
                    continue
                key = (row["source_pdf"], int(row["page"]), row["cat_nr"], field.split(".", 1)[1])
                out[key] = os.path.basename(path)
    return out


def _image(r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for im in r.get("images") or []:
        if im.get("association_type") in EVIDENCE_LABELS:
            return {
                "src": "../output_v2/" + im["file_path"].replace("\\", "/"),
                "evidence": im["association_type"],
                "evidence_label": EVIDENCE_LABELS[im["association_type"]],
                "evidence_detail": im.get("evidence"),
            }
    return None


def _review_overlay(r: Dict[str, Any], decision: Tuple[Optional[str], Optional[Dict[str, Any]]]):
    """Status, status label, extra notes and verification info from a person's decision.

    Verified: only while the values still match the verified fingerprint. Flagged: needs review,
    with the reviewer's comment as a note. Stale or no decision: the dataset's own status."""
    state, entry = decision
    status = r["verification_status"]
    extra_notes: List[Dict[str, Any]] = []
    info = None
    if state in ("verified", "flagged"):
        info = {"state": state, "reviewer": entry["reviewer"], "at": entry["at"]}
        if state == "verified":
            status = "verified"
        else:
            status = "needs_review"
            extra_notes.append({"field": ", ".join(entry.get("fields") or []) or "record", "published_value": "",
                                "issue": f"Flagged by {entry['reviewer']} on {entry['at'][:10]}: {entry.get('comment', '')}",
                                "status": "flagged by reviewer"})
    return status, STATUS_LABELS.get(status, status), extra_notes, info


def export_record(r: Dict[str, Any], pending: Dict[Tuple[str, int, str, str], str],
                  printed_title: Optional[Dict[str, Any]] = None,
                  decision: Tuple[Optional[str], Optional[Dict[str, Any]]] = (None, None)) -> Dict[str, Any]:
    cat = CATALOGUES.get(r["source_pdf"], {"category": "Other", "brand": "", "title": r["source_pdf"], "art": "tool"})
    status, status_label, review_notes, verified_info = _review_overlay(r, decision)
    specs_in = r.get("specifications") or {}
    specs, under_review = [], []
    for key in sorted(specs_in, key=lambda k: (SPEC_ORDER.index(k) if k in SPEC_ORDER else len(SPEC_ORDER), k)):
        value = specs_in[key]
        if value is None or value == "":
            continue
        if (r["source_pdf"], r["physical_page_number"], r.get("cat_nr"), key) in pending:
            under_review.append({"key": key, "label": spec_label(key)})
            continue
        specs.append({"key": key, "label": spec_label(key), "value": str(value)})
    # Fields being removed by a pending correction (present in the dataset, value withheld above) are
    # listed as under review; fields a correction would add are not shown (not in the dataset).
    image = _image(r)
    unresolved = any(im.get("association_type") == "unresolved" for im in r.get("images") or [])
    return {
        "id": record_id(r),
        "cat_nr": r.get("cat_nr"),
        "ord_nr": r.get("ord_nr"),
        "model_code": r.get("product_name"),
        "title": printed_title["text"] if printed_title else None,
        "title_source": {k: printed_title[k] for k in ("rule", "pdf_page", "evidence")} if printed_title else None,
        "heading": heading_text(r),
        "heading_relation": relation(r.get("sub_title"), printed_title["text"] if printed_title else None),
        "category": cat["category"],
        "brand": cat["brand"],
        "catalogue": {"pdf": r["source_pdf"], "title": cat["title"], "href": f"../{r['source_pdf']}#page={r['physical_page_number']}"},
        "page": r["physical_page_number"],
        "printed_page": r.get("catalog_page_label"),
        "dimensions_inch": r.get("dimensions_inch"),
        "dimensions_mm": r.get("dimensions_mm"),
        "box_qty": r.get("box_qty"),
        "specs": specs,
        "under_review": under_review,
        "image": image,
        "image_candidate_unconfirmed": image is None and unresolved,
        "status": status,
        "status_label": status_label,
        "verification": verified_info,
        "notes": [{"field": n.get("field_name"), "published_value": n.get("published_value"),
                   "issue": n.get("suspected_issue"), "status": n.get("review_status")}
                  for n in r.get("editorial_notes") or []] + review_notes,
        "source_row_text": r.get("source_row_text"),
    }


def build(dataset_path: str = DATASET, preview_glob: str = PREVIEW_GLOB, pdf_root: str = ".",
          ledger_path: str = verification.LEDGER) -> Dict[str, Any]:
    with open(dataset_path, "rb") as f:
        raw = f.read()
    records = json.loads(raw.decode("utf-8"))
    pending = load_pending_corrections(preview_glob)
    ledger = verification.load_ledger(ledger_path)
    reader = TitleReader(pdf_root)
    try:
        items = [export_record(r, pending, reader.title_for(r), verification.state_for(ledger, record_id(r), r))
                 for r in records]
    finally:
        reader.close()
    review_counts = verification.summary(ledger, [(record_id(r), r) for r in records])
    ids = Counter(i["id"] for i in items)
    duplicates = [k for k, n in ids.items() if n > 1]
    if duplicates:
        raise ValueError(f"Record ids are not unique: {duplicates[:5]}")
    by_cat = Counter(i["category"] for i in items)
    catalogues = []
    for pdf in CATALOGUE_ORDER:
        if pdf in CATALOGUES:
            c = CATALOGUES[pdf]
            catalogues.append({"pdf": pdf, "href": f"../{pdf}", **c,
                               "records": sum(1 for i in items if i["catalogue"]["pdf"] == pdf)})
    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataset": dataset_path.replace("\\", "/"),
            "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "records": len(items),
            "verified": sum(1 for i in items if i["status"] == "verified"),
            "flagged_by_reviewer": review_counts["flagged"],
            "verification_stale": review_counts["stale"],
            "fields_under_review": sum(len(i["under_review"]) for i in items),
            "pending_correction_files": sorted({v for v in pending.values()}),
            "with_confirmed_image": sum(1 for i in items if i["image"]),
            "titles_by_rule": dict(sorted(Counter((i["title_source"] or {}).get("rule", "none") for i in items).items())),
            "heading_relations": dict(sorted(Counter(i["heading_relation"] for i in items).items())),
        },
        "categories": [{"name": c["category"], "art": c["art"], "blurb": c["blurb"], "records": by_cat[c["category"]]}
                       for c in catalogues],
        "catalogues": catalogues,
        "products": items,
    }


def write(data: Dict[str, Any], path: str = SITE_DATA) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


TITLE_REVIEW_COLUMNS = ["source_pdf", "pdf_page", "printed_page", "cat_nr", "ord_nr", "relation",
                        "extracted_heading", "display_title", "title_rule", "title_pdf_page", "evidence"]


def title_review_rows(data: Dict[str, Any], dataset_path: str = DATASET) -> List[Dict[str, Any]]:
    """Every product whose display title is not identical to its extracted heading (for review)."""
    with open(dataset_path, encoding="utf-8") as f:
        raw_heading = {record_id(r): r.get("sub_title") for r in json.load(f)}
    rows = []
    for p in data["products"]:
        if p["heading_relation"] == "same":
            continue
        src = p["title_source"] or {}
        rows.append({"source_pdf": p["catalogue"]["pdf"], "pdf_page": p["page"], "printed_page": p["printed_page"] or "",
                     "cat_nr": p["cat_nr"] or "", "ord_nr": p["ord_nr"] or "", "relation": p["heading_relation"],
                     "extracted_heading": raw_heading.get(p["id"]) or "", "display_title": p["title"] or "",
                     "title_rule": src.get("rule", ""), "title_pdf_page": src.get("pdf_page", ""),
                     "evidence": src.get("evidence", "")})
    return rows


def write_title_review(data: Dict[str, Any], path: str = TITLE_REVIEW, dataset_path: str = DATASET) -> int:
    rows = title_review_rows(data, dataset_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TITLE_REVIEW_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    return len(rows)
