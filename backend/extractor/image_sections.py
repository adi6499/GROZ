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
5. Front view (rules 3.1.0, decision I; the lighting catalogue only): a worklight is often printed
   twice, its front (the lit face, with callouts such as "COB light", "SMD Worklight", "Top torch")
   and its back (hook, magnets, switch). A callout belongs to the picture its leader line points
   into (image_extractor "callout_text"). When the picture chosen by the rules above has no callout
   naming the light and exactly one other large picture in the product's section has one, that
   picture is the front view and is used instead. Pictures labelled with a code are never replaced;
   pages without leader lines are left as they are.
6. Facing right-hand page (rules 3.2.0; the Workshop Tools CB-05 catalogue only): a left-hand page that
   prints a product's title and table but no picture uses the only (or clearly largest) picture of the
   facing right-hand page, when that page prints no title of its own.
7. Main picture (rules 3.2.0; Workshop Tools CB-05 only): that catalogue pictures each product family large
   under its title; a smaller photo printed beside the table (the tool in use, a detail) never replaces the
   clearly largest picture of the product's section. Since rules 3.3.0 that largest picture must be printed
   above the product's table: a promotional photo printed beside the table ("Professional Quality SOCKETS",
   p139) or below it (a socket set in use, p140) is never the family's picture.
8. Views of one product (rules 3.3.0; Workshop Tools CB-05 only): when several pictures are printed
   directly above a product's table and none is clearly the largest, they show the same product from
   different sides (each socket table prints a side view and an angled view): the largest of those printed
   over the product's own table is used (a hex and a bi-hex socket table printed side by side each keep
   their own photos). This also holds on a page whose title is printed further down (p141).
10. Last resort (rules 3.3.2; Workshop Tools CB-05 only, for a product no rule above gave a picture; asked
    for by the owner on 27 Nov 2026). In this order, each recorded with its reason:
    a. variant code: the picture labelled with the product's code without its variant letter (SP/3C, a
       corrugated-base plane: the plane labelled SP/3; KIT/HKP/4L/ST: KIT/HKP/4/ST);
    b. the same set: the picture labelled for a set in the same table described the same way apart from its
       number of pieces ("5 pc Bell Type Arch Punch Set - Packed in a vinyl pouch": the 7 pc set);
    c. one table in its section: the largest picture printed anywhere in the product's section, beside its
       table too, when that table is the only one in the section (the socket merchandiser, p141; two views
       of the adjustable bevel, p230);
    d. a family continued: on a page whose title says "(continued)", the clearly largest picture of the
       family on the page where its title is printed (the hollow punch sets, p62: the hollow punch, p60);
    e. the same table: the picture labelled for another product of the same table, the one with most of the
       same printed columns ticked (the larger picture on a tie): a family picture of a related product.
    Thin tools pictured upright (at least three times as tall as wide, 3000 pt2) count as pictures printed
    above their table (the flexible extension, p144), and sets printed one under the other share the photo
    under them (socket sets on rails, p152).
