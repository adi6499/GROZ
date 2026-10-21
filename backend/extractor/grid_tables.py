"""Ordering tables of the Fluid Handling CC-07 and FUEL CAT 400 catalogues (rules 3.0.0, batch_3_fluid).

These catalogues print every product's values in columns under a header of up to four lines:
CAT NR. / ORD NR. pairs (two pairs side by side for the BSP and NPT thread variants of one product),
then shared columns such as THREADS, MAX. PRESSURE (PSI) (BAR), FLOW RATE, BOX QTY. This reader keeps
the table exactly as printed:

- one record per printed CAT NR. (a "-" in a CAT column is no product); best-seller and new-product
  marks printed before a code are not part of it;
- the ORD NR. printed in the same row, in the paired ORD column (FUEL CAT 400 prints "ORDERING #");
- every shared column's cell, verbatim, as a specification named after its printed header: the
  column's header words from top to bottom, e.g. "MAX. PRESSURE (PSI)". Cells printed "-" are left out;
- BOX QTY. as the box quantity, SIZE / DIMENSION (INCH) and (MM) cells as the dimensions, and the
  DESCRIPTION cell as the row description;
- labels printed under a CAT/ORD pair (e.g. "BSP THREADS", "6" (150 MM) STEEL EXTENSION & COUPLER") as
  the row's variant label, and section rows printed across the table (e.g. "ALUMINUM DIE CAST HEAD") as
  the table section of the rows below them.

Nothing is read from outside the table's columns: a table ends at its BOX QTY. column (or its last
header word), so feature text printed beside a table is never taken for a cell.
"""

import re
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

GLYPH = re.compile(r"^[^A-Za-z0-9\-]+")  # best-seller / new-product marks printed before a code
ORD_WORD = re.compile(r"^\d{5}$")
DASHES = {"-", "–", "—"}
HEADER_TOKENS = {"CAT", "NR", "NO", "ORD", "ORDERING", "#"}
ROW_PITCH_MIN = 12.0


def _hdr(t: str) -> str:
    return t.upper().strip(".:|")


def _clean(t: str) -> str:
    """A printed word without the marks around it: best-seller / new glyphs before it, and punctuation
    or a footnote star after it ("M15/BS/R*" refers to a note under the table)."""
    return GLYPH.sub("", t).rstrip(".,;:*")


def _cx(w) -> float:
    return (w[0] + w[2]) / 2.0


def code_of(token: str) -> Optional[str]:
    """A catalogue code printed as one word: capitals and digits with / - . (e.g. G1R/HD/B, R13604,
    FPM-12, DMK/EDP). A plain number is an order number, not a code."""
    t = _clean(token)
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9/\-.()]*", t) or not re.search(r"[A-Z]", t):
        return None
    if not (re.search(r"\d", t) or re.search(r"[/\-]", t)):
        return None
    return t


def _lines(words: List[Any], tol: float = 3.5) -> List[List[Any]]:
    out: List[List[Any]] = []
    for w in sorted(words, key=lambda w: (w[1], w[0])):
        if out and abs(out[-1][0][1] - w[1]) < tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(l, key=lambda w: w[0]) for l in out]


def _phrases(line: List[Any], gap: float = 6.5) -> List[Dict[str, Any]]:
    """Words of one line joined into phrases (a header cell, a label) where they nearly touch. Two unit
    sub-headers printed side by side ("(INCH) (MM)") stay separate: each heads its own column."""
    out: List[Dict[str, Any]] = []
    for w in line:
        units = out and out[-1]["words"][-1][4].endswith(")") and w[4].startswith("(")
        if out and w[0] - out[-1]["x1"] <= gap and not units:
            p = out[-1]
            p["words"].append(w)
            p["x1"] = max(p["x1"], w[2])
        else:
            out.append({"words": [w], "x0": w[0], "x1": w[2], "y": w[1]})
    for p in out:
        p["text"] = " ".join(w[4] for w in p["words"])
        p["cx"] = (p["x0"] + p["x1"]) / 2.0
    return out


def _cell_text(words: List[Any]) -> str:
    text = " ".join(" ".join(w[4] for w in l) for l in _lines(words))
    return re.sub(r"\s+", " ", text).strip()


