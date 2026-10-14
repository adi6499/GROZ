"""Caption and section evidence for product pictures (extraction rules 2.3.0).

Used only when a product has no picture labelled with its own code (or base model, or tripod text),
so these rules never replace stronger evidence. Every picture they choose is a `product_family`
picture: it shows the product family of the section, not necessarily this exact variant.

1. Caption: a picture printed with this product's table caption next to it ("Jacobs Taper Arbors"
   under the arbors pictured for the JACOBS TAPER ARBORS table). The table's own caption line does
   not count.
2. Section: the pictures printed in the product's own section (under its printed title, see
   printed_titles.py) above its ordering table, with no other table in between. Pictures printed
   directly above this table are preferred over pictures above no table at all. The rule applies
   when there is one such picture, or one at least twice the area of every other one.
3. Sibling label: if the section's only picture is labelled with the code of another variant
   printed in the same table, it is used as that family's picture and the evidence names the
   variant. When several variants are pictured, the product stays unconfirmed.
4. Facing page: a right-hand page that prints no title of its own and no picture for the product
   uses the section's picture on the facing page (same single/clearly-largest condition).

A picture is never used when it is labelled for a product outside this table, or when another
section's title is printed on or against it. Anything ambiguous stays unconfirmed.
"""

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .image_extractor import _code_in
from .printed_titles import PageTitles, section_of_point

DOMINANT = 2.0      # the largest picture must be at least this many times the area of every other
MIN_AREA = 6000     # pt²: smaller pictures are icons, badges or usage thumbnails

Cand = Dict[str, Any]
Box = Sequence[float]


def _compact(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _center(c: Cand) -> Tuple[float, float]:
    x0, y0, x1, y1 = c["rect"]
    return (x0 + x1) / 2, (y0 + y1) / 2


def _grow(r: Box, d: float) -> Tuple[float, float, float, float]:
    return r[0] - d, r[1] - d, r[2] + d, r[3] + d


def _intersects(a: Box, b: Box) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _phrase_boxes(words: Sequence[Any], phrase: str) -> List[Tuple[float, float, float, float]]:
    """Where `phrase` is printed on the page (consecutive words, spacing and punctuation ignored)."""
    target, out = _compact(phrase), []
    for i in range(len(words)):
        acc, j = "", i
        while j < len(words) and len(acc) < len(target):
            acc += _compact(words[j][4])
            j += 1
        if acc == target and j > i:
            ws = words[i:j]
            out.append((min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws)))
    return out


def caption_picture(cands: Sequence[Cand], table_caption: Optional[str], words: Sequence[Any],
                    table_bbox: Optional[Box]) -> Optional[Tuple[Cand, str]]:
    """A picture with this product's table caption printed on it or right next to it."""
    cap = re.sub(r"^ORDERING INFORMATION\s*-\s*", "", table_caption or "", flags=re.I).strip()
    if len(_compact(cap)) < 8 or not table_bbox:
        return None
    printed = [b for b in _phrase_boxes(words, cap)
               if not (abs(b[1] - table_bbox[1]) < 8 and table_bbox[0] - 15 <= b[0] <= table_bbox[2])]  # not the table's own caption
    # printed on the picture, beside it, or under it (captions sit up to ~30 pt below a picture)
    near = lambda r: (r[0] - 14, r[1] - 14, r[2] + 14, r[3] + 30)
    hits = [c for c in cands if c["area"] >= MIN_AREA and any(_intersects(near(c["rect"]), b) for b in printed)]
    if not hits:
        return None
    best = max(hits, key=lambda c: c["area"])
    return best, f"picture labelled “{cap}”, the caption printed on this product's table"


def _choose(pics: List[Cand]) -> Optional[Tuple[Cand, int]]:
    if not pics:
        return None
    pics = sorted(pics, key=lambda c: c["area"], reverse=True)
    if len(pics) == 1 or pics[0]["area"] >= DOMINANT * pics[1]["area"]:
        return pics[0], len(pics)
    return None


def _labelled(c: Cand, codes: Sequence[str]) -> List[str]:
    label = c.get("label_text") or ""
    return [o for o in codes if _code_in(o, label)]


def _touches_other_title(c: Cand, other_blocks: Sequence[Dict[str, Any]]) -> bool:
    """Another section's title printed on the picture or right against it (within 8 pt)."""
    x0, _, x1, _ = c["rect"]
    return any(_intersects(_grow(c["rect"], 8), (b["x0"], b["y0"], b["x1"], b["y1"]))
               and x0 <= (b["x0"] + b["x1"]) / 2 <= x1 for b in other_blocks)


