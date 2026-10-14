"""Printed product titles for the website, read from the catalogue PDFs. Presentation layer only.

The dataset's `sub_title` comes from a fixed banner rectangle at the top of the page, so it often
mixes the title with the first lines of description ("Tool Bits & Cut Off Blades Square Toolbits and
Cut Off Blades are"), and products lower on a page or on a facing page get another product's
heading. The catalogues print every product title in one dedicated type per catalogue, so the title
that belongs to a product's ordering table can be read back from the page:

1. "above":  the nearest title printed above the product's own table, in the same column (or, on a
             two-page spread, the same half of the spread).
2. "page":   a single page that prints exactly one product title, above the table (a page title
             over several side-by-side tables).
3. "spread": a two-page spread that prints exactly one product title.
4. "facing": a right-hand page that prints no title of its own continues the title printed on the
             facing left-hand page (the previous PDF page), when that page prints exactly one title.

Anything else gets no title (the page is ambiguous). The dataset is never modified: the display
title is stored next to the extracted heading, with the rule, page and type it came from.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

# The type each catalogue prints its product titles in: (font name prefix, size in pt).
TITLE_TYPE: Dict[str, Tuple[str, float]] = {
    "Estwing_Hammer_E-03_Interactive_1.pdf": ("Futura-Bold", 12.0),
    "GROZ_LIGHTING_GL-10_1.pdf": ("Mont-Heavy", 16.0),
    "Precision_Catalogue_CA_03.pdf": ("Mont-Heavy", 16.0),
    "tools_storage.pdf": ("Mont-Heavy", 16.0),
}
# Lighting titles have a second line printed directly below in a lighter type ("Worklight" /
# "Impact Resistant"); it is part of the printed title.
SUBTITLE_TYPE: Dict[str, Tuple[str, float]] = {
    "GROZ_LIGHTING_GL-10_1.pdf": ("Mont-Book", 14.0),
}
# Text set in a title type that is not a product title.
NOT_TITLES = {"NOTES"}

SIZE_TOLERANCE = 0.3
SPREAD_MIN_WIDTH = 900  # pt; single catalogue pages are 595 pt wide, two-page spreads about 1190 pt


def _is_type(span: Dict[str, Any], spec: Optional[Tuple[str, float]]) -> bool:
    return bool(spec) and span["font"].startswith(spec[0]) and abs(span["size"] - spec[1]) < SIZE_TOLERANCE


def title_blocks(page: pymupdf.Page, pdf: str) -> List[Dict[str, Any]]:
    """Printed product titles on a page: [{"text", "x0", "y0", "x1", "y1"}], stacked lines joined."""
    title_t, sub_t = TITLE_TYPE.get(pdf), SUBTITLE_TYPE.get(pdf)
    if not title_t:
        return []
    lines = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            kind = "title" if any(_is_type(s, title_t) for s in spans) else "sub" if any(_is_type(s, sub_t) for s in spans) else None
            if not kind:
                continue
            size = title_t[1] if kind == "title" else sub_t[1]
            # Keep every span of the line in the same size (a degree sign or apostrophe may be set
            # in another font), in reading order.
            parts = sorted((s for s in spans if abs(s["size"] - size) < SIZE_TOLERANCE), key=lambda s: s["bbox"][0])
            text = re.sub(r"\s+", " ", "".join(s["text"] for s in parts)).strip()
            if not text or text in NOT_TITLES:
                continue
            x0, y0 = min(s["bbox"][0] for s in parts), min(s["bbox"][1] for s in parts)
            x1, y1 = max(s["bbox"][2] for s in parts), max(s["bbox"][3] for s in parts)
            lines.append({"kind": kind, "text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "size": size})
    lines.sort(key=lambda l: (round(l["y0"]), l["x0"]))
    blocks: List[Dict[str, Any]] = []
    for l in lines:
        # A line continues a block when it starts at the same x and directly below it (a title may
        # wrap onto several lines; a subtitle follows its title, never the other way round).
        host = next((g for g in blocks
                     if abs(g["x0"] - l["x0"]) < 6 and -0.6 * l["size"] <= l["y0"] - g["y1"] < 0.9 * l["size"]
                     and (l["kind"] == "sub" or not g["has_sub"])), None)
        if host is None:
            if l["kind"] != "title":
                continue
            blocks.append({"text": l["text"], "x0": l["x0"], "y0": l["y0"], "x1": l["x1"], "y1": l["y1"], "has_sub": False})
        else:
            host["text"] = f'{host["text"]} {l["text"]}'
            host["x1"], host["y1"] = max(host["x1"], l["x1"]), max(host["y1"], l["y1"])
            host["has_sub"] = host["has_sub"] or l["kind"] == "sub"
    return [{k: g[k] for k in ("text", "x0", "y0", "x1", "y1")} for g in blocks]


class TitleReader:
    """Finds the printed title for a record's ordering table. Opens each PDF once."""

    def __init__(self, pdf_root: str = "."):
        self.pdf_root = pdf_root
        self._docs: Dict[str, pymupdf.Document] = {}
        self._pages: Dict[Tuple[str, int], Tuple[float, List[Dict[str, Any]]]] = {}

    def close(self) -> None:
        for d in self._docs.values():
            d.close()
        self._docs.clear()

    def _page(self, pdf: str, number: int) -> Optional[Tuple[float, List[Dict[str, Any]]]]:
        key = (pdf, number)
        if key not in self._pages:
            path = os.path.join(self.pdf_root, pdf)
            if pdf not in self._docs:
                if not os.path.isfile(path):
                    return None
                self._docs[pdf] = pymupdf.open(path)
            doc = self._docs[pdf]
            if not 1 <= number <= len(doc):
                return None
            page = doc[number - 1]
            self._pages[key] = (page.rect.width, title_blocks(page, pdf))
        return self._pages[key]

    def title_for(self, r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pdf, n, bb = r["source_pdf"], r["physical_page_number"], r.get("bounding_box")
        info = self._page(pdf, n)
        if not info or not bb:
            return None
        width, blocks = info
        spread = width > SPREAD_MIN_WIDTH
        left = lambda x0, x1: (x0 + x1) / 2 < width / 2
        type_ = TITLE_TYPE[pdf]
        type_text = f"{type_[0]} {type_[1]:g} pt"

        def found(block, rule, page, why):
            return {"text": block["text"], "rule": rule, "pdf_page": page, "type": type_text,
                    "evidence": f"{why} (PDF page {page}, printed in the catalogue's title type {type_text})."}

        above_any = [g for g in blocks if g["y1"] <= bb["y0"] + 2]
        above = [g for g in above_any if (g["x0"] < bb["x1"] and g["x1"] > bb["x0"])
                 or (spread and left(g["x0"], g["x1"]) == left(bb["x0"], bb["x1"]))]
        if above:
            return found(max(above, key=lambda g: g["y1"]), "above", n, "Title printed above this product's ordering table")
        if not spread and len(blocks) == 1 and above_any:
            return found(blocks[0], "page", n, "The only product title printed on this page, above this product's ordering table")
        if spread and len(blocks) == 1:
            return found(blocks[0], "spread", n, "The only product title printed on this two-page spread")
        label = str(r.get("catalog_page_label") or "")
        if not blocks and label.isdigit() and int(label) % 2 == 1 and n > 1:
            prev = self._page(pdf, n - 1)
            if prev and prev[0] <= SPREAD_MIN_WIDTH and len(prev[1]) == 1:
                return found(prev[1][0], "facing", n - 1,
                             "This right-hand page prints no title of its own; title printed on the facing page")
        return None


def _norm(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").replace("˚", "°")).strip().casefold()


def relation(extracted: Optional[str], printed: Optional[str]) -> str:
    """How the display title relates to the extracted heading.

    same: identical. cleaned: the extracted heading contains the printed title plus other text
    (description lines, badges). expanded: the printed title contains the extracted heading plus
    more (e.g. a subtitle line). different: neither contains the other (the extracted heading
    belongs to another product or section of the page). added: no heading was extracted.
    none: no printed title could be attributed.
    """
    if not printed:
        return "none"
    if not extracted:
        return "added"
    e, p = _norm(extracted), _norm(printed)
    if e == p:
        return "same"
    contains = lambda outer, inner: re.search(r"(?<![a-z0-9])" + re.escape(inner) + r"(?![a-z0-9])", outer) is not None
    if contains(e, p):
        return "cleaned"
    if contains(p, e):
        return "expanded"
    return "different"