def _key(label: str) -> str:
    return re.sub(r"\s+", "_", label.strip().lower())


# ---------------------------------------------------------------------------------------------------------
def _header_cats(words: List[Any]) -> List[Any]:
    """CAT header words with an ORD (or ORDERING #) header beside them on the same line, or with "NR."
    under them when another CAT header shares the line (a table whose header omits the ORD column)."""
    out = []
    for w in words:
        if _hdr(w[4]) != "CAT":
            continue
        if any(_hdr(o[4]) in ("ORD", "ORDERING") and 0 < o[0] - w[0] < 170 and abs(o[1] - w[1]) < 6 for o in words):
            out.append(w)
        elif (any(_hdr(o[4]) == "NR" and abs(o[0] - w[0]) < 8 and 4 < o[1] - w[1] < 14 for o in words)
              and any(o is not w and _hdr(o[4]) == "CAT" and abs(o[1] - w[1]) < 3 for o in words)):
            out.append(w)
    return out


def _blocks(words: List[Any], cats: List[Any], page_width: float, all_cats: List[Any]) -> List[Dict[str, Any]]:
    """Split one header line into tables. A CAT/ORD pair "owns" columns when other header words follow
    its ORD before the next CAT; pairs without columns of their own share those of the next pair. A
    table's columns stop at the next table's CAT header to its right (even one printed a little lower)."""
    cats = sorted(cats, key=lambda w: w[0])
    hy = min(c[1] for c in cats)
    zone = [w for w in words if hy - 8 <= w[1] <= hy + 14]  # an ORD header may sit a little higher (FUEL p27)
    groups = []
    for i, c in enumerate(cats):
        beside = [o[0] for o in all_cats if o[0] > c[0] + 10 and abs(o[1] - hy) < 20]
        nxt = cats[i + 1][0] if i + 1 < len(cats) else min([page_width] + beside)
        ords = [w for w in zone if _hdr(w[4]) in ("ORD", "ORDERING") and c[0] < w[0] < nxt - 10]
        ord_w = min(ords, key=lambda w: w[0]) if ords else None
        after = ord_w[2] if ord_w else c[2]
        own = [w for w in zone if after + 2 < w[0] < nxt - 10 and _hdr(w[4]) not in HEADER_TOKENS]
        groups.append({"cat": c, "ord": ord_w, "own": own})
    blocks, cur = [], []
    for g in groups:
        cur.append(g)
        if g["own"]:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        own = b[-1]["own"]
        box = [w for w in own if _hdr(w[4]) == "BOX"]
        if box:
            right = max(w[2] for w in box) + 12  # BOX QTY. is the last column; its numbers sit under it
        else:
            # without a BOX QTY. column: up to the last header word that still belongs to the table
            # (header words follow each other at column spacing; feature text further right does not)
            last = b[-1]["ord"][2] if b[-1]["ord"] else b[-1]["cat"][2]
            for w in sorted(own, key=lambda w: w[0]):
                if w[0] - last > 60:
                    break
                last = max(last, w[2])
            right = last + 22
        out.append({"groups": b, "hy": hy, "cat0": b[0]["cat"][0], "x_end": min(right, page_width - 8)})
    return out


