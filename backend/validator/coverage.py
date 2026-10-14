"""Coverage and traceability gates, checked against the source PDFs.

- every 5-digit ORD number printed on a processed product page is extracted (or listed for review);
- every extracted ORD is printed on its recorded page (nothing invented);
- every extracted CAT NR is printed on its recorded page as a whole word (nothing truncated);
- where a catalogue has a numerical index, every indexed ORD is in the dataset.
"""

import os
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pymupdf

from ..pipeline.batches import INDEX_PAGES

_LEAD = re.compile(r"^[^A-Za-z0-9]+")


def _printed_words(page: pymupdf.Page) -> List[str]:
    return [_LEAD.sub("", w[4]).rstrip(".,;:)") for w in page.get_text("words")]


def _five_digit(words: Iterable[str]) -> set:
    return {re.sub(r"^\D+", "", w) for w in words if re.fullmatch(r"\d{5}", re.sub(r"^\D+", "", w))}


def coverage_report(records: Sequence[Dict[str, Any]], pages_by_pdf: Dict[str, Sequence[int]],
                    pdf_root: str = ".", index_pages: Optional[Dict[str, Sequence[int]]] = None) -> Dict[str, Any]:
    index_pages = INDEX_PAGES if index_pages is None else index_pages
    by_page = defaultdict(list)
    for r in records:
        by_page[(r["source_pdf"], r["physical_page_number"])].append(r)

    result: Dict[str, Any] = {}
    for pdf, pages in pages_by_pdf.items():
        idx = set(index_pages.get(pdf, ()))
        missing, phantom, cat_not_printed = {}, {}, []
        printed_total = extracted_total = 0
        printed_where = defaultdict(list)
        with pymupdf.open(os.path.join(pdf_root, pdf)) as doc:
            for pno in pages:
                words = _printed_words(doc[pno - 1])
                if pno in idx:
                    continue
                printed = _five_digit(words)
                for o in printed:
                    printed_where[o].append(pno)
                recs = by_page.get((pdf, pno), [])
                extracted = {r["ord_nr"] for r in recs if r.get("ord_nr")}
                printed_total += len(printed)
                extracted_total += len(extracted)
                if printed - extracted:
                    missing[pno] = sorted(printed - extracted)
                if extracted - printed:
                    phantom[pno] = sorted(extracted - printed)
                wordset = set(words)
                cat_not_printed += [(pno, r["cat_nr"]) for r in recs if r.get("cat_nr") and r["cat_nr"] not in wordset]
            index = None
            if idx:
                indexed = set()
                for pno in idx:
                    indexed |= _five_digit(_printed_words(doc[pno - 1]))
                in_dataset = {r["ord_nr"] for r in records if r["source_pdf"] == pdf and r.get("ord_nr")}
                index = {
                    "index_pages": sorted(idx),
                    "indexed": len(indexed),
                    "missing_from_dataset": {o: printed_where.get(o, []) for o in sorted(indexed - in_dataset)},
                    "extracted_not_in_index": sorted(in_dataset - indexed),
                }
        result[pdf] = {
            "pages_checked": len(pages),
            "printed_ord_tokens": printed_total,
            "extracted_ords": extracted_total,
            "printed_not_extracted": missing,
            "extracted_not_printed": phantom,
            "cat_nr_not_printed_as_word": cat_not_printed,
            "index": index,
        }
    return result


def coverage_problems(report: Dict[str, Any]) -> List[str]:
    """Human-readable list of gate failures (empty list = all gates pass)."""
    out = []
    for pdf, c in report.items():
        for pno, v in c["printed_not_extracted"].items():
            out.append(f"{pdf} p{pno}: printed ORD not extracted: {', '.join(v)}")
        for pno, v in c["extracted_not_printed"].items():
            out.append(f"{pdf} p{pno}: extracted ORD not printed on page: {', '.join(v)}")
        for pno, cat in c["cat_nr_not_printed_as_word"]:
            out.append(f"{pdf} p{pno}: CAT NR not printed as a whole word: {cat}")
        if c["index"]:
            for o, where in c["index"]["missing_from_dataset"].items():
                out.append(f"{pdf}: indexed ORD {o} not in dataset (printed on pages {where or 'none'})")
    return out
