"""Printed product titles and table captions, read from the catalogue page (rules 2.2.0, decision F).

The catalogues print every product title in one dedicated type per catalogue, so the title that
belongs to a product's ordering table can be read back from the page:

1. "above":  the nearest title printed above the product's own table, in the same column (or, on a
             two-page spread, the same half of the spread).
2. "page":   a single page that prints exactly one product title, above the table (a page title
             over several side-by-side tables).
3. "spread": a two-page spread that prints exactly one product title.
4. "facing": a right-hand page that prints no title of its own continues the title printed on the
             facing left-hand page (the previous PDF page), when that page prints exactly one title.
5. "contents": (Fluid Handling CC-07 and FUEL CAT 400 only, rules 3.0.0) otherwise, the title the
             catalogue's contents page lists for the product family that starts on or before this
             printed page, when exactly one family starts there.

Anything else gets no title (the page is ambiguous). Used by the extractor (sub_title) and by the
website builder (title evidence), so both apply the same rules.

Rules 2.3.0 add the CAT NR tie-break for two titles printed side by side over one table, and
section_of_point() (which printed section a picture belongs to, for image_sections.py).
"""

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymupdf

# The type each catalogue prints its product titles in: (font name prefix, size in pt).
TITLE_TYPE: Dict[str, Tuple[str, float]] = {
    "Estwing_Hammer_E-03_Interactive_1.pdf": ("Futura-Bold", 12.0),
    "GROZ_LIGHTING_GL-10_1.pdf": ("Mont-Heavy", 16.0),
    "Precision_Catalogue_CA_03.pdf": ("Mont-Heavy", 16.0),
    "tools_storage.pdf": ("Mont-Heavy", 16.0),
    "Fluid_Handling_Catalogue_spread.pdf": ("Mont-Heavy", 16.0),
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

# Table captions: bold 8 pt in the catalogue orange, at the table's top-left corner.
CAPTION_COLOR = 0xDF4505
CAPTION_SIZE = (7.5, 8.5)
PLAIN_CAPTIONS = {"ORDERING INFORMATION"}  # carries no information about the products


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


class PageTitles:
    """Caches the title blocks of the pages of one open document."""

    def __init__(self, doc: pymupdf.Document, pdf: str):
        self.doc, self.pdf = doc, pdf
        self._pages: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}
        self._words: Dict[int, List[Any]] = {}
        self._contents: Optional[List[Dict[str, Any]]] = None

    def contents_title(self, number: int) -> Optional[Dict[str, Any]]:
        """Rule 5 ("contents"): the family the contents page lists as starting on, or most recently
        before, this page's printed number (CC-07 and FUEL CAT 400 only)."""
        from .grid_tables import CONTENTS_PAGES, contents_entries, printed_page_number
        if self.pdf not in CONTENTS_PAGES or not 1 <= number <= len(self.doc):
            return None
        if self._contents is None:
            self._contents = contents_entries(self.doc, CONTENTS_PAGES[self.pdf])
        label = printed_page_number(self.doc[number - 1])
        if not label:
            return None
        printed = int(label)
        starts = [e["page"] for e in self._contents if e["page"] <= printed]
        if not starts:
            return None
        start = max(starts)
        fams = [e for e in self._contents if e["page"] == start]
        if len(fams) != 1:
            return None  # two families start on that page: the contents cannot tell which this is
        e = fams[0]
        return {"text": e["title"], "rule": "contents", "pdf_page": e["contents_page"], "type": "contents entry",
                "block": (e["contents_page"], float(start), 0.0),
                "evidence": (f"Title the catalogue's contents lists for the product family starting on printed page "
                             f"{start} (contents on PDF page {e['contents_page']}; this is printed page {printed}).")}

    def anchor_x(self, number: int, bbox: Sequence[float], cat_nr: Optional[str]) -> Optional[float]:
        """Horizontal centre of the product's CAT NR as printed in its table (its own column)."""
        if not cat_nr or not bbox or not 1 <= number <= len(self.doc):
            return None
        if number not in self._words:
            self._words[number] = self.doc[number - 1].get_text("words")
        x0, y0, x1, y1 = bbox
        for w in self._words[number]:
            if re.sub(r"^[^0-9A-Za-z]+", "", w[4]).rstrip(".,;:") == cat_nr and x0 - 3 <= w[0] and w[2] <= x1 + 3 and y0 - 3 <= w[1] <= y1 + 3:
                return (w[0] + w[2]) / 2
        return None

    def page(self, number: int) -> Optional[Tuple[float, List[Dict[str, Any]]]]:
        if not 1 <= number <= len(self.doc):
            return None
        if number not in self._pages:
            p = self.doc[number - 1]
            self._pages[number] = (p.rect.width, title_blocks(p, self.pdf))
        return self._pages[number]

    def title_for(self, number: int, bbox: Sequence[float], page_label: Optional[str],
                  cat_nr: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """The printed title for the ordering table at `bbox` (x0, y0, x1, y1) on page `number`.

        When two titles are printed side by side at the same height above one table (two tables
        detected as one), the title over the product's own CAT NR wins (rules 2.3.0)."""
        info = self.page(number)
        if not info or not bbox:
            return None
        if self.pdf not in TITLE_TYPE:
            return self.contents_title(number)
        width, blocks = info
        bx0, by0, bx1, _ = bbox
        spread = width > SPREAD_MIN_WIDTH
        left = lambda x0, x1: (x0 + x1) / 2 < width / 2
        type_ = TITLE_TYPE[self.pdf]
        type_text = f"{type_[0]} {type_[1]:g} pt"

        def found(block, rule, page, why):
            return {"text": block["text"], "rule": rule, "pdf_page": page, "type": type_text,
                    "block": (page, round(block["x0"], 1), round(block["y0"], 1)),
                    "evidence": f"{why} (PDF page {page}, printed in the catalogue's title type {type_text})."}

        above_any = [g for g in blocks if g["y1"] <= by0 + 2]
        above = [g for g in above_any if (g["x0"] < bx1 and g["x1"] > bx0)
                 or (spread and left(g["x0"], g["x1"]) == left(bx0, bx1))]
        if above:
            best = max(above, key=lambda g: g["y1"])
            tied = [g for g in above if best["y1"] - g["y1"] < 3]
            ax = self.anchor_x(number, bbox, cat_nr) if len(tied) > 1 else None
            if ax is not None:
                best = min(tied, key=lambda g: 0 if g["x0"] <= ax <= g["x1"] else min(abs(ax - g["x0"]), abs(ax - g["x1"])))
            return found(best, "above", number, "Title printed above this product's ordering table")
        if not spread and len(blocks) == 1 and above_any:
            return found(blocks[0], "page", number, "The only product title printed on this page, above this product's ordering table")
        if spread and len(blocks) == 1:
            return found(blocks[0], "spread", number, "The only product title printed on this two-page spread")
        label = str(page_label or "")
        if not blocks and label.isdigit() and int(label) % 2 == 1 and number > 1:
            prev = self.page(number - 1)
            if prev and prev[0] <= SPREAD_MIN_WIDTH and len(prev[1]) == 1:
                return found(prev[1][0], "facing", number - 1,
                             "This right-hand page prints no title of its own; title printed on the facing page")
        return self.contents_title(number)


def section_of_point(titles: "PageTitles", number: int, x: float, y: float) -> Optional[Tuple[int, float, float]]:
    """The printed section a point belongs to: the nearest title that starts above it, preferring
    titles in the same half of the page (two-column pages and spreads). Same key as found()['block']."""
    info = titles.page(number)
    if not info:
        return None
    width, blocks = info
    above = [b for b in blocks if b["y0"] <= y]
    if not above:
        return None
    left = lambda b: (b["x0"] + b["x1"]) / 2 < width / 2
    same = [b for b in above if left(b) == (x < width / 2)]
    b = max(same or above, key=lambda b: b["y0"])
    return (number, round(b["x0"], 1), round(b["y0"], 1))


def table_caption(page: pymupdf.Page, bbox: Sequence[float]) -> Optional[str]:
    """The caption printed at the top-left of an ordering table (verbatim), unless it is the plain
    'ORDERING INFORMATION' (e.g. 'JACOBS TAPER ARBORS', 'ORDERING INFORMATION - METRIC SIZES')."""
    if not bbox:
        return None
    bx0, by0 = bbox[0], bbox[1]
    for b in page.get_text("dict", clip=pymupdf.Rect(bx0 - 20, by0 - 8, bx0 + 320, by0 + 14))["blocks"]:
        for line in b.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            s0 = spans[0]
            if not ("Bold" in s0["font"] and CAPTION_SIZE[0] <= s0["size"] <= CAPTION_SIZE[1] and s0["color"] == CAPTION_COLOR):
                continue
            if abs(line["bbox"][1] - by0) > 6 or not (bx0 - 15 <= line["bbox"][0] <= bx0 + 40):
                continue
            text = re.sub(r"\s+", " ", "".join(s["text"] for s in spans)).strip()
            return None if text in PLAIN_CAPTIONS else text
    return None


def _norm(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").replace("˚", "°")).strip().casefold()


def relation(extracted: Optional[str], printed: Optional[str]) -> str:
    """How a display title relates to an extracted heading.

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