def _bound(blocks: List[Dict[str, Any]], page_width: float) -> None:
    """Each table's horizontal extent and column ranges. Tables printed side by side (on the same header
    line or a little lower) never reach into each other: a table starts where the one to its left ends."""
    side = lambda a, b: abs(a["hy"] - b["hy"]) < 60  # header lines at about the same height
    for b in blocks:
        b["own_end"] = b["x_end"]
    for b in blocks:
        left = [o["own_end"] for o in blocks if o is not b and side(o, b) and o["own_end"] <= b["cat0"]]
        # Codes are printed left-aligned under a centred CAT header: the first pair's code column starts
        # at the table's left edge (up to 60 pt left of its header, never inside the table to its left).
        b["x_start"] = max([b["cat0"] - 60] + left)
    for b in blocks:
        nxt = [o["x_start"] for o in blocks if o is not b and side(o, b) and o["cat0"] >= b["own_end"] - 30]
        b["x_end"] = min([b["x_end"]] + [max(x, b["cat0"] + 40) for x in nxt])
        groups = b["groups"]
        last = groups[-1]
        # The shared columns start right after the last ORD column (their unit sub-headers, e.g. "(INCH)",
        # may be printed left of the column's first header word).
        own = last["own"]
        if last["ord"]:
            b["shared_x0"] = last["ord"][2] + 6
        else:  # no ORD column: halfway between the last CAT header and the first value column header
            b["shared_x0"] = (last["cat"][2] + 20 + min((w[0] for w in own), default=b["x_end"])) / 2
        for gi, g in enumerate(groups):
            g["cat_lo"] = b["x_start"] if gi == 0 else (groups[gi - 1]["ord"][2] + 4 if groups[gi - 1]["ord"] else g["cat"][0] - 30)
        for gi, g in enumerate(groups):
            nxt_cat = groups[gi + 1]["cat_lo"] if gi + 1 < len(groups) else b["shared_x0"]
            g["cat_hi"] = (g["ord"][0] - 3) if g["ord"] else nxt_cat
            g["ord_lo"] = (g["ord"][0] - 16) if g["ord"] else None
            g["ord_hi"] = nxt_cat


def _leaf_columns(header_words: List[Any]) -> List[Dict[str, Any]]:
    """The printed columns of the shared part of a table, each labelled with its header words from top
    to bottom ("MAX." / "PRESSURE" / "(PSI)" -> "MAX. PRESSURE (PSI)").

    1. Header words stacked directly under each other (centred on the same point, e.g. "INLET /",
       "OUTLET", "THREADS") are one header cell.
    2. A cell that starts lower down belongs to the cell above it whose width covers it (18 pt either
       side): the lowest such cell, then the nearest by centre. Units under a column ("(INCH)" "(MM)"),
       or a sub-column ("O.D. STEEL END" under "FOLLOWER PLATE DIMENSIONS").
    3. Cells with nothing under them are the columns.
    """
    lines = [_phrases(l) for l in _lines(header_words)]
    if not lines:
        return []
    unit = lambda p: bool(re.fullmatch(r"\([^()]{1,10}\)\**|LPM|GPM|CFM|M|FEET|MM|INCH|KGS?|LBS?\.?|OZ\.?|ML|GMS|PSI|BAR",
                                       p["text"]))
    for k in range(len(lines) - 1):
        below = lines[k + 1]
        if lines[k] and all(unit(p) for p in lines[k]) and any(
                not unit(q) and sum(1 for p in lines[k] if q["x0"] - 15 <= p["cx"] <= q["x1"] + 15) >= 2 for q in below):
            # Column names printed below their unit sub-headers (e.g. "(INCH) (MM)" over "RIGID"): which
            # column a value belongs to cannot be read reliably, so no column of this table is labelled.
            raise ValueError("units printed above the column names")
    cells: List[Dict[str, Any]] = []
    for li, ps in enumerate(lines):
        for p in ps:
            stack = [c for c in cells if c["last_li"] == li - 1 and abs(c["last_cx"] - p["cx"]) <= 9]
            if stack:
                c = min(stack, key=lambda c: abs(c["last_cx"] - p["cx"]))
                c["parts"].append(p["text"])
                c["x0"], c["x1"] = min(c["x0"], p["x0"]), max(c["x1"], p["x1"])
                c["last_li"], c["last_cx"] = li, p["cx"]
            else:
                cells.append({"parts": [p["text"]], "x0": p["x0"], "x1": p["x1"], "top": li, "last_li": li,
                              "last_cx": p["cx"], "parent": None, "kids": 0})
    for c in cells:
        c["cx"] = (c["x0"] + c["x1"]) / 2
    for c in cells:
        above = [o for o in cells if o is not c and o["top"] < c["top"] and o["last_li"] < c["top"]]
        cover = [o for o in above if o["x0"] - 18 <= c["cx"] <= o["x1"] + 18]
        near = [o for o in above if abs(o["cx"] - c["cx"]) <= 45]
        # the most specific (lowest) cell that covers it, then the nearest by centre
        if cover:
            pick = min(cover, key=lambda o: (-o["top"], abs(o["cx"] - c["cx"])))
        else:
            pick = min(near, key=lambda o: abs(o["cx"] - c["cx"])) if near else None
        if pick is not None:
            c["parent"] = pick
            pick["kids"] += 1
    leaves = []
    for c in cells:
        if c["kids"]:
            continue
        chain, cur = [], c
        while cur is not None:
            chain.append(" ".join(cur["parts"]))
            cur = cur["parent"]
        leaves.append({"label": re.sub(r"\s+", " ", " ".join(reversed(chain))).strip(),
                       "x0": c["x0"], "x1": c["x1"], "cx": c["cx"]})
    leaves.sort(key=lambda c: c["cx"])
    for i, c in enumerate(leaves):
        left = leaves[i - 1] if i else None
        right = leaves[i + 1] if i + 1 < len(leaves) else None
        c["lo"] = ((left["x1"] + c["x0"]) / 2 if left["x1"] < c["x0"] else (left["cx"] + c["cx"]) / 2) if left else -1e9
        c["hi"] = ((c["x1"] + right["x0"]) / 2 if c["x1"] < right["x0"] else (c["cx"] + right["cx"]) / 2) if right else 1e9
    return leaves