9. Sets printed as tiles (rules 3.3.0; Workshop Tools CB-05 only): a set or kit printed as a tile ("HEX
   SOCKET SET / KIT/SKT/... / ORD NR. / BOX QTY.") takes the largest picture printed beside or under it,
   before the next tile of its column; a tile alone on its line may have its photo anywhere along it.

A picture is never used when it is labelled for a product outside this table, or when another
section's title is printed on or against it. Anything ambiguous stays unconfirmed.
"""

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .image_extractor import _code_in
from .printed_titles import PageTitles, section_of_point

DOMINANT = 2.0      # the largest picture must be at least this many times the area of every other
MIN_AREA = 6000     # pt²: smaller pictures are icons, badges or usage thumbnails
PAGE_SIZED = 250000  # pt²: about half an A4 page or more: a chapter divider photo (rules 3.3.0)

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


LIGHT_CALLOUT = re.compile(r"\b(COB|SMD|torch)\b", re.I)


def front_view_picture(chosen: Optional[Cand], title: Optional[Dict[str, Any]], cands: Sequence[Cand],
                       titles: PageTitles, page_number: int, own_codes: Sequence[str],
                       other_codes: Sequence[str]) -> Optional[Tuple[Cand, str]]:
    """Rule 5: the front view of a worklight when the chosen picture shows another side; else None."""
    if not title or title["rule"] == "facing" or chosen is None:
        return None
    if LIGHT_CALLOUT.search(chosen.get("callout_text") or "") or _labelled(chosen, own_codes):
        return None
    info = titles.page(page_number)
    other_blocks = [b for b in (info[1] if info else []) if b["text"] != title["text"]]
    fronts = []
    for c in cands:
        if c is chosen or c["area"] < MIN_AREA or _touches_other_title(c, other_blocks) or _labelled(c, other_codes):
            continue
        if section_of_point(titles, page_number, *_center(c)) != title["block"]:
            continue
        words = LIGHT_CALLOUT.findall(c.get("callout_text") or "")
        if words:
            fronts.append((c, words))
    if len(fronts) != 1:
        return None
    c, words = fronts[0]
    named = ", ".join(dict.fromkeys("torch" if w.lower() == "torch" else w.upper() for w in words))
    return c, (f"the front view, printed with callouts naming its light ({named}) under the title “{title['text']}”; "
               "preferred to the product's other picture, which has none")


def main_section_picture(chosen: Optional[Cand], title: Optional[Dict[str, Any]], cands: Sequence[Cand],
                         titles: PageTitles, page_number: int, other_codes: Sequence[str],
                         table_bbox: Optional[Box] = None) -> Optional[Tuple[Cand, str]]:
    """Rule 7 (rules 3.2.0; Workshop Tools CB-05 only): the catalogue pictures each product family large
    under its title; smaller photos on the page show details or the tool in use. When the picture chosen
    by the rules above is not the clearly largest picture printed in the product's section (DOMINANT), the
    clearly largest one is used. Else None (also when no picture is clearly the largest)."""
    if not title or title["rule"] not in ("above", "page") or chosen is None:
        return None
    info = titles.page(page_number)
    other_blocks = [b for b in (info[1] if info else []) if b["text"] != title["text"]]
    pics = [c for c in cands if c["area"] >= MIN_AREA and not _touches_other_title(c, other_blocks)
            and not _labelled(c, other_codes) and section_of_point(titles, page_number, *_center(c)) == title["block"]]
    best = _choose(pics)
    if best and table_bbox is not None and best[0]["rect"][3] > table_bbox[1] + 10:
        return None  # rules 3.3.0: only a picture printed above the product's table, not beside or below it
    if not best or best[0] is chosen:
        return None
    c, n = best
    return c, f"the clearly largest of {n} pictures printed under the title “{title['text']}”"


def facing_right_picture(title: Optional[Dict[str, Any]], next_cands: Sequence[Cand], titles: PageTitles,
                         page_number: int, other_codes: Sequence[str]) -> Optional[Tuple[Cand, str]]:
    """Rule 6 (rules 3.2.0; Workshop Tools CB-05 only): a left-hand page that prints a product's title
    and ordering table but no picture continues on the facing right-hand page. When that page prints no
    title of its own, its only (or clearly largest) picture not labelled for another product is the
    family's picture. Else None."""
    if not title or title["rule"] not in ("above", "page"):
        return None
    info = titles.page(page_number + 1)
    if not info or info[1]:
        return None
    # (rules 3.3.0: a picture covering most of the page is a chapter divider, never a product's photo)
    pics = [c for c in next_cands if c["area"] >= MIN_AREA and not _labelled(c, other_codes) and c["area"] < PAGE_SIZED]
    chosen = _choose(pics)
    if not chosen:
        return None
    c, n = chosen
    which = "the only picture" if n == 1 else f"the largest of {n} pictures"
    return c, (f"{which} under the title “{title['text']}”, printed on the facing right-hand page "
               f"(PDF page {page_number + 1}), which prints no title of its own")


def table_views_picture(table_bbox: Optional[Box], cands: Sequence[Cand], tables: Sequence[Box],
                        other_codes: Sequence[str]) -> Optional[Tuple[Cand, str]]:
    """Rule 8 without a title (rules 3.3.0, CB-05): the largest picture printed directly above the product's
    own table (its centre over the table, its bottom within 150 pt above the table's top, no other table in
    between), not labelled for another product. Else None."""
    if not table_bbox:
        return None
    tx0, ty0, tx1, _ = table_bbox
    pics = []
    for c in cands:
        cx, _ = _center(c)
        bottom = c["rect"][3]
        upright = c["height"] >= 3 * c["width"] and c["area"] >= 3000  # (rules 3.3.2: a thin tool pictured upright)
        if (c["area"] < MIN_AREA and not upright) or not tx0 - 5 <= cx <= tx1 + 5 or not ty0 - 150 <= bottom <= ty0 + 10 or _labelled(c, other_codes):
            continue
        if any(t is not table_bbox and t[0] <= cx <= t[2] and bottom <= t[1] < ty0 - 5 for t in tables):
            continue  # another table is printed between the picture and this one
        pics.append(c)
    if not pics:
        return None
    c = max(pics, key=lambda c: c["area"])
    which = "the only picture" if len(pics) == 1 else f"the largest of {len(pics)} pictures"
    return c, f"{which} printed directly above this product's table"


def tile_picture(tile_bbox: Box, tiles: Sequence[Box], cands: Sequence[Cand], page_width: float, page_height: float,
                 other_codes: Sequence[str]) -> Optional[Tuple[Cand, str]]:
    """Rule 9 (rules 3.3.0, CB-05): the largest picture printed beside or under a set printed as a tile, before
    the next tile of its column (a tile alone on its line: anywhere along its band). Else None."""
    x0, y0, x1, _ = tile_bbox
    same_line = [t for t in tiles if t is not tile_bbox and abs(t[1] - y0) < 6]
    below = [t[1] for t in tiles if t is not tile_bbox and t[1] > y0 + 60 and (abs(t[0] - x0) < 10 or not same_line)]
    y_end = min(below) if below else page_height - 40
    in_band = lambda c, lo, hi: (c["area"] >= 2500 and lo <= _center(c)[0] <= hi and y0 - 30 <= _center(c)[1] < y_end
                                 and not _labelled(c, other_codes))
    pics = [c for c in cands if in_band(c, x0 - 10, x1 + 10)] if same_line else [c for c in cands if in_band(c, 0, page_width)]
    if not pics and same_line:
        # tiles printed side by side with one photo to their right (a hex and a bi-hex set, p149, p151)
        right_end = max(t[2] for t in same_line + [tile_bbox])
        pics = [c for c in cands if in_band(c, right_end - 10, page_width)]
    if not pics:
        return None
    c = max(pics, key=lambda c: c["area"])
    which = "the only picture" if len(pics) == 1 else f"the largest of {len(pics)} pictures"
    return c, f"{which} printed beside or under this set, before the next set of its column"


def _set_phrase(row: Dict[str, Any]) -> str:
    """The words a set's row prints before its code and sizes, without its number of pieces."""
    text, code = row.get("source_row_text") or "", row.get("cat_nr") or ""
    i = text.find(code) if code else -1
    head = text[:i] if i > 0 else ""
    head = re.split(r'\s[\d./-]+(?:"|”)', " " + head)[0]
    head = re.sub(r"^\W*\d+\s*pcs?\b", "", head.strip(), flags=re.I)
    return " ".join(re.sub(r"[^a-z]+", " ", head.lower()).split())


def _variant_base(code: str) -> Optional[str]:
    """The code without the variant letter of its last numbered part: SP/3C -> SP/3, KIT/HKP/4L/ST ->
    KIT/HKP/4/ST, HPL/7A/BEL/ST -> HPL/7/BEL/ST. None when no part carries one."""
    parts = code.split("/")
    for k in range(len(parts) - 1, -1, -1):
        m = re.fullmatch(r"(\d+(?:\.\d+)?)([A-Z]{1,2})", parts[k])
        if m:
            return "/".join(parts[:k] + [m.group(1)] + parts[k + 1:])
    return None


def last_resort_picture(row: Dict[str, Any], rows: Sequence[Dict[str, Any]], title: Optional[Dict[str, Any]],
                        cands: Sequence[Cand], tables: Sequence[Box], titles: PageTitles, page_number: int,
                        other_codes: Sequence[str], family_cands=None) -> Optional[Tuple[Cand, str]]:
    """Rule 10 (rules 3.3.2, CB-05): a picture for a product no other rule found one for, with its reason."""
    code = row.get("cat_nr") or ""
    siblings = [r for r in rows if r is not row and r.get("table_bbox") == row.get("table_bbox") and r.get("cat_nr")]
    labelled_for = lambda c_code: [c for c in cands if _labelled(c, [c_code])]
    # a. variant code
    base = _variant_base(code)
    if base and base != code:
        pics = labelled_for(base)
        if pics:
            c = max(pics, key=lambda c: c["area"])
            return c, (f"picture labelled {base}, the same product without the variant letter of {code}; "
                       "this variant is not pictured in the catalogue")
    # b. the same set with another number of pieces
    phrase = _set_phrase(row)
    if phrase:
        for s in siblings:
            if _set_phrase(s) == phrase and labelled_for(s["cat_nr"]):
                c = max(labelled_for(s["cat_nr"]), key=lambda c: c["area"])
                return c, (f"picture labelled {s['cat_nr']}, the set printed in the same table as “{phrase}” with "
                           "another number of pieces; this set is not pictured in the catalogue")
    if title:
        info = titles.page(page_number)
        other_blocks = [b for b in (info[1] if info else []) if b["text"] != title["text"]]
        # c. the only table of its section: the section's picture, also beside the table
        in_section = lambda x, y: section_of_point(titles, page_number, x, y) == title["block"]
        own_tables = {tuple(t) for t in tables if in_section(t[0] + 10, t[1] + 10)}
        if title["rule"] in ("above", "page") and len(own_tables) == 1:
            pics = [c for c in cands if MIN_AREA <= c["area"] < PAGE_SIZED and in_section(*_center(c))
                    and not _labelled(c, other_codes) and not _touches_other_title(c, other_blocks)]
            if pics:
                c = max(pics, key=lambda c: c["area"])
                which = "the only picture" if len(pics) == 1 else f"the largest of {len(pics)} pictures (views of the same product)"
                return c, f"{which} printed in its section, under the title “{title['text']}”, whose only table is this product's"
        # d. a family continued from an earlier page
        m = re.fullmatch(r"(.+?)\s*\(continued\)", title["text"], re.I)
        if m and family_cands is not None:
            for back in range(1, 5):
                n0 = page_number - back
                info0 = titles.page(n0)
                block = next((b for b in (info0[1] if info0 else []) if b["text"] == m.group(1)), None)
                if not block:
                    continue
                key = (n0, round(block["x0"], 1), round(block["y0"], 1))
                pics = [c for c in family_cands(n0) if MIN_AREA <= c["area"] < PAGE_SIZED
                        and section_of_point(titles, n0, *_center(c)) == key and not _labelled(c, other_codes)]
                chosen = _choose(pics)
                if chosen:
                    return chosen[0], (f"the picture of the “{m.group(1)}” family on PDF page {n0}, where its title is "
                                       "printed; this product is not pictured on its own page")
                break
    # e. another product of the same table
    ticks = lambda r: {k for k, v in (r.get("column_specs") or {}).items() if v in ("Yes", "✓")}
    scored = []
    for s in siblings:
        pics = labelled_for(s["cat_nr"])
        if pics:
            c = max(pics, key=lambda c: c["area"])
            scored.append((len(ticks(row) & ticks(s)), c["area"], s["cat_nr"], c))
    if scored:
        shared, _, sib, c = max(scored, key=lambda t: (t[0], t[1]))
        why = f", with {shared} of the same printed columns ticked" if shared else ""
        return c, (f"picture labelled {sib}, another product of the same table{why} (a related product: this one "
                   "is not pictured in the catalogue)")
    return None


def section_picture(table_bbox: Optional[Box], title: Optional[Dict[str, Any]], cands: Sequence[Cand],
                    tables: Sequence[Box], titles: PageTitles, page_number: int,
                    own_codes: Sequence[str], sibling_codes: Sequence[str], other_codes: Sequence[str],
                    facing_cands: Optional[Sequence[Cand]] = None, views: bool = False) -> Optional[Tuple[Cand, str]]:
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
        if pool and views and pool is direct:
            # rule 8 (rules 3.3.0, CB-05): several views of the product printed right above its table
            own = [c for c in pool if table_bbox[0] <= _center(c)[0] <= table_bbox[2]] or pool
            c = max(own, key=lambda c: c["area"])
            return c, (f"the largest of {len(own)} pictures printed directly above this product's table "
                       f"(views of the same product), under the title “{name}”")
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
