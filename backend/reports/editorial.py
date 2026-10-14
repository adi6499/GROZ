"""Editorial (source) discrepancies and the decision log -- kept separate from extraction defects.

A source discrepancy is something the printed catalogue itself is inconsistent about (e.g. its own
numerical index lists an ORD that no product page prints). It is recorded for human review; the data
is not changed to make the catalogue look consistent.
"""

import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Sequence

import pymupdf

from ..pipeline.batches import INDEX_PAGES
from ..validator.coverage import index_entries, printed_page_labels

DECISIONS_PATH = os.path.join("review", "editorial_decisions.json")


def _one_digit_apart(a: str, b: str) -> bool:
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1


def index_discrepancies(records: Sequence[Dict[str, Any]], pdf: str, pdf_root: str = ".") -> List[Dict[str, Any]]:
    """Compare a catalogue's numerical index with its product pages and the extracted records."""
    idx = INDEX_PAGES[pdf]
    with pymupdf.open(os.path.join(pdf_root, pdf)) as doc:
        entries = index_entries(doc, idx)
        label_to_phys = defaultdict(list)
        page_words = {}
        for pno in range(1, len(doc) + 1):
            if pno in idx:
                continue
            for lab in printed_page_labels(doc[pno - 1]):
                label_to_phys[lab].append(pno)
            page_words[pno] = {re.sub(r"^\D+", "", w[4]).rstrip(".,") for w in doc[pno - 1].get_text("words")}
    recs = {r["ord_nr"]: r for r in records if r["source_pdf"] == pdf and r.get("ord_nr")}
    rows = []
    # Note: index page references often point to the first page of a product family (e.g. Precision
    # TB tool bits printed on page 55 are indexed to page 54), so a page-reference difference is the
    # catalogue's convention, not a discrepancy, and is not listed.
    for o, refs in sorted(entries.items()):
        printed_on = [p for p, ws in page_words.items() if o in ws]
        if o in recs:
            continue
        rows.append({"type": "in index, not printed on any product page" if not printed_on else "in index and printed, not extracted",
                     "source_pdf": pdf, "ord_nr": o, "cat_nr": "", "index_page_ref": "/".join(refs),
                     "physical_page": "/".join(str(p) for p in sorted({p for x in refs for p in label_to_phys.get(x, [])})),
                     "printed_page": "/".join(refs), "note": ""})
    for o, r in sorted(recs.items()):
        if o not in entries:
            rows.append({"type": "printed on a product page, not in index", "source_pdf": pdf, "ord_nr": o, "cat_nr": r.get("cat_nr"),
                         "index_page_ref": "", "physical_page": r["physical_page_number"],
                         "printed_page": r.get("catalog_page_label"), "note": ""})
    # Hint (not a conclusion): an index-only ORD and a non-indexed printed ORD on the same printed page
    # that differ by one digit are probably the same product with a typo on one side.
    only_index = [x for x in rows if x["type"].startswith("in index, not printed")]
    not_indexed = [x for x in rows if x["type"].startswith("printed on a product page")]
    for a in only_index:
        for b in not_indexed:
            if str(b["printed_page"]) in a["printed_page"].split("/") and _one_digit_apart(a["ord_nr"], b["ord_nr"]):
                a["note"] = f"possibly the same product as printed {b['ord_nr']} ({b['cat_nr']}); which number is right is unknown"
                b["note"] = f"possibly the same product as index-only {a['ord_nr']}; which number is right is unknown"
    return rows


def load_decisions(path: str = DECISIONS_PATH) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)["decisions"]