def _norm_label(label: str) -> str:
    return re.sub(r"[^A-Z]", "", label.upper())


def extract_grid_rows(page: pymupdf.Page) -> List[Dict[str, Any]]:
    """Every product row of every ordering table on the page (see the module notes)."""
    width, height = page.rect.width, page.rect.height
    words = [w for w in page.get_text("words") if w[4].strip()]
    cats = _header_cats(words)
    if not cats:
        return []
    header_lines: List[List[Any]] = []
    for c in sorted(cats, key=lambda w: (w[1], w[0])):
        if header_lines and abs(header_lines[-1][0][1] - c[1]) < 6:
            header_lines[-1].append(c)
        else:
            header_lines.append([c])
    blocks = [b for line in header_lines for b in _blocks(words, line, width, cats)]
    blocks.sort(key=lambda b: b["cat0"])
    _bound(blocks, width)
    rows_out: List[Dict[str, Any]] = []
    for b in blocks:
        rows_out.extend(_read_block(page, words, b, blocks, width, height))
    return rows_out


def _read_block(page, words, b, blocks, width, height) -> List[Dict[str, Any]]:
    hy, x0, x1, shared_x0 = b["hy"], b["x_start"], b["x_end"], b["shared_x0"]
    groups = b["groups"]
    # the table runs down to the next table header printed below it in the same columns
    below = [o["hy"] for o in blocks if o is not b and o["hy"] > hy + 10 and x0 <= o["cat0"] < x1]
    y_end = (min(below) - 6) if below else height - 20
    zone = [w for w in words if x0 <= w[0] < x1 and hy - 9 <= w[1] < y_end]  # header words may start a little above CAT
    lines = _lines(zone)

    def code_hits(line):
        hits = {}
        for gi, g in enumerate(groups):
            cw = [w for w in line if g["cat_lo"] <= w[0] < g["cat_hi"] and code_of(w[4])]
            if g["ord_lo"] is not None:
                ow = [w for w in line if g["ord_lo"] <= w[0] < g["ord_hi"] and ORD_WORD.match(_clean(w[4]))]
            else:  # the header omits the ORD column: the number printed right after the code
                ow = [w for w in line if cw and 0 < w[0] - cw[0][2] < 25 and w[0] < g["cat_hi"] and ORD_WORD.match(_clean(w[4]))]
            if cw or ow:
                hits[gi] = (cw[0] if cw else None, ow[0] if ow else None)
        return hits

    has_ord = any(g["ord"] for g in groups)
    code_lines = [(i, code_hits(l)) for i, l in enumerate(lines) if lines[i][0][1] > hy + 5]
    # A product row prints a code and, in a table with ORD columns, an order number (a thread label
    # such as "M10 × 1" printed under a CAT column in the header is not a product).
    code_lines = [(i, h) for i, h in code_lines
                  if any(c for c, _ in h.values()) and (not has_ord or any(o for _, o in h.values()))]
    if not code_lines:
        return []
    first_i = code_lines[0][0]
    first_y = lines[first_i][0][1]
    ys = [lines[i][0][1] for i, _ in code_lines]
    pitch = median([b2 - a for a, b2 in zip(ys, ys[1:]) if b2 - a < 40] or [13.0])
    pitch = max(pitch, ROW_PITCH_MIN)

    # Header: everything above the first product row. Shared-part words make the columns; words under
    # the CAT/ORD pairs are group labels (one per pair) or a section label (one phrase across).
    # Lines just above the first product row belong to it (a cell printed over two lines, centred on
    # the row), not to the header.
    head_lines = [l for l in lines[:first_i] if l[0][1] < first_y - pitch * 0.72]
    labels = ["" for _ in groups]

    def section_line(line_words) -> Optional[str]:
        """One phrase that starts under the CAT/ORD columns and may run on into the value columns, with
        no order number in it: a section row (e.g. "HOSE WITH PROFESSIONAL 4 JAW COUPLER")."""
        ps = _phrases(line_words, gap=9)
        if len(ps) != 1 or ps[0]["x0"] >= shared_x0 or any(ORD_WORD.match(_clean(w[4])) for w in line_words):
            return None
        if any(_hdr(w[4]) in HEADER_TOKENS for w in line_words) or not re.search(r"[A-Za-z]{3}", ps[0]["text"]):
            return None
        return ps[0]["text"] if ps[0]["x1"] >= shared_x0 else None

    def classify(line_words):
        """("labels", {pair: text}) for labels printed under each CAT/ORD pair, ("section", text) for one
        phrase across the CAT/ORD columns, or None."""
        long_section = section_line(line_words)
        if long_section:
            return ("section", long_section)
        ws = [w for w in line_words if w[0] < shared_x0 and _hdr(w[4]) not in HEADER_TOKENS]
        if not ws:
            return None
        phrases = _phrases(ws, gap=9)
        owners = []
        for p in phrases:
            gi = next((i for i, g in enumerate(groups)
                       if g["cat_lo"] <= p["x0"] < (groups[i + 1]["cat_lo"] if i + 1 < len(groups) else shared_x0)), None)
            owners.append(gi)
        if len(groups) > 1 and len(phrases) > 1 and len(set(owners)) == len(owners) and None not in owners:
            return ("labels", {gi: p["text"] for p, gi in zip(phrases, owners)})
        text = " ".join(p["text"] for p in phrases)
        return ("section", text) if re.search(r"[A-Za-z]{3}", text) else None

    shared_head = [w for l in head_lines if not (l[0][1] > hy + 9 and section_line(l)) for w in l if w[0] >= shared_x0]
    try:
        columns = _leaf_columns(shared_head)
        columns_note = None
    except ValueError as e:
        # Only the box quantity is read (BOX QTY. is always the last column, under its own header).
        box_words = [w for w in shared_head if _hdr(w[4]) in ("BOX", "QTY")]
        columns = ([{"label": "BOX QTY.", "x0": min(w[0] for w in box_words), "x1": max(w[2] for w in box_words),
                     "cx": (min(w[0] for w in box_words) + max(w[2] for w in box_words)) / 2,
                     "lo": min(w[0] for w in box_words) - 12, "hi": 1e9}] if box_words else [])
        columns_note = str(e)

    section = ""
    for l in head_lines:
        if l[0][1] <= hy + 9:  # the CAT / NR. header lines themselves
            continue
        kind = classify(l)
        if kind and kind[0] == "labels":
            for gi, t in kind[1].items():
                labels[gi] = (labels[gi] + " " + t).strip()
        elif kind:
            section = (section + " " + kind[1]).strip()

    # Rows: each product line, with the lines above and below it that belong to it (wrapped cells).
    row_index = {i: k for k, (i, _) in enumerate(code_lines)}
    owners: Dict[int, List[int]] = {k: [] for k in range(len(code_lines))}
    sections_at: Dict[int, str] = {}
    current = section
    last_code_y = ys[-1]
    body_start = next((i for i in range(len(lines)) if lines[i][0][1] >= first_y - pitch * 0.72 and lines[i][0][1] > hy + 9), first_i)
    for i in range(body_start, len(lines)):
        l = lines[i]
        y = l[0][1]
        if i in row_index:
            sections_at[row_index[i]] = current
            continue
        if y > last_code_y + pitch * 0.9:
            break  # below the last row: legends, notes
        nearest = min(range(len(code_lines)), key=lambda k: abs(ys[k] - y))
        only_left = (not any(w[0] >= shared_x0 for w in l) or section_line(l)) and not any(ORD_WORD.match(_clean(w[4])) for w in l)
        if only_left and any(yk > y for yk in ys) and abs(ys[nearest] - y) > pitch * 0.45:
            kind = classify(l)
            if kind and kind[0] == "section":
                current = kind[1]  # a section row: it names the rows below it
                continue
        if abs(ys[nearest] - y) <= pitch * 0.75:
            owners[nearest].append(i)

    rows: List[Dict[str, Any]] = []
    for k, (i, hits) in enumerate(code_lines):
        band = list(lines[i]) + [w for j in owners[k] for w in lines[j]]
        shared = [w for w in band if w[0] >= shared_x0]
        cells: Dict[int, List[Any]] = {}
        for w in shared:
            c = next((ci for ci, col in enumerate(columns) if col["lo"] <= _cx(w) < col["hi"]), None)
            if c is not None:
                cells.setdefault(c, []).append(w)
        values: Dict[str, str] = {}
        box_qty = None
        dims_inch = dims_mm = None
        description = None
        for ci, col in enumerate(columns):
            text = _cell_text(cells.get(ci, []))
            if not text or text in DASHES:
                continue
            n = _norm_label(col["label"])
            if n in ("BOXQTY", "QTY", "PACKQTY"):
                if re.fullmatch(r"\d{1,5}", text):
                    box_qty = int(text)
                continue
            if (n.startswith("SIZE") or n.startswith("DIMENSION")) and ("INCH" in n or n.endswith("MM")):
                if "INCH" in n:
                    dims_inch = text
                else:
                    dims_mm = text
                continue
            if n == "DESCRIPTION":
                description = text
                continue
            values[col["label"]] = text
        for gi, (cw, ow) in hits.items():
            if cw is None:
                continue  # "-" in the CAT column: no product in this variant
            cat_nr = code_of(cw[4])
            ord_nr = _clean(ow[4]) if ow is not None else None
            if ord_nr is None:  # the order number may sit on a wrapped line of the same row
                extra = [w for j in owners[k] for w in lines[j]
                         if groups[gi]["ord_lo"] is not None and groups[gi]["ord_lo"] <= w[0] < groups[gi]["ord_hi"]
                         and ORD_WORD.match(_clean(w[4]))]
                ord_nr = _clean(extra[0][4]) if extra else None
            own_cols = [w for w in band if groups[gi]["cat_lo"] <= w[0] < groups[gi]["ord_hi"]]
            text_row = _cell_text(sorted(own_cols + shared, key=lambda w: (round(w[1]), w[0])))
            prefix = " · ".join(t for t in (labels[gi], sections_at.get(k, "")) if t)
            row = {
                "cat_nr": cat_nr,
                "ord_nr": ord_nr,
                "model_code": cat_nr.replace("/", "-"),
                "description": description,
                "dimensions_inch": dims_inch,
                "dimensions_mm": dims_mm,
                "box_qty": box_qty,
                "measured": {},
                "column_specs": dict(values),
                "variant_label": labels[gi] or None,
                "table_section": sections_at.get(k) or None,
                "source_row_text": (f"[{prefix}] " if prefix else "") + text_row,
                "table_bbox": (x0, hy - 15, x1, ys[-1] + pitch),
                "columns_note": columns_note,
            }
            rows.append(row)
    mid = width / 2.0
    for r in rows:
        bx0, _, bx1, _ = r["table_bbox"]
        r["region_half"] = "left" if bx1 <= mid + 30 else ("right" if bx0 >= mid - 30 else "full_page")
        r["raw_text"] = " ".join(w[4] for w in zone)[:2000]
    return rows


