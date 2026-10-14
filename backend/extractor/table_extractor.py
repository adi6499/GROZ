"""Table Extractor for GROZ Product Catalogues.

Extracts ordering matrices (CAT NR, ORD NR, DESCRIPTION, DIMENSIONS, BOX QTY)
and specification mode grids with strict spatial boundaries across both
two-page spreads (Batch 1) and single-page portrait catalogues (Batch 2).

Recovery changes (14 Oct 2026), each covered by a regression test:
- Side-by-side CAT/ORD column groups ("paired" tables such as GRADE A | GRADE B, or two
  complete tables in one half-page) yield one record per printed CAT/ORD pair. Previously
  only the left pair was kept.
- The CAT NR pattern accepts a single-letter prefix (G/10/M1 was truncated to 10/M1).
- Box quantity is the value under the table's own BOX QTY header in the product's row (no
  value whitelist). A table without a BOX QTY column yields no box quantity.
- Dimensions may begin with a bare fraction (1/16 × 5/16 × 3-1/2 lost its leading "1/").
- Row attributes are read only from the product's own row, inside the table's horizontal
  extent, and only when the table has the matching column header (no leakage from feature
  text printed beside the table). Power source is read verbatim, never derived from plug type.
"""

from statistics import median
from typing import List, Dict, Any, Optional, Sequence
import pymupdf
import re

_LEAD_GLYPHS = re.compile(r'^[^A-Za-z0-9]+')
_ORD_WORD = re.compile(r'^\d{5}$')


def _clean_token(token: str) -> str:
    """Strip best-seller / new-product glyphs before a code and trailing punctuation after it."""
    return _LEAD_GLYPHS.sub('', token).rstrip('.,;:)')


def _hdr(token: str) -> str:
    """Normalise a header word for comparison (e.g. 'QTY.' -> 'QTY')."""
    return token.upper().strip('.:|')


def _center_x(w: Sequence[Any]) -> float:
    return (w[0] + w[2]) / 2.0


def _group_lines(words: List[Any], tol: float = 4.0) -> List[List[Any]]:
    """Group words into visual lines (same rule as the original extractor)."""
    lines: List[List[Any]] = []
    cur: List[Any] = []
    cur_y: Optional[float] = None
    for w in sorted(words, key=lambda w: (w[1], w[0])):
        if cur_y is None or abs(w[1] - cur_y) < tol:
            cur.append(w)
            cur_y = w[1] if cur_y is None else (cur_y + w[1]) / 2.0
        else:
            lines.append(sorted(cur, key=lambda x: x[0]))
            cur = [w]
            cur_y = w[1]
    if cur:
        lines.append(sorted(cur, key=lambda x: x[0]))
    return lines


def _words_text(words: List[Any]) -> str:
    """Join words line by line, preserving reading order."""
    return " \n ".join(" ".join(w[4] for w in line) for line in _group_lines(words))