def _groups(tables: Sequence[Box]) -> List[Tuple[Tuple[float, float, float, float], List[Box]]]:
    """Tables printed side by side with the same top (one table split in two columns) as one group."""
    groups: List[List[Box]] = []
    for t in sorted(tables, key=lambda t: (t[1], t[0])):
        for g in groups:
            if abs(g[0][1] - t[1]) < 2 and any(min(abs(t[0] - o[2]), abs(o[0] - t[2])) < 8 or (t[0] < o[2] and o[0] < t[2]) for o in g):
                g.append(t)
                break
        else:
            groups.append([t])
    return [((min(t[0] for t in g), min(t[1] for t in g), max(t[2] for t in g), max(t[3] for t in g)), g) for g in groups]


def section_picture(table_bbox: Optional[Box], title: Optional[Dict[str, Any]], cands: Sequence[Cand],
                    tables: Sequence[Box], titles: PageTitles, page_number: int,
                    own_codes: Sequence[str], sibling_codes: Sequence[str], other_codes: Sequence[str],
                    facing_cands: Optional[Sequence[Cand]] = None) -> Optional[Tuple[Cand, str]]:
    """The section picture for a product's table, with the evidence sentence; None if ambiguous."""
    if not title or not table_bbox:
        return None
    tx0, ty0, _, _ = table_bbox
    info = titles.page(page_number)
    other_blocks = [b for b in (info[1] if info else []) if b["text"] != title["text"]]
    name = title["text"]
    groups = _groups(tables)
    ours = lambda t: abs(t[1] - ty0) < 1 and abs(t[0] - tx0) < 1

    def right_below(c: Cand):
        """The nearest table group under the picture that it covers by at least a quarter of its width."""
        x0, _, x1, _ = c["rect"]
        _, my = _center(c)
        below = [(r, g) for r, g in groups if r[1] > my and min(x1, r[2]) - max(x0, r[0]) >= 0.25 * (x1 - x0)]
        return min(below, key=lambda rg: rg[0][1])[1] if below else None

    direct, general, sibling = [], [], []
    excluded = 0  # pictures in place but labelled for another product
    for c in cands:
        mx, my = _center(c)
        if my >= ty0 or c["area"] < MIN_AREA or _touches_other_title(c, other_blocks):
            continue
        section = section_of_point(titles, page_number, mx, my)
        if (section is not None) if title["rule"] == "facing" else (section != title["block"]):
            continue
        below = right_below(c)
        if below is not None and not any(ours(t) for t in below):
            continue  # another table is printed between this picture and the product's table
        foreign = _labelled(c, other_codes)
        if foreign and not _labelled(c, own_codes):
            if all(f in sibling_codes for f in foreign):
                sibling.append((c, foreign))
            excluded += 1
            continue
        (direct if below is not None else general).append(c)
    for pool, where in ((direct, "printed directly above this product's table"), (general, "printed in its section")):
        chosen = _choose(pool)
        if chosen:
            c, n = chosen
            which = "the only picture" if n == 1 else f"the largest of {n} pictures"
            unlabelled = " not labelled for another product" if excluded else ""
            return c, f"{which}{unlabelled} {where}, under the title “{name}”"
        if pool:
            return None  # pictures exist but none is clearly the one: stay unconfirmed
    if sibling:
        # Only when the section pictures a single variant: with several variants pictured, which
        # one an unpictured product looks like is not shown (sub-groups, different bodies).
        if len(sibling) == 1 and sibling[0][0]["area"] >= MIN_AREA:
            c, codes = sibling[0]
            return c, (f"picture labelled {', '.join(codes)}, a variant printed in the same table "
                       f"(no picture of its own), under the title “{name}”")
        return None
    if title["rule"] == "facing" and facing_cands:
        prev = page_number - 1
        pics = [c for c in facing_cands if c["area"] >= MIN_AREA and not _labelled(c, other_codes)
                and section_of_point(titles, prev, *_center(c)) == title["block"]]
        chosen = _choose(pics)
        if chosen:
            c, n = chosen
            which = "the only picture" if n == 1 else f"the largest of {n} pictures"
            return c, f"{which} under the title “{name}”, printed on the facing page (PDF page {prev})"
    return None