def spec_key(label: str) -> str:
    """The specification key for a printed column label (kept readable: "MAX. PRESSURE (PSI)" ->
    "max._pressure_(psi)"; the website shows the printed label)."""
    return _key(label)


def extract_tile_rows(page: pymupdf.Page, known_ords: set) -> List[Dict[str, Any]]:
    """Products printed as tiles outside any table (e.g. "ACCESSORIES AVAILABLE", "MOUNTING BRACKET
    OPTIONS"): a code with its order number printed directly below it, left-aligned, and the tile's
    description below that. Order numbers already read from a table are skipped."""
    words = [w for w in page.get_text("words") if w[4].strip()]
    rows = []
    codes = [w for w in words if code_of(w[4])]
    for c in codes:
        below = [o for o in words if ORD_WORD.match(_clean(o[4])) and abs(o[0] - c[0]) < 6 and 4 < o[1] - c[1] < 16]
        if not below:
            continue
        o = min(below, key=lambda o: o[1] - c[1])
        ord_nr = _clean(o[4])
        if ord_nr in known_ords:
            continue
        # the tile's column: from its code to the next tile's code on the same line (the last tile of a
        # line is as wide as the others, so badges printed further right are not part of it)
        same = sorted(w[0] for w in codes if abs(w[1] - c[1]) < 3)
        later = [x for x in same if x > c[0] + 10]
        if later:
            right = later[0] - 4
        else:
            earlier = [x for x in same if x < c[0] - 10]
            right = min(c[0] + ((c[0] - earlier[-1]) if earlier else 170), page.rect.width - 20) - 4
        desc, y = [], o[3]
        for line in _lines([w for w in words if c[0] - 4 <= w[0] < right and o[1] + 4 < w[1] < o[1] + 70]):
            if line[0][1] - y > 14 or any(code_of(w[4]) and w[0] < c[0] + 6 for w in line[:1]):
                break
            desc.extend(line)
            y = max(w[3] for w in line)
        heading = None
        heads = [l for l in _lines([w for w in words if c[1] - 260 < w[1] < c[1] - 6 and w[0] < right])
                 if all(re.fullmatch(r"[A-Z&/\-]+", w[4]) for w in l) and len(l) >= 2 and l[0][0] <= c[0] + 20]
        if heads:
            heading = " ".join(w[4] for w in heads[-1])
        rows.append({
            "cat_nr": code_of(c[4]), "ord_nr": ord_nr, "model_code": code_of(c[4]).replace("/", "-"),
            "description": _cell_text(desc) or None, "dimensions_inch": None, "dimensions_mm": None,
            "box_qty": None, "measured": {}, "column_specs": {}, "variant_label": None, "table_section": heading,
            "source_row_text": _cell_text([c, o] + desc),
            "table_bbox": (c[0] - 4, c[1] - 10, right, y + 4),
            "region_half": "left" if right <= page.rect.width / 2 + 30 else ("right" if c[0] >= page.rect.width / 2 - 30 else "full_page"),
            "raw_text": _cell_text([c, o] + desc),
            "tile": True,
        })
        known_ords.add(ord_nr)
    return rows


