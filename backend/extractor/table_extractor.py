"""Table Extractor for GROZ Product Catalogues.

Extracts ordering matrices (CAT NR, ORD NR, DESCRIPTION, DIMENSIONS, BOX QTY)
and specification mode grids with strict spatial boundaries across both
two-page spreads (Batch 1) and single-page portrait catalogues (Batch 2).
"""

from typing import List, Dict, Any, Optional
import pymupdf
import re


class TableExtractor:
    """Extracts structured tables from PDF pages using spatial coordinates and text layout."""

    CAT_PATTERN = (
        r'(?:[*º‡\x87Ø]\s*)?((?=[A-Z0-9/\-.]*[A-Z])('
        r'(?:LED|RTC|RTCL|TCH|TCHL|TCHH|TCHS|MTB|SRC|WBN)/[A-Z0-9/\-.]+|'
        r'E[A-Z0-9]{1,4}(?:[/-][A-Z0-9/\-.]+)+|'
        r'E[A-Z0-9]{1,4}-[A-Z0-9/\-.]+|'
        r'[A-Z0-9]{2,8}(?:[/-][A-Z0-9/\-.]+)+|'
        r'[A-Z]{2,6}/\d+(?:[A-Z0-9/\-.]+)?|'
        r'[A-Z]{2,6}-[A-Z0-9/\-.]+'
        r'))'
    )
    ORD_PATTERN = r'(?<![\.\d])(\d{5})(?![\.\d])'

    @staticmethod
    def extract_ordering_records(page: pymupdf.Page, source_pdf: str, page_number: int) -> List[Dict[str, Any]]:
        """Finds ordering tables on the page (spread or single-page) and extracts structured rows."""
        width = page.rect.width
        height = page.rect.height
        mid_x = width / 2.0
        ordering_records: List[Dict[str, Any]] = []

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

                rows = TableExtractor._extract_rows_from_clip(page, table_clip)
                for row in rows:
                    row["source_pdf"] = source_pdf
                    row["physical_page_number"] = page_number
                    row["region_half"] = half
                    row["table_bbox"] = (table_clip.x0, table_clip.y0, table_clip.x1, table_clip.y1)
                    ordering_records.append(row)

            return ordering_records

        # ---------------------------------------------------------
        # Case B: Single portrait page layout (Batch 2: width <= 800 pt)
        # ---------------------------------------------------------
        # Check for Knurls matrix page (Page 68 of Precision Catalogue)
        knurls_rects = page.search_for("CAT. & ORDERING NR.")
        if knurls_rects:
            knurl_clip = pymupdf.Rect(20, max(0, knurls_rects[0].y0 - 20), width - 20, height - 30)
            rows = TableExtractor._parse_knurl_matrix_page(page, knurl_clip)
            for row in rows:
                row["source_pdf"] = source_pdf
                row["physical_page_number"] = page_number
                row["region_half"] = "full_page"
                row["table_bbox"] = (knurl_clip.x0, knurl_clip.y0, knurl_clip.x1, knurl_clip.y1)
                ordering_records.append(row)
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
                rows = TableExtractor._extract_rows_from_clip(page, clip)
                for row in rows:
                    row["source_pdf"] = source_pdf
                    row["physical_page_number"] = page_number
                    row["region_half"] = "full_page"
                    row["table_bbox"] = (clip.x0, clip.y0, clip.x1, clip.y1)
                    ordering_records.append(row)
            return ordering_records

        # If only 1 CAT header exists on page:
        if len(cat_headers) == 1:
            ch = cat_headers[0]
            clip = pymupdf.Rect(20, max(0, ch[1] - 15), width - 20, height - 30)
            rows = TableExtractor._extract_rows_from_clip(page, clip)
            for row in rows:
                row["source_pdf"] = source_pdf
                row["physical_page_number"] = page_number
                row["region_half"] = "full_page"
                row["table_bbox"] = (clip.x0, clip.y0, clip.x1, clip.y1)
                ordering_records.append(row)
            return ordering_records

        # Multiple CAT headers: Partition by left and right columns
        left_headers = sorted([h for h in cat_headers if h[0] < mid_x], key=lambda h: h[1])
        right_headers = sorted([h for h in cat_headers if h[0] >= mid_x], key=lambda h: h[1])

        # Left column tables
        for i, h in enumerate(left_headers):
            y_top = max(0, h[1] - 15)
            y_bottom = (left_headers[i + 1][1] - 10) if (i + 1 < len(left_headers)) else (height - 30)
            x_right = (mid_x - 5) if right_headers else (width - 20)
            clip = pymupdf.Rect(20, y_top, x_right, y_bottom)
            rows = TableExtractor._extract_rows_from_clip(page, clip)
            for row in rows:
                row["source_pdf"] = source_pdf
                row["physical_page_number"] = page_number
                row["region_half"] = "left"
                row["table_bbox"] = (clip.x0, clip.y0, clip.x1, clip.y1)
                ordering_records.append(row)

        # Right column tables
        for i, h in enumerate(right_headers):
            y_top = max(0, h[1] - 15)
            y_bottom = (right_headers[i + 1][1] - 10) if (i + 1 < len(right_headers)) else (height - 30)
            clip = pymupdf.Rect(mid_x + 5, y_top, width - 20, y_bottom)
            rows = TableExtractor._extract_rows_from_clip(page, clip)
            for row in rows:
                row["source_pdf"] = source_pdf
                row["physical_page_number"] = page_number
                row["region_half"] = "right"
                row["table_bbox"] = (clip.x0, clip.y0, clip.x1, clip.y1)
                ordering_records.append(row)

        return ordering_records

    @staticmethod
    def _extract_rows_from_clip(page: pymupdf.Page, clip: pymupdf.Rect) -> List[Dict[str, Any]]:
        """Extracts spatial text lines from a table clip box and parses them into rows."""
        words = page.get_text("words", clip=clip)
        words.sort(key=lambda w: (w[1], w[0]))

        spatial_lines: List[List[Any]] = []
        curr_y: Optional[float] = None
        curr_line: List[Any] = []
        for w in words:
            if curr_y is None or abs(w[1] - curr_y) < 4.0:
                curr_line.append(w)
                curr_y = w[1] if curr_y is None else (curr_y + w[1]) / 2.0
            else:
                spatial_lines.append(sorted(curr_line, key=lambda x: x[0]))
                curr_line = [w]
                curr_y = w[1]
        if curr_line:
            spatial_lines.append(sorted(curr_line, key=lambda x: x[0]))

        lines = [" ".join([w[4] for w in lw]) for lw in spatial_lines]
        table_text = page.get_text("text", clip=clip).strip()

        rows = TableExtractor._parse_table_lines(lines, page, clip)
        for r in rows:
            r["raw_text"] = table_text
        return rows

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
                            "dimensions_inch": dim_in,
                            "dimensions_mm": dim_m,
                            "box_qty": None,
                            "top_options": None,
                            "colour": None,
                            "no_of_drawers": None,
                            "plug_type": None,
                            "power_source": None,
                            "raw_text": f"{desc_line} {c_nr} {o_nr} {sz}",
                        })
        return rows

    @staticmethod
    def _parse_table_lines(lines: List[str], page: Optional[pymupdf.Page], clip: Optional[pymupdf.Rect]) -> List[Dict[str, Any]]:
        """Parses lines within the ordering table clipping box into structured rows."""
        rows = []
        cat_indices = [i for i, l in enumerate(lines) if re.search(TableExtractor.CAT_PATTERN, l)]

        if not cat_indices:
            cat_indices = [i for i, l in enumerate(lines) if re.search(TableExtractor.ORD_PATTERN, l)]

        column_box_qtys = []
        if page and clip:
            words = page.get_text("words", clip=clip)
            qty_words = [w for w in words if "QTY" in w[4]]
            for qw in qty_words:
                col_digits = [
                    int(w[4]) for w in sorted(words, key=lambda x: x[1])
                    if abs(w[0] - qw[0]) < 22 and qw[1] < w[1] and w[4].isdigit() and int(w[4]) in [1, 2, 4, 6, 8, 10, 12, 13, 15, 20, 25, 27, 36, 50, 75, 80, 100, 150, 200]
                ]
                column_box_qtys.extend(col_digits)

        header_text = " ".join(lines[:min(5, len(lines))])
        has_ord_column = bool(re.search(r'\bORD(?:\.|\b)', header_text))

        for k, idx in enumerate(cat_indices):
            end_idx = cat_indices[k + 1] if k + 1 < len(cat_indices) else len(lines)
            slice_lines = lines[idx:end_idx]
            slice_text = " \n ".join(slice_lines).replace("Î", "×").replace("Ð", "×")

            # Extract CAT NR
            cat_match = re.search(TableExtractor.CAT_PATTERN, slice_text)
            cat_nr = cat_match.group(1) if cat_match else None
            if cat_nr:
                cat_nr = re.sub(r'^[*º‡\x87Ø\s]+', '', cat_nr)

            # Extract ORD NR (5 digits)
            ord_match = re.search(TableExtractor.ORD_PATTERN, slice_text)
            ord_nr = ord_match.group(1) if ord_match else None

            # If the table explicitly has an ORD NR column but this slice has no ORD NR, skip it
            if has_ord_column and not ord_nr:
                continue

            # Identify model code e.g. LED-550 from LED/550 or RTC-27-10D-1
            model_code = cat_nr.replace('/', '-') if cat_nr else None
            if model_code and '/' in model_code:
                model_code = model_code.split('/')[0]

            # Head Weight (hammers)
            head_weight = None
            hw_match = re.search(r'(\d+(?:\.\d+)?\s*(?:lb|lbs|kg|g)(?:\s*/\s*[0-9.]+\s*(?:kg|lb|lbs|g))?)', slice_text, re.IGNORECASE)
            if hw_match:
                head_weight = hw_match.group(1).strip()

            # Overall Length (hammers)
            overall_length = None
            ol_match = re.search(r'(\d+(?:\.\d+)?\s*(?:”|"|inch|in)(?:\s*/\s*[0-9.]+\s*mm)?)', slice_text, re.IGNORECASE)
            if ol_match:
                overall_length = ol_match.group(1).strip()

            # Spring Steel Bars (hammers)
            spring_steel_bars = None
            if "SPRING" in header_text:
                for sl in slice_lines:
                    sb_m = re.search(r'\b([246])\s*$', sl.strip())
                    if sb_m:
                        spring_steel_bars = int(sb_m.group(1))
                        break

            # Top Options (tool storage)
            top_opt = None
            for opt in ["Rubberized Mat", "Thermofoam", "Wooden", "Stainless Steel"]:
                if opt.lower() in slice_text.lower():
                    top_opt = opt
                    break

            # Colour (tool storage)
            colour = None
            for col in ["Classic Black", "Cool Grey", "Bossy Blue", "Fiery Red", "Royal Purple", "Aqua Lux", "Vibrant Orange"]:
                if col.lower() in slice_text.lower():
                    colour = col
                    break

            # Find dimension entries including range/telescopic heights e.g. "46 × (48 to 75-1/2) × 46"
            dim_pattern = (
                r'(\b\d+(?:-[0-9/]+)?(?:\.\d+)?[^\S\n]*×[^\S\n]*(?:\([^)]+\)|[0-9./\-]+)[^\S\n]*×[^\S\n]*[0-9./\-]+|'
                r'\b\d+(?:-[0-9/]+)?(?:\.\d+)?[^\S\n]*(?:×|x)[^\S\n]*[0-9./\-]+(?:[^\S\n]*(?:×|x)[^\S\n]*[0-9./\-]+)?)'
            )
            dims = re.findall(dim_pattern, slice_text)
            dim_inch = dims[0].strip() if len(dims) > 0 else None
            dim_mm = dims[1].strip() if len(dims) > 1 else None

            # Box Quantity: prioritize column alignment, fallback to trailing standalone digit after dimension removal
            box_qty = None
            if k < len(column_box_qtys):
                box_qty = column_box_qtys[k]
            else:
                clean_for_box = slice_text
                for d in dims:
                    clean_for_box = clean_for_box.replace(d, " ")
                if ord_nr:
                    clean_for_box = clean_for_box.replace(ord_nr, " ")
                if top_opt:
                    clean_for_box = clean_for_box.replace(top_opt, " ")
                if colour:
                    clean_for_box = clean_for_box.replace(colour, " ")
                if head_weight:
                    clean_for_box = clean_for_box.replace(head_weight, " ")
                if overall_length:
                    clean_for_box = clean_for_box.replace(overall_length, " ")
                if spring_steel_bars is not None:
                    clean_for_box = re.sub(rf'\b{spring_steel_bars}\b', ' ', clean_for_box)
                # Strip fractional annotations e.g. 7-7/8" or 1/2"
                clean_for_box = re.sub(r'\b\d+-[0-9/]+"?|\b[0-9/]+"\b', ' ', clean_for_box)
                box_candidates = [
                    int(m) for m in re.findall(r'\b([1-9]|10|12|13|15|20|25|27|36|50|75|80|100|150|200)\b', clean_for_box)
                ]
                box_qty = box_candidates[-1] if box_candidates else None

            # Drawer count if DRAWER is in header
            no_drawers = None
            if "DRAWER" in header_text:
                clean_for_dr = slice_text
                if ord_nr:
                    clean_for_dr = clean_for_dr.replace(ord_nr, " ")
                if cat_nr:
                    clean_for_dr = clean_for_dr.replace(cat_nr, " ")
                if box_qty is not None:
                    clean_for_dr = re.sub(rf'\b{box_qty}\b', ' ', clean_for_dr)
                dr_candidates = [int(m) for m in re.findall(r'\b([2-9]|10)\b', clean_for_dr)]
                if dr_candidates:
                    no_drawers = dr_candidates[0]

            # Description tokens
            desc = None
            if "tripod" in slice_text.lower():
                desc = "Worklight complete with tripod" if "worklight" in slice_text.lower() else "Floodlight complete with tripod"
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

            # Plug & Power Source
            plug_type = None
            power_source = None
            if "EU" in (cat_nr or "") or "EU Pin" in slice_text or "220V" in slice_text:
                plug_type = "EU"
                power_source = "220V AC, 50Hz"
            elif "US" in (cat_nr or "") or "US Pin" in slice_text or "110V" in slice_text:
                plug_type = "US"
                power_source = "110V AC, 60Hz"

            rows.append({
                "ord_nr": ord_nr,
                "cat_nr": cat_nr,
                "model_code": model_code,
                "description": desc,
                "dimensions_inch": dim_inch,
                "dimensions_mm": dim_mm,
                "box_qty": box_qty,
                "head_weight": head_weight,
                "overall_length": overall_length,
                "spring_steel_bars": spring_steel_bars,
                "top_options": top_opt,
                "colour": colour,
                "no_of_drawers": no_drawers,
                "plug_type": plug_type,
                "power_source": power_source,
            })

        return rows
