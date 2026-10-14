"""Printed product titles for the website, with the evidence of where each was read.

The rules live in `backend/extractor/printed_titles.py` (extraction rules 2.2.0, decision F), so
the extractor's `sub_title` and the website's title evidence always agree. This module opens the
catalogue PDFs by path for the site builder.
"""

import os
from typing import Any, Dict, Optional

import pymupdf

from ..extractor.printed_titles import (NOT_TITLES, SPREAD_MIN_WIDTH, SUBTITLE_TYPE, TITLE_TYPE,  # noqa: F401
                                        PageTitles, relation, title_blocks)


class TitleReader:
    """Finds the printed title for a record's ordering table. Opens each PDF once."""

    def __init__(self, pdf_root: str = "."):
        self.pdf_root = pdf_root
        self._docs: Dict[str, pymupdf.Document] = {}
        self._titles: Dict[str, PageTitles] = {}

    def close(self) -> None:
        for d in self._docs.values():
            d.close()
        self._docs.clear()
        self._titles.clear()

    def _for(self, pdf: str) -> Optional[PageTitles]:
        if pdf not in self._titles:
            path = os.path.join(self.pdf_root, pdf)
            if not os.path.isfile(path):
                return None
            self._docs[pdf] = pymupdf.open(path)
            self._titles[pdf] = PageTitles(self._docs[pdf], pdf)
        return self._titles[pdf]

    def title_for(self, r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        titles = self._for(r["source_pdf"])
        bb = r.get("bounding_box")
        if not titles or not bb:
            return None
        return titles.title_for(r["physical_page_number"], (bb["x0"], bb["y0"], bb["x1"], bb["y1"]), r.get("catalog_page_label"))