# ---------------------------------------------------------------------------------------------------------
# The catalogues read with this module (batch_3_fluid). The four catalogues of batches 1 and 2 keep the
# table reader in table_extractor.py unchanged.
GRID_PDFS = {"Fluid_Handling_Catalogue_spread.pdf", "FUEL.pdf"}

# Contents pages: product family titles with the printed page each starts on.
CONTENTS_PAGES: Dict[str, Tuple[int, ...]] = {
    "Fluid_Handling_Catalogue_spread.pdf": (4, 5, 6, 7),
    "FUEL.pdf": (3,),
}


def printed_page_number(page: pymupdf.Page) -> Optional[str]:
    """The page number printed in the page's bottom margin: the largest number set there (CC-07 sets it
    in 14 pt, FUEL CAT 400 in 12 pt; table values printed near the bottom are 7-9 pt)."""
    best = None
    h = page.rect.height
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for sp in line["spans"]:
                t = sp["text"].strip()
                if t.isdigit() and sp["bbox"][1] > h - 80 and sp["size"] >= 11 and (best is None or sp["size"] > best[0]):
                    best = (sp["size"], t)
    return best[1] if best else None


def contents_entries(doc: pymupdf.Document, pages: Tuple[int, ...]) -> List[Dict[str, Any]]:
    """Entries of a contents page: {"title", "page" (first printed page), "contents_page"}. Each column of
    entries ends in a column of right-aligned page numbers; a name may wrap onto the line below."""
    out: List[Dict[str, Any]] = []
    for pno in pages:
        words = doc[pno - 1].get_text("words")
        nums = [w for w in words if re.fullmatch(r"\d{1,3}(?:-\d{1,3})?", w[4])]
        cols: List[float] = []
        for w in sorted(nums, key=lambda w: w[2]):
            if not cols or w[2] - cols[-1] > 20:
                cols.append(w[2])
        cols = [c for c in cols if sum(1 for w in nums if abs(w[2] - c) <= 20) >= 3]
        for ci, cx in enumerate(cols):
            left = cols[ci - 1] + 20 if ci else 0
            col_nums = sorted([w for w in nums if abs(w[2] - cx) <= 20], key=lambda w: w[1])
            region = [w for w in words if left <= w[0] < cx - 12 and w not in col_nums]
            for k, n in enumerate(col_nums):
                nxt_y = col_nums[k + 1][1] if k + 1 < len(col_nums) else 1e9
                same = [w for w in region if abs(w[1] - n[1]) < 3]
                # a wrapped name continues on the line(s) just below, before the next entry
                wrap = [w for w in region if 3 <= w[1] - n[1] < min(12, nxt_y - n[1] - 1)]
                name = " ".join(" ".join(x[4] for x in l) for l in _lines(same + wrap)).strip()
                # (a number in a product name, e.g. "2 piece", is not a page: no entry points before page 6)
                if name and not re.fullmatch(r"[IVX]+", name) and int(n[4].split("-")[0]) >= 6:
                    out.append({"title": name, "page": int(n[4].split("-")[0]), "contents_page": pno})
    return out


