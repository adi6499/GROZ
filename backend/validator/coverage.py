"""Coverage and traceability gates, checked against the source PDFs.

- every 5-digit ORD number printed on a processed product page is extracted (or listed for review);
- every extracted ORD is printed on its recorded page (nothing invented);
- every extracted CAT NR is printed on its recorded page as a whole word (nothing truncated);
- where a catalogue has a numerical index, every indexed ORD is in the dataset (for a partial run,
  every ORD the index places on the printed pages that were processed).
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


def index_entries(doc: pymupdf.Document, index_pages: Iterable[int]) -> Dict[str, List[str]]:
    """Numerical index as {ORD NR: [printed page numbers]} -- each ORD is followed by its page on the same line."""
    out: Dict[str, List[str]] = defaultdict(list)
    for pno in index_pages:
        words = sorted(doc[pno - 1].get_text("words"), key=lambda w: (round(w[1]), w[0]))
        for a, b in zip(words, words[1:]):
            if re.fullmatch(r"\d{5}", a[4]) and re.fullmatch(r"\d{1,3}", b[4]) and abs(a[1] - b[1]) < 3:
                out[a[4]].append(b[4])
    return dict(out)


def printed_page_labels(page: pymupdf.Page) -> set:
    """Printed page numbers in the top/bottom margins (a two-page spread can carry two)."""
    h = page.rect.height
    return {w[4] for w in page.get_text("words") if (w[1] < 45 or w[1] > h - 45) and re.fullmatch(r"\d{1,3}", w[4])}


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
                entries = index_entries(doc, sorted(idx))
                indexed = set(entries)
                in_dataset = {r["ord_nr"] for r in records if r["source_pdf"] == pdf and r.get("ord_nr")}
                content_pages = [p for p in range(1, len(doc) + 1) if p not in idx]
                full = set(content_pages) <= set(pages)
                if full:
                    expected, scope_labels = indexed, None
                else:
                    # Partial run (e.g. a pilot): expect only the ORDs the index places on the printed
                    # pages that were processed.
                    scope_labels = set()
                    for pno in pages:
                        if pno not in idx:
                            scope_labels |= printed_page_labels(doc[pno - 1])
                    expected = {o for o, pg in entries.items() if scope_labels & set(pg)}
                idx_missing = sorted(expected - in_dataset)
                outside = {}
                if not full and idx_missing:
                    # The index cites a family's first page, so an ORD indexed to a processed page may be
                    # printed on a neighbouring page that was not processed: report it as outside scope.
                    tokens = {p: _five_digit(_printed_words(doc[p - 1])) for p in content_pages}
                    for o in idx_missing:
                        where = [p for p in content_pages if o in tokens[p]]
                        if where and not set(where) & set(pages):
                            outside[o] = where
                    idx_missing = [o for o in idx_missing if o not in outside]
                index = {
                    "index_pages": sorted(idx),
                    "scope": "whole catalogue" if full else f"printed pages {sorted(scope_labels, key=int)}",
                    "indexed": len(indexed),
                    "expected_in_scope": len(expected),
                    "missing_from_dataset": {o: printed_where.get(o, []) for o in idx_missing},
                    "index_page_refs": {o: entries[o] for o in idx_missing},
                    "indexed_here_printed_outside_scope": outside,
                    "extracted_not_in_index": sorted(in_dataset - indexed),
                }
        no_ord_unexplained = [
            (r["physical_page_number"], r.get("cat_nr")) for r in records
            if r["source_pdf"] == pdf and not r.get("ord_nr")
            and not any(n.get("field_name") == "ord_nr" for n in r.get("editorial_notes", []))
        ]
        result[pdf] = {
            "records_without_ord_unexplained": no_ord_unexplained,
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
        for pno, cat in c.get("records_without_ord_unexplained", []):
            out.append(f"{pdf} p{pno}: record {cat} has no ORD NR and no editorial note explaining why")
        if c["index"]:
            refs = c["index"].get("index_page_refs", {})
            for o, where in c["index"]["missing_from_dataset"].items():
                out.append(f"{pdf}: indexed ORD {o} (index page ref {', '.join(refs.get(o, [])) or '?'}) not in dataset "
                           f"(printed on physical pages {where or 'none'})")
    return out