class TableExtractor:
    """Extracts structured tables from PDF pages using spatial coordinates and text layout."""

    CAT_PATTERN = (
        r'(?:[*º‡\x87Ø]\s*)?((?=[A-Z0-9/\-.]*[A-Z])('
        r'(?:LED|RTC|RTCL|TCH|TCHL|TCHH|TCHS|MTB|SRC|WBN)/[A-Z0-9/\-.]+|'
        r'E[A-Z0-9]{1,4}(?:[/-][A-Z0-9/\-.]+)+|'
        r'E[A-Z0-9]{1,4}-[A-Z0-9/\-.]+|'
        r'[A-Z0-9]{2,8}(?:[/-][A-Z0-9/\-.]+)+|'
        r'[A-Z]{2,6}/\d+(?:[A-Z0-9/\-.]+)?|'
        r'[A-Z]{2,6}-[A-Z0-9/\-.]+|'
        r'[A-Z]/\d[A-Z0-9/\-.]*'  # single-letter prefix, e.g. G/10/M1 (Precision p61)
        r'))'
    )
    ORD_PATTERN = r'(?<![\.\d])(\d{5})(?![\.\d])'

    # Dimension terms: mixed fraction (75-1/2), bare fraction (1/16, also "1/ 2" as printed),
    # or decimal/integer; a parenthesised range "(48 to 75-1/2)"; joined by × or x (2D or 3D).
    _NUM = r'(?:\d+-\d+/\s?\d+|\d+/\s?\d+|\d+(?:\.\d+)?)'
    _RANGE = r'\(\s*' + _NUM + r'\s*(?:to|-|–)\s*' + _NUM + r'\s*\)'
    _TERM = r'(?:' + _RANGE + r'|' + _NUM + r')'
    _SEP = r'[^\S\n]*[×x][^\S\n]*'
    DIM_PATTERN = r'(?<![\w/.\-])(' + _TERM + r'(?:' + _SEP + _TERM + r'){1,2})(?![\w/.])'

    HEAD_WEIGHT_PATTERN = (
        r'(\d+(?:\.\d+)?[^\S\n]*(?:lbs?|kg|g)(?![a-z])\.?'
        r'(?:[^\S\n]*/[^\S\n]*[0-9.]+[^\S\n]*(?:kg|lbs?|g)(?![a-z])\.?)?)'
    )
    LENGTH_PATTERN = (
        r'(\d+(?:\.\d+)?[^\S\n]*(?:”|″|"|inch(?![a-z])|in(?![a-z]))'
        r'(?:[^\S\n]*/[^\S\n]*[0-9.]+[^\S\n]*mm)?)'
    )
    POWER_PATTERN = r'(\d+\s*V\s*AC,?\s*\d+\s*Hz)'

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @staticmethod
    def extract_ordering_records(page: pymupdf.Page, source_pdf: str, page_number: int) -> List[Dict[str, Any]]:
        """Finds ordering tables on the page (spread or single-page) and extracts structured rows."""
        width = page.rect.width
        height = page.rect.height
        mid_x = width / 2.0
        ordering_records: List[Dict[str, Any]] = []

        def _annotate(rows: List[Dict[str, Any]], half: str, clip: pymupdf.Rect) -> None:
            for row in rows:
                row["source_pdf"] = source_pdf
                row["physical_page_number"] = page_number
                row.setdefault("region_half", half)
                row["table_bbox"] = (clip.x0, clip.y0, clip.x1, clip.y1)
                ordering_records.append(row)

        # ---------------------------------------------------------
        # Case A: Two-page spread layout (Batch 1: width > 800 pt)
        # ---------------------------------------------------------
        if width > 800:
            rects = page.search_for("ORDERING INFORMATION")
            rects.sort(key=lambda r: (0 if r.x0 < mid_x else 1, r.y0))

            for r in rects:
                half = "left" if r.x0 < mid_x else "right"
                same_half_next = [
                    other for other in rects
                    if (("left" if other.x0 < mid_x else "right") == half) and other.y0 > r.y0 + 10
                ]
                max_y = same_half_next[0].y0 - 5 if same_half_next else (height - 35)
                x_min = max(0, r.x0 - 20)
                x_max = mid_x - 10 if half == "left" else (width - 10)
                table_clip = pymupdf.Rect(x_min, r.y0 - 2, x_max, max_y)
                _annotate(TableExtractor._extract_rows_from_clip(page, table_clip), half, table_clip)

            return ordering_records

        # ---------------------------------------------------------
        # Case B: Single portrait page layout (Batch 2: width <= 800 pt)
        # ---------------------------------------------------------
        # Knurls matrix page (Page 68 of Precision Catalogue)
        knurls_rects = page.search_for("CAT. & ORDERING NR.")
        if knurls_rects:
            knurl_clip = pymupdf.Rect(20, max(0, knurls_rects[0].y0 - 20), width - 20, height - 30)
            _annotate(TableExtractor._parse_knurl_matrix_page(page, knurl_clip), "full_page", knurl_clip)
            return ordering_records

        # Standard single-page table detection via CAT/ORD headers
        words = page.get_text("words")
        cat_headers = []
        for w in words:
            clean = w[4].upper().strip(".:|")
            if clean == "CAT":
                has_nr_below = any(
                    "NR" in other[4].upper() and abs(other[0] - w[0]) < 15 and 0 < (other[1] - w[1]) < 25
                    for other in words
                )
                has_ord_nearby = any(
                    "ORD" in other[4].upper() and (0 < other[0] - w[0] < 120) and abs(other[1] - w[1]) < 20
                    for other in words
                )
                if has_ord_nearby or (has_nr_below and any(o[4].upper().strip(".:") in ["ORD", "ORDERING"] for o in words)):
                    cat_headers.append(w)

        if not cat_headers:
            oi_rects = page.search_for("ORDERING INFORMATION")
            if oi_rects:
                clip = pymupdf.Rect(20, max(0, oi_rects[0].y0 - 2), width - 20, height - 30)
                _annotate(TableExtractor._extract_rows_from_clip(page, clip), "full_page", clip)
            return ordering_records

        # Header lines carrying two or more CAT headers: side-by-side column groups.
        handled: List[Any] = []
        for line in TableExtractor._group_header_lines(cat_headers):
            if len(line) < 2:
                continue
            blocks = TableExtractor._plan_blocks(words, line, width)
            if not TableExtractor._needs_block_parser(blocks, mid_x):
                continue
            hy = min(h[1] for h in line)
            for block in blocks:
                bx0, bx1 = block[0]["x_start"], block[-1]["x_end"]
                below = [h[1] for h in cat_headers if h[1] > hy + 5 and bx0 - 30 <= h[0] <= bx1]
                y_bottom = (min(below) - 10) if below else (height - 30)
                half = "left" if bx1 <= mid_x + 30 else ("right" if bx0 >= mid_x - 30 else "full_page")
                clip = pymupdf.Rect(max(0, bx0), max(0, hy - 15), min(width, bx1), y_bottom)
                _annotate(TableExtractor._parse_block(words, block, hy, y_bottom), half, clip)
            handled.extend(line)

        remaining = [h for h in cat_headers if not any(h is x for x in handled)]
        if not remaining:
            return ordering_records
        handled_ys = sorted({round(h[1], 1) for h in handled})

        def _cap(y_top: float, y_bottom: float) -> float:
            """Stop a table's clip at the next side-by-side header line handled above."""
            nxt = [y for y in handled_ys if y > y_top + 20]
            return min([y_bottom] + [y - 10 for y in nxt])

        # If only 1 CAT header remains on page:
        if len(remaining) == 1:
            ch = remaining[0]
            clip = pymupdf.Rect(20, max(0, ch[1] - 15), width - 20, _cap(ch[1], height - 30))
            _annotate(TableExtractor._extract_rows_from_clip(page, clip), "full_page", clip)
            return ordering_records

        # Multiple CAT headers: Partition by left and right columns
        left_headers = sorted([h for h in remaining if h[0] < mid_x], key=lambda h: h[1])
        right_headers = sorted([h for h in remaining if h[0] >= mid_x], key=lambda h: h[1])

        for i, h in enumerate(left_headers):
            y_top = max(0, h[1] - 15)
            y_bottom = (left_headers[i + 1][1] - 10) if (i + 1 < len(left_headers)) else (height - 30)
            x_right = (mid_x - 5) if right_headers else (width - 20)
            clip = pymupdf.Rect(20, y_top, x_right, _cap(h[1], y_bottom))
            _annotate(TableExtractor._extract_rows_from_clip(page, clip), "left", clip)

        for i, h in enumerate(right_headers):
            y_top = max(0, h[1] - 15)
            y_bottom = (right_headers[i + 1][1] - 10) if (i + 1 < len(right_headers)) else (height - 30)
            clip = pymupdf.Rect(mid_x + 5, y_top, width - 20, _cap(h[1], y_bottom))
            _annotate(TableExtractor._extract_rows_from_clip(page, clip), "right", clip)

        return ordering_records

    # ------------------------------------------------------------------
    # Code / header helpers
    # ------------------------------------------------------------------
    @staticmethod
    def cat_code_of_word(token: str) -> Optional[str]:
        """Return the CAT NR if a single printed word is entirely a catalogue code, else None."""
        t = _clean_token(token)
        m = re.match(TableExtractor.CAT_PATTERN, t)
        return t if (m and m.group(1) == t) else None

    @staticmethod
    def _group_header_lines(cat_headers: List[Any]) -> List[List[Any]]:
        lines: List[List[Any]] = []
        for h in sorted(cat_headers, key=lambda w: (w[1], w[0])):
            if lines and abs(lines[-1][0][1] - h[1]) < 4:
                lines[-1].append(h)
            else:
                lines.append([h])
        return lines

    @staticmethod
    def _plan_blocks(words: List[Any], line_cats: List[Any], page_width: float) -> List[List[Dict[str, Any]]]:
        """Split a header line with several CAT headers into column groups and table blocks.

        A group is one CAT/ORD column pair. A group "owns" columns when other header words
        (SIZE, BOX, RANGE, ...) follow its ORD before the next CAT. Consecutive groups without
        own columns share the columns of the next group that has them (a paired table).
        """
        cats = sorted(line_cats, key=lambda w: w[0])
        hy = cats[0][1]
        zone = [w for w in words if hy - 3 <= w[1] <= hy + 15]
        groups: List[Dict[str, Any]] = []
        for i, c in enumerate(cats):
            nxt = cats[i + 1][0] if i + 1 < len(cats) else None
            limit = (nxt - 22) if nxt is not None else page_width
            ords = [w for w in zone if _hdr(w[4]) == "ORD" and c[0] < w[0] < limit]
            own = [w for w in zone if c[0] < w[0] < limit and _hdr(w[4]) not in ("CAT", "ORD", "NR")]
            groups.append({
                "cat": c,
                "ord": min(ords, key=lambda w: w[0]) if ords else None,
                "own_columns": bool(own),
                "x_start": c[0] - 22,
                "x_end": (nxt - 22) if nxt is not None else page_width - 15,
            })
        blocks: List[List[Dict[str, Any]]] = []
        cur: List[Dict[str, Any]] = []
        for g in groups:
            cur.append(g)
            if g["own_columns"]:
                blocks.append(cur)
                cur = []
        if cur:
            blocks.append(cur)
        return blocks

    @staticmethod
    def _needs_block_parser(blocks: List[List[Dict[str, Any]]], mid_x: float) -> bool:
        """Use the column-group parser for paired groups, or for independent tables sharing a half page.

        Independent tables in opposite halves (e.g. Estwing p4) keep the original half-page parser.
        """
        if any(len(b) > 1 for b in blocks):
            return True
        halves = ["L" if b[0]["cat"][0] < mid_x else "R" for b in blocks]
        return len(set(halves)) < len(halves)

    @staticmethod
    def _column_value(candidates: List[Any], header_word: Optional[Any], anchor_y: float,
                      tol: float = 18.0, pattern: str = r'^\d{1,4}$') -> Optional[Any]:
        """Pick the word printed under a header column in this row (nearest to the row's anchor line)."""
        if header_word is None:
            return None
        hx = _center_x(header_word)
        hits = [w for w in candidates if abs(_center_x(w) - hx) <= tol and re.match(pattern, _clean_token(w[4]))]
        if not hits:
            return None
        return min(hits, key=lambda w: (abs(w[1] - anchor_y), abs(_center_x(w) - hx)))

    @staticmethod
    def _header_word(header_words: List[Any], *names: str) -> Optional[Any]:
        hits = [w for w in header_words if _hdr(w[4]) in names]
        return min(hits, key=lambda w: (w[1], w[0])) if hits else None

    @staticmethod
    def _qualified_columns(header_words: List[Any], name: str) -> List[Any]:
        """Header words equal to `name` (e.g. LENGTH) with their qualifier word, if any.

        The qualifier is the header word printed immediately to the left on the same line, or
        directly above it (two-line headers such as OVERALL / LENGTH). Returns [(qualifier, word)].
        """
        skip = {"CAT", "ORD", "NR"}
        out = []
        for w in sorted(header_words, key=lambda w: (w[1], w[0])):
            if _hdr(w[4]) != name:
                continue
            left = [o for o in header_words if abs(o[1] - w[1]) < 3 and 0 <= w[0] - o[2] < 12 and _hdr(o[4]) not in skip]
            above = [o for o in header_words if 4 < w[1] - o[1] < 14 and abs(_center_x(o) - _center_x(w)) < 25
                     and _hdr(o[4]) not in skip]
            cand = left or above
            out.append((_hdr(max(cand, key=lambda o: o[1])[4]) if cand else None, w))
        return out

    _UNITS = ("mm", "cm", "kg", "g", "lb", "lbs", "in", "inch")

    @staticmethod
    def _column_measure(row_words: List[Any], header_word: Any, pattern: str) -> Optional[str]:
        """Read a measurement printed under `header_word` in this row (e.g. 24”/600mm, 6lb/2.7kg).

        Checked line by line. A line is skipped when the words under the column belong to a run of
        prose (a set description such as "One each of 2" (50 mm), 3" ..." spanning the columns).
        """
        hx = _center_x(header_word)
        for line in _group_lines(row_words):
            window = [w for w in line if abs(_center_x(w) - hx) <= 40]
            if not window:
                continue
            runs, cur = [], [line[0]]
            for a, b in zip(line, line[1:]):
                if b[0] - a[2] <= 6:
                    cur.append(b)
                else:
                    runs.append(cur)
                    cur = [b]
            runs.append(cur)
            touched = [w for r in runs if any(x is w for w in r for x in window) for w in r]
            if any(re.fullmatch(r"[A-Za-z]+[.,):]*", w[4]) and w[4].lower().strip(".,):") not in TableExtractor._UNITS
                   for w in touched):
                continue
            m = re.search(pattern, " ".join(w[4] for w in window), re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    @staticmethod
    def _column_keys(header_words: List[Any], name: str) -> List[Any]:
        """Spec keys named after the printed column headers: LENGTH -> length, OVERALL LENGTH ->
        overall_length, HEAD WEIGHT -> head_weight, HANDLE LENGTH -> handle_length, ...

        Returns [(key, header_word)], one per printed column, first occurrence of each key only.
        """
        out, seen = [], set()
        for q, w in TableExtractor._qualified_columns(header_words, name):
            qual = re.sub(r'[^a-z]', '', (q or "").lower())
            key = f"{qual}_{name.lower()}" if qual else name.lower()
            if key not in seen:
                seen.add(key)
                out.append((key, w))
        return out

    # ------------------------------------------------------------------
    # Single-group tables (one CAT/ORD pair per row)
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_rows_from_clip(page: pymupdf.Page, clip: pymupdf.Rect) -> List[Dict[str, Any]]:
        """Extracts spatial text lines from a table clip box and parses them into rows."""
        all_words = [w for w in page.get_text("words", clip=clip) if w[4].strip()]
        table_text = page.get_text("text", clip=clip).strip()

        # Table geometry: the top-most CAT header and its BOX QTY header bound the table horizontally.
        cats = [w for w in all_words if _hdr(w[4]) == "CAT"]
        cat_hdr = min(cats, key=lambda w: (round(w[1]), w[0])) if cats else None
        qty_hdr = None
        if cat_hdr is not None:
            qtys = [w for w in all_words if _hdr(w[4]) == "QTY" and cat_hdr[1] - 5 <= w[1] <= cat_hdr[1] + 30
                    and w[0] > cat_hdr[0]]
            qty_hdr = min(qtys, key=lambda w: w[0]) if qtys else None
        x_left = (cat_hdr[0] - 40) if cat_hdr is not None else clip.x0
        x_right = (qty_hdr[2] + 25) if qty_hdr is not None else clip.x1

        lines = _group_lines(all_words)
        texts = [" ".join(w[4] for w in lw) for lw in lines]
        # The line holding the CAT header is never a product row, even when a caption printed just
        # below the header (e.g. "EST/2/ST" on Precision p39) is grouped into the same visual line.
        header_line = next((i for i, lw in enumerate(lines) if any(w is cat_hdr for w in lw)), -1)
        cat_idx = [i for i, t in enumerate(texts) if i > header_line and re.search(TableExtractor.CAT_PATTERN, t)]
        if not cat_idx:
            cat_idx = [i for i, t in enumerate(texts) if i > header_line and re.search(TableExtractor.ORD_PATTERN, t)]
        if not cat_idx:
            return []

        header_words = [w for lw in lines[:cat_idx[0]] for w in lw if x_left <= w[0] <= x_right]
        header_text = _words_text(header_words) if header_words else " ".join(texts[:min(5, len(texts))])
        has_ord_column = bool(re.search(r'\bORD(?:\.|\b)', header_text))

        anchor_ys = [min(w[1] for w in lines[i]) for i in cat_idx]
        # A row never extends further than a normal row height below its CAT line: this stops the
        # text of a section heading or another table further down the page joining the row above it.
        gaps = [b - a for a, b in zip(anchor_ys, anchor_ys[1:]) if b - a <= 40]
        row_cap = max(1.6 * median(gaps), 22.0) if gaps else 22.0

        rows = []
        for k, idx in enumerate(cat_idx):
            end_idx = cat_idx[k + 1] if k + 1 < len(cat_idx) else len(lines)
            slice_lines = [lw for lw in lines[idx:end_idx] if min(w[1] for w in lw) <= anchor_ys[k] + row_cap]
            slice_text = " \n ".join(" ".join(w[4] for w in lw) for lw in slice_lines)
            slice_text = slice_text.replace("Î", "×").replace("Ð", "×")
            slice_words = [w for lw in slice_lines for w in lw]
            attr_words = [w for w in slice_words if x_left <= w[0] <= x_right]

            cat_match = re.search(TableExtractor.CAT_PATTERN, slice_text)
            cat_nr = cat_match.group(1) if cat_match else None
            if cat_nr:
                cat_nr = re.sub(r'^[*º‡\x87Ø\s]+', '', cat_nr)
            ord_match = re.search(TableExtractor.ORD_PATTERN, slice_text)
            ord_nr = ord_match.group(1) if ord_match else None
            if has_ord_column and not ord_nr:
                continue

            box_word = TableExtractor._column_value(slice_words, qty_hdr, anchor_ys[k])
            box_qty = int(_clean_token(box_word[4])) if box_word is not None else None
            row = TableExtractor._row_attributes(
                attr_text=_words_text(attr_words).replace("Î", "×").replace("Ð", "×"),
                header_text=header_text,
                header_words=header_words,
                attr_words=[w for w in attr_words if w is not box_word],
                anchor_y=anchor_ys[k],
                cat_nr=cat_nr,
                ord_nr=ord_nr,
                box_qty=box_qty,
            )
            row["source_row_text"] = _words_text(attr_words)
            rows.append(row)

        for r in rows:
            r["raw_text"] = table_text
        return rows

    # ------------------------------------------------------------------
    # Column-group tables (several CAT/ORD pairs per printed row)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_block(words: List[Any], block: List[Dict[str, Any]], hy: float, y_bottom: float) -> List[Dict[str, Any]]:
        x0, x1 = block[0]["x_start"], block[-1]["x_end"]
        bw = [w for w in words if x0 <= w[0] < x1 and hy - 3 <= w[1] <= y_bottom and w[4].strip()]
        g0 = block[0]
        g0_cat_hi = (g0["ord"][0] - 2) if g0["ord"] is not None else g0["x_end"]
        anchors = sorted(
            [w for w in bw if w[1] > hy + 5 and g0["x_start"] <= w[0] < g0_cat_hi
             and TableExtractor.cat_code_of_word(w[4])],
            key=lambda w: w[1],
        )
        if not anchors:
            return []
        first_y = anchors[0][1]
        header_words = [w for w in bw if w[1] < first_y - 1]
        header_text = _words_text(header_words)
        qty_hdr = TableExtractor._header_word(header_words, "QTY")
        last_ord_x = max((g["ord"][0] for g in block if g["ord"] is not None), default=g0["x_start"])
        shared_x0 = last_ord_x + 25
        table_text = _words_text(bw)

        anchor_ys = [a[1] for a in anchors]
        gaps = [b - a for a, b in zip(anchor_ys, anchor_ys[1:])]
        last_cap = max(1.6 * median(gaps), 22.0) if gaps else 22.0

        labels: List[Optional[str]] = []
        for g in block:
            if len(block) < 2:
                labels.append(None)
                continue
            lab_hi = (g["ord"][0] + 25) if g["ord"] is not None else g["x_end"]
            lab = [w for w in header_words if w[1] > hy + 6 and g["x_start"] <= w[0] < lab_hi
                   and _hdr(w[4]) not in ("CAT", "ORD", "NR")]
            labels.append(" ".join(w[4] for w in sorted(lab, key=lambda w: (round(w[1]), w[0]))) or None)

        rows: List[Dict[str, Any]] = []
        for k, a in enumerate(anchors):
            y_lo = a[1] - 4
            y_hi = (anchors[k + 1][1] - 2) if k + 1 < len(anchors) else (a[1] + last_cap)
            band = [w for w in bw if y_lo <= w[1] < y_hi]
            shared = [w for w in band if w[0] >= shared_x0]
            box_word = TableExtractor._column_value(shared, qty_hdr, a[1])
            box_qty = int(_clean_token(box_word[4])) if box_word is not None else None
            shared_attr = [w for w in shared if w is not box_word]

            for gi, g in enumerate(block):
                cat_hi = (g["ord"][0] - 2) if g["ord"] is not None else g["x_end"]
                cws = [w for w in band if g["x_start"] <= w[0] < cat_hi and TableExtractor.cat_code_of_word(w[4])]
                if not cws:
                    continue
                cw = min(cws, key=lambda w: abs(w[1] - a[1]))
                cat_nr = TableExtractor.cat_code_of_word(cw[4])
                ord_nr = None
                if g["ord"] is not None:
                    ows = [w for w in band if g["ord"][0] - 12 <= w[0] < g["x_end"] and _ORD_WORD.match(_clean_token(w[4]))]
                    if not ows:
                        continue
                    ord_nr = _clean_token(min(ows, key=lambda w: (abs(w[0] - g["ord"][0]), abs(w[1] - a[1])))[4])

                row = TableExtractor._row_attributes(
                    attr_text=_words_text(shared_attr).replace("Î", "×").replace("Ð", "×"),
                    header_text=header_text,
                    header_words=header_words,
                    attr_words=shared_attr,
                    anchor_y=a[1],
                    cat_nr=cat_nr,
                    ord_nr=ord_nr,
                    box_qty=box_qty,
                )
                own_words = [w for w in band if g["x_start"] <= w[0] < (g["x_end"] if gi + 1 < len(block) else shared_x0)]
                row["source_row_text"] = (f"[{labels[gi]}] " if labels[gi] else "") + _words_text(own_words + shared)
                if labels[gi]:
                    row["variant_label"] = labels[gi]
                row["raw_text"] = table_text
                rows.append(row)
        return rows

    # ------------------------------------------------------------------
    # Row attributes (shared by both parsers and by the text-only parser)
    # ------------------------------------------------------------------
    @staticmethod
    def _row_attributes(attr_text: str, header_text: str, header_words: List[Any], attr_words: List[Any],
                        anchor_y: float, cat_nr: Optional[str], ord_nr: Optional[str],
                        box_qty: Optional[int]) -> Dict[str, Any]:
        """Reads a row's own attributes. Each attribute requires its column header in this table."""
        hu = header_text.upper()
        has = {
            "spring": "SPRING" in hu,
            "top": re.search(r'\bTOP\b', hu) is not None,
            "colour": "COLOUR" in hu or "COLOR" in hu,
            "drawer": "DRAWER" in hu,
            "plug": "PLUG" in hu,
            "power": "POWER" in hu,
            "size": any(k in hu for k in ("SIZE", "(INCH)", "(MM)", "DIA", "DIMENSION")),
        }
        slice_text = attr_text
        slice_lines = [l for l in slice_text.split("\n")]

        def column_text(*names: str, tol: float = 40.0) -> Optional[str]:
            hw = TableExtractor._header_word(header_words, *names)
            if hw is None or not attr_words:
                return None
            hx = _center_x(hw)
            ws = [w for w in attr_words if abs(_center_x(w) - hx) <= tol]
            return _words_text(ws) if ws else ""

        model_code = cat_nr.replace('/', '-') if cat_nr else None
        if model_code and '/' in model_code:
            model_code = model_code.split('/')[0]

        # Weight and length columns: one spec key per printed column, named after its header
        # (HEAD WEIGHT -> head_weight, WEIGHT -> weight, OVERALL LENGTH -> overall_length,
        # HANDLE LENGTH -> handle_length, LENGTH -> length). The value is read under that column and
        # kept only if it carries a unit (e.g. 24”/600mm, 6lb/2.7kg); bare numbers are not guessed at.
        measured: Dict[str, Optional[str]] = {}
        for name, pattern in (("WEIGHT", TableExtractor.HEAD_WEIGHT_PATTERN), ("LENGTH", TableExtractor.LENGTH_PATTERN)):
            if header_words:
                for key, hw in TableExtractor._column_keys(header_words, name):
                    value = TableExtractor._column_measure(attr_words, hw, pattern)
                    if value:
                        measured[key] = value
            else:  # text-only parsing (no geometry): only the hammer-table headers are recognised
                qual = "HEAD" if name == "WEIGHT" else "OVERALL"
                m = re.search(pattern, slice_text, re.IGNORECASE) if (qual in hu and name in hu) else None
                if m:
                    measured[f"{qual.lower()}_{name.lower()}"] = m.group(1).strip()

        spring_steel_bars = None
        if has["spring"]:
            src = column_text("BARS", "SPRING")
            for sl in (src.split("\n") if src is not None else slice_lines):
                sb_m = re.search(r'\b([246])\s*$', sl.strip())
                if sb_m:
                    spring_steel_bars = int(sb_m.group(1))
                    break

        top_opt = None
        if has["top"]:
            for opt in ["Rubberized Mat", "Thermofoam", "Wooden", "Stainless Steel"]:
                if opt.lower() in slice_text.lower():
                    top_opt = opt
                    break

        colour = None
        if has["colour"]:
            for col in ["Classic Black", "Cool Grey", "Bossy Blue", "Fiery Red", "Royal Purple", "Aqua Lux", "Vibrant Orange"]:
                if col.lower() in slice_text.lower():
                    colour = col
                    break

        dim_inch = dim_mm = None
        if has["size"]:
            dims = [d.strip() for d in re.findall(TableExtractor.DIM_PATTERN, slice_text)]
            has_inch, has_mm = "(INCH)" in hu, "(MM)" in hu
            if has_mm and not has_inch:
                dim_mm = dims[0] if dims else None
            else:
                dim_inch = dims[0] if len(dims) > 0 else None
                dim_mm = dims[1] if len(dims) > 1 else None

        # Drawer count: only from a "NO. OF DRAWERS" column, as a standalone number under its header
        # (a "7 DRAWER" caption or a digit inside a CAT NR is not a drawer count).
        no_drawers = None
        drawers_hdr = TableExtractor._header_word(header_words, "DRAWERS")
        if drawers_hdr is not None:
            dw = TableExtractor._column_value(attr_words, drawers_hdr, anchor_y, tol=22.0, pattern=r'^\d{1,2}$')
            no_drawers = int(_clean_token(dw[4])) if dw is not None else None
        elif not header_words and has["drawer"]:  # text-only parsing (no geometry)
            clean_for_dr = slice_text
            if ord_nr:
                clean_for_dr = clean_for_dr.replace(ord_nr, " ")
            if cat_nr:
                clean_for_dr = clean_for_dr.replace(cat_nr, " ")
            if box_qty is not None:
                clean_for_dr = re.sub(rf'\b{box_qty}\b', ' ', clean_for_dr)
            dr_candidates = [int(m) for m in re.findall(r'\b([2-9]|10)\b', clean_for_dr)]
            no_drawers = dr_candidates[0] if dr_candidates else None

        desc = None
        if "tripod" in slice_text.lower():
            # The light type is the word printed before "complete" in this row (LED/685T prints
            # "Sitelamp complete with tripod"); the old two-way guess is kept only as a fallback.
            tm = re.search(r"\b(Worklight|Floodlight|Sitelamp)\s+complete\b", slice_text)
            kind = tm.group(1) if tm else ("Worklight" if "worklight" in slice_text.lower() else "Floodlight")
            desc = f"{kind} complete with tripod"
        elif "Tool Box with Trolley" in slice_text:
            desc = "Tool Box with Trolley"
        elif "Tool Box" in slice_text:
            desc = "Tool Box"
        elif "Single Piece" in slice_text:
            desc = "Single Piece"
        elif "Set of Two" in slice_text:
            desc = "Set of Two"
        elif "Floodlight" in slice_text:
            desc = "Floodlight"
        elif "Worklight" in slice_text:
            desc = "Worklight"
        elif "Sitelamp" in slice_text:
            desc = "Sitelamp"

        plug_type = None
        if has["plug"]:
            if "EU" in (cat_nr or "") or "EU Pin" in slice_text or re.search(r'\bEU\b', slice_text):
                plug_type = "EU"
            elif "US" in (cat_nr or "") or "US Pin" in slice_text or re.search(r'\bUS\b', slice_text):
                plug_type = "US"
        power_source = None
        if has["power"]:
            pm = re.search(TableExtractor.POWER_PATTERN, slice_text)
            power_source = pm.group(1) if pm else None

        return {
            "ord_nr": ord_nr,
            "cat_nr": cat_nr,
            "model_code": model_code,
            "description": desc,
            "dimensions_inch": dim_inch,
            "dimensions_mm": dim_mm,
            "box_qty": box_qty,
            "measured": measured,  # weight/length columns, keyed by printed header
            "head_weight": measured.get("head_weight"),
            "overall_length": measured.get("overall_length"),
            "spring_steel_bars": spring_steel_bars,
            "top_options": top_opt,
            "colour": colour,
            "no_of_drawers": no_drawers,
            "plug_type": plug_type,
            "power_source": power_source,
        }

    # ------------------------------------------------------------------
    # Knurl matrix (unchanged)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_knurl_matrix_page(page: pymupdf.Page, clip: pymupdf.Rect) -> List[Dict[str, Any]]:
        """Specialized parser for the Knurl Matrix table (Precision Catalogue Page 68)."""
        text = page.get_text("text", clip=clip)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        sizes = ['5/8"', '3/4"', '1"', '20 mm']
        rows = []

        for i, line in enumerate(lines):
            if "Cat. Nr." in line or line == "Cat. Nr.":
                cat_candidates = []
                idx = i + 1
                while idx < len(lines) and len(cat_candidates) < 4 and not lines[idx].startswith("Ordering"):
                    cat_candidates.append(lines[idx])
                    idx += 1

                ord_candidates = []
                if idx < len(lines) and "Ordering" in lines[idx]:
                    idx += 1
                    while idx < len(lines) and len(ord_candidates) < 4:
                        if re.match(r'^\d{5}$', lines[idx]):
                            ord_candidates.append(lines[idx])
                        idx += 1

                desc_line = lines[i - 1] if i > 0 else "Knurl"

                if len(cat_candidates) == 4 and len(ord_candidates) == 4:
                    for k in range(4):
                        c_nr = cat_candidates[k]
                        o_nr = ord_candidates[k]
                        sz = sizes[k]
                        dim_in = sz if "mm" not in sz else None
                        dim_m = sz if "mm" in sz else None
                        rows.append({
                            "ord_nr": o_nr,
                            "cat_nr": c_nr,
                            "model_code": c_nr.replace('/', '-'),
                            "description": f"Knurls - {desc_line}",
                            # the label printed above this Cat. Nr. column set (e.g. "COARSE LEFT")
                            "variant_label": desc_line,
                            "dimensions_inch": dim_in,
                            "dimensions_mm": dim_m,
                            "box_qty": None,
                            "top_options": None,
                            "colour": None,
                            "no_of_drawers": None,
                            "plug_type": None,
                            "power_source": None,
                            "raw_text": f"{desc_line} {c_nr} {o_nr} {sz}",
                            "source_row_text": f"{desc_line} {c_nr} {o_nr} {sz}",
                        })
        return rows

    # ------------------------------------------------------------------
    # Text-only parser (used by unit tests without a page)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_table_lines(lines: List[str], page: Optional[pymupdf.Page], clip: Optional[pymupdf.Rect]) -> List[Dict[str, Any]]:
        """Parses table lines into rows. With a page and clip, uses the spatial parser."""
        if page is not None and clip is not None:
            return TableExtractor._extract_rows_from_clip(page, clip)

        rows = []
        cat_indices = [i for i, l in enumerate(lines) if re.search(TableExtractor.CAT_PATTERN, l)]
        if not cat_indices:
            cat_indices = [i for i, l in enumerate(lines) if re.search(TableExtractor.ORD_PATTERN, l)]

        header_text = " ".join(lines[:min(5, len(lines))])
        has_ord_column = bool(re.search(r'\bORD(?:\.|\b)', header_text))
        has_box_column = "BOX" in header_text.upper()

        for k, idx in enumerate(cat_indices):
            end_idx = cat_indices[k + 1] if k + 1 < len(cat_indices) else len(lines)
            slice_text = " \n ".join(lines[idx:end_idx]).replace("Î", "×").replace("Ð", "×")

            cat_match = re.search(TableExtractor.CAT_PATTERN, slice_text)
            cat_nr = cat_match.group(1) if cat_match else None
            if cat_nr:
                cat_nr = re.sub(r'^[*º‡\x87Ø\s]+', '', cat_nr)
            ord_match = re.search(TableExtractor.ORD_PATTERN, slice_text)
            ord_nr = ord_match.group(1) if ord_match else None
            if has_ord_column and not ord_nr:
                continue

            # Without page geometry, box quantity is the last standalone number left after removing
            # the codes and dimensions -- only when the header declares a BOX QTY column.
            box_qty = None
            if has_box_column:
                clean_for_box = slice_text
                for d in re.findall(TableExtractor.DIM_PATTERN, slice_text):
                    clean_for_box = clean_for_box.replace(d, " ")
                for token in (ord_nr, cat_nr):
                    if token:
                        clean_for_box = clean_for_box.replace(token, " ")
                box_candidates = re.findall(r'(?<![\w/.\-])(\d{1,4})(?![\w/.\-])', clean_for_box)
                box_qty = int(box_candidates[-1]) if box_candidates else None

            rows.append(TableExtractor._row_attributes(
                attr_text=slice_text, header_text=header_text, header_words=[], attr_words=[],
                anchor_y=0.0, cat_nr=cat_nr, ord_nr=ord_nr, box_qty=box_qty,
            ))
        return rows