def tag_match(tag: str, code: str) -> int:
    """How specifically a picture's printed family tag names a code (0 = not at all). The tag's parts
    must each begin the code's parts in order: "G1-HD" names G1R/HD/B and G1F/HD/N (score 4), "G10-HD"
    names G10R/HD/B more specifically (5) than "G1-HD" does (4)."""
    t = [x for x in re.split(r"[-/]", tag) if x]
    c = [x for x in re.split(r"[-/]", code) if x]
    if not t or len(t) > len(c) or len(t[0]) < 2:
        return 0
    if all(cp.startswith(tp) for tp, cp in zip(t, c)):
        return sum(len(x) for x in t)
    return 0


def grid_picture(cat_nr: Optional[str], page_cands: List[Dict[str, Any]], facing_cands: List[Dict[str, Any]],
                 tables_on_page: int) -> Optional[Tuple[Dict[str, Any], str, str]]:
    """The picture for a product of CC-07 / FUEL CAT 400 (rules 3.0.0), with its evidence:

    1. a picture labelled with the product's own code (direct_product);
    2. a picture labelled with a family tag the code begins with, the most specific tag winning
       ("G1-HD" for G1R/HD/B; product_family);
    3. when no picture of the page (or of the spread, with the facing left-hand page) carries any code
       or tag: the largest picture there, if the page holds a single ordering table (product_family);
    4. otherwise none (pictures labelled for other products are never given to this one).
    """
    if not cat_nr:
        return None
    cands = list(page_cands) + list(facing_cands)
    def tags(c):
        return [t for t in (code_of(x) for x in re.split(r"\s+", c.get("label_text") or "")) if t]
    for c in cands:
        if cat_nr in tags(c):
            return c, "direct_product", f"product code {cat_nr} printed beside the picture"
    scored = [(tag_match(t, cat_nr), t, c) for c in cands for t in tags(c)]
    scored = [s for s in scored if s[0]]
    if scored:
        best = max(s[0] for s in scored)
        top = [s for s in scored if s[0] == best]
        if len({id(s[2]) for s in top}) == 1:
            _, t, c = top[0]
            return c, "product_family", f"picture labelled {t}, the family tag its code {cat_nr} begins with"
        return None
    if any(tags(c) for c in cands) or tables_on_page != 1:
        return None
    pool = page_cands or facing_cands
    if not pool:
        return None
    c = max(pool, key=lambda c: c["area"])
    where = "this page" if page_cands else "the facing page of the spread"
    return c, "product_family", (f"largest picture on {where}; the page holds one ordering table and no picture "
                                 "there is labelled with a product code")
