"""Product Builder module.

Combines ordering tables, spatial text blocks, technical specifications,
editorial review notes, and candidate images into strictly validated ProductRecord models.
"""

from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
import pymupdf
import re

from ..validator.schema import ProductRecord, BoundingBox, ProductImageRef, EditorialReviewNote
from ..validator.confidence import calculate_product_confidence, determine_initial_status
from .table_extractor import TableExtractor
from .image_extractor import ImageExtractor
from .printed_titles import PageTitles, table_caption


def _words_in_order(phrase: str, text: str) -> bool:
    """True when every word of `phrase` is printed in `text`, in the same order (a table cell may
    wrap: 'Worklight complete' / 'with tripod' around the size columns)."""
    words, pos = phrase.split(), 0
    tokens = (text or "").split()
    for w in words:
        while pos < len(tokens) and tokens[pos] != w:
            pos += 1
        if pos == len(tokens):
            return False
        pos += 1
    return bool(words)


class ProductBuilder:
    """Builds validated ProductRecord instances from page data."""

    def __init__(self, image_extractor: ImageExtractor):
        self.image_extractor = image_extractor

    def process_page(
        self,
        page: pymupdf.Page,
        source_pdf: str,
        page_number: int,
        extraction_method: str = "native_pdf",
    ) -> List[ProductRecord]:
        """Extracts and builds all products present on the page."""
        mid_x = page.rect.width / 2.0
        full_text = page.get_text("text")

        # Extract printed page labels strictly from top/bottom margins (y < 45 or y > page.rect.height - 45)
        top_words = page.get_text("words", clip=pymupdf.Rect(0, 0, page.rect.width, 45))
        bot_words = page.get_text("words", clip=pymupdf.Rect(0, page.rect.height - 45, page.rect.width, page.rect.height))
        margin_digits = [w[4] for w in top_words + bot_words if w[4].isdigit() and 1 <= int(w[4]) <= 150]
        seen_digits: List[str] = []
        for d in margin_digits:
            if d not in seen_digits:
                seen_digits.append(d)
        catalog_label = "-".join(seen_digits[:2]) if seen_digits else str(page_number)

        # 1. Extract ordering table records
        ordering_rows = TableExtractor.extract_ordering_records(page, source_pdf, page_number)
        
        # 2. Extract candidate images
        candidate_images = self.image_extractor.extract_page_product_images(
            page, source_pdf, page_number
        )

        # Determine whether this page is a single spread product family or dual-split page
        is_unified_spread = (
            len(ordering_rows) > 0
            and all(r["region_half"] == ordering_rows[0]["region_half"] for r in ordering_rows)
            and len(page.search_for("ORDERING INFORMATION")) == 1
        )

        products: List[ProductRecord] = []
        titles = PageTitles(page.parent, source_pdf)

        # Every code on the page: an image labelled with several of them is a family image.
        page_codes = sorted({c for r in ordering_rows for c in (r.get("cat_nr"), r.get("model_code")) if c})

        labelled_blocks = self._assign_labelled_blocks(page, page_codes) if ordering_rows else []

        def tables_in_region(region: str) -> int:
            boxes = {r.get("table_bbox") for r in ordering_rows
                     if region in ("full_spread", "full_page") or r.get("region_half") in (region, "full_page")}
            return len(boxes)

        for row in ordering_rows:
            ord_nr = row.get("ord_nr")
            cat_nr = row.get("cat_nr")
            model_code = row.get("model_code") or (cat_nr.replace('/', '-') if cat_nr else "GROZ-PROD")
            
            # If unified spread, narrative text and images span the full page
            text_region = "full_spread" if is_unified_spread else row.get("region_half", "left")

            # Determine product name & subtitle
            product_name, subtitle, desc, features = self._extract_product_text_details(
                page, model_code, text_region, mid_x
            )

            # Specific override for row description if provided by table (e.g. "Worklight complete with tripod")
            row_description = None
            if row.get("description"):
                if "tripod" in row["description"].lower():
                    product_name = f"{model_code} (With Tripod)"
                    subtitle = row["description"]
                    row_description = row["description"]
                elif not model_code.startswith("LED"):
                    subtitle = row["description"]
                    if not row["description"].startswith("Knurls - "):  # knurl labels: variant_label
                        row_description = row["description"]

            # Decision F (rules 2.2.0): the heading is the title printed for this product's own
            # ordering table, in the catalogue's title type (see printed_titles.py). The old banner
            # and row-text guesses above remain only as a fallback when no printed title is found.
            printed_title = titles.title_for(page_number, row.get("table_bbox"), catalog_label)
            if printed_title:
                subtitle = printed_title["text"]

            # Extract specs for this region
            if text_region in ["full_spread", "full_page"]:
                clip_rect = page.rect
            elif text_region == "left":
                clip_rect = pymupdf.Rect(0, 0, mid_x, page.rect.height)
            else:
                clip_rect = pymupdf.Rect(mid_x, 0, page.rect.width, page.rect.height)

            region_tables = tables_in_region(text_region)
            specs = self._extract_specifications(
                page, clip_rect,
                lighting_context=self._is_lighting_context(cat_nr, page.get_text("text", clip=clip_rect)),
                single_table_region=(region_tables == 1),
            )
            # Capacity / net weight: read from this product's own panel or table area (see
            # _storage_specs_for); never copied from a neighbouring variant's block.
            specs.update(self._storage_specs_for(row, cat_nr, labelled_blocks, clip_rect, region_tables))

            # Printed text that the heading used to carry is kept verbatim (decision F): the table
            # caption above the product's table, and the row's own description cell.
            caption = table_caption(page, row.get("table_bbox"))
            if caption:
                specs["table_caption"] = caption
            if row_description and _words_in_order(row_description, row.get("source_row_text") or ""):
                specs["table_description"] = row_description

            # Special case for circular/diameter products (LED-800 on page 10)
            dim_inch = row.get("dimensions_inch")
            dim_mm = row.get("dimensions_mm")
            editorial_notes: List[EditorialReviewNote] = []

            if not dim_inch and "800" in model_code:
                dia_match = re.search(r'Dia\.\s*\n*(\d+-[0-9/]+"?)\s*\n*\(([\d\s]+mm)\)', full_text)
                if dia_match:
                    # Decision A (approved 14 Oct 2026): the ordering table has no SIZE column, so the
                    # size fields stay empty; the only printed dimension, the diameter callout on the
                    # LED-800 diagram, is recorded verbatim as a specification.
                    callout = f"{dia_match.group(1)} ({dia_match.group(2).strip()})"
                    specs["diameter"] = callout
                    editorial_notes.append(
                        EditorialReviewNote(
                            field_name="dimensions",
                            published_value=f"Dia. {callout}",
                            suspected_issue=(
                                "The ordering table has no SIZE column. The only printed dimension is this diameter "
                                f"callout on the LED-800 diagram (physical page {page_number}), recorded verbatim as "
                                "specifications.diameter."
                            ),
                            suggested_correction=None,
                            source_page_reference=f"{source_pdf} Physical Page {page_number}, Technical Callout",
                            review_status="pending_review",
                        )
                    )

            # Identify known editorial review observations on source values
            if ord_nr == "55050" and cat_nr == "LED/670":
                editorial_notes.append(
                    EditorialReviewNote(
                        field_name="dimensions_mm",
                        published_value="24 x 26 x 13",
                        suspected_issue=(
                            "Upstream unit label mismatch: the catalogue table lists '24 x 26 x 13' under column "
                            "explicitly labeled '(MM)' (suggesting cm; conversion of 9.5 × 10 × 5 in would be ~241 × 254 × 127 mm). "
                            "Technical drawing contains no dimension callouts; unresolved pending technical drawing interpretation."
                        ),
                        suggested_correction=None,
                        source_page_reference=f"{source_pdf} Physical Page 7, Printed Page 11, Table column SIZE (LÐHÐD) (MM)",
                        review_status="pending_review",
                    )
                )
            elif ord_nr == "55077" and cat_nr == "LED/670T":
                editorial_notes.append(
                    EditorialReviewNote(
                        field_name="dimensions_mm",
                        published_value="117 × (122 - 192) × 117",
                        suspected_issue=(
                            "Catalogue discrepancy: the table lists '(INCH)' as '46 × (48 to 75-1/2) × 46' and '(MM)' as "
                            "'117 × (122 - 192) × 117' (suggesting cm). Meanwhile, the technical diagram callout on the same page "
                            "indicates an operational height range of '1m - 1.68m (39-1/2\" - 66\")'. The table values and "
                            "diagram callout conflict and require interpretation against the original technical drawing; "
                            "left unresolved per audit rules."
                        ),
                        suggested_correction=None,
                        source_page_reference=f"{source_pdf} Physical Page 7, Printed Page 11, Table column SIZE (LÐHÐD) (MM)",
                        review_status="pending_review",
                    )
                )
            elif ord_nr == "55119" and cat_nr == "LED/685T":
                editorial_notes.append(
                    EditorialReviewNote(
                        field_name="dimensions_inch",
                        published_value="28-17/64 × 6-27/64 × 19-9/16",
                        suspected_issue=(
                            "Catalogue discrepancy: the printed table lists height as '6-27/64\"' under (INCH) and '1630' "
                            "under (MM). Meanwhile, the technical diagram callout indicates an operational height range of "
                            "0.7m – 1.3m (27-1/2\" – 51\"). The 1630 mm table value and the diagram range require "
                            "interpretation against the original technical drawing; left unresolved per audit rules."
                        ),
                        suggested_correction=None,
                        source_page_reference=f"{source_pdf} Physical Page 9, Printed Page 15, Table column SIZE (LÐHÐD) (INCH)",
                        review_status="pending_review",
                    )
                )
            elif cat_nr in ["LED/616/US", "LED/616/EU"] and not ord_nr:
                editorial_notes.append(
                    EditorialReviewNote(
                        field_name="ord_nr",
                        published_value="[Not in table]",
                        suspected_issue=(
                            "Catalogue omission: the ordering table for LED/616 omits the ORD NR column entirely, "
                            "providing only CAT NR, PLUG TYPE, POWER SOURCE, and dual open/closed dimensions."
                        ),
                        suggested_correction=None,
                        source_page_reference=f"{source_pdf} Physical Page 12, Printed Page 20, Table column ORDERING INFORMATION",
                        review_status="pending_review",
                    )
                )
            elif ord_nr == "62900" and cat_nr in ("EMLTT/CH-25W", "EMLTT/CH-45W"):
                # Decision B (approved 14 Oct 2026): the same note on both variants, without guessing
                # which one the number belongs to.
                editorial_notes.append(
                    EditorialReviewNote(
                        field_name="ord_nr",
                        published_value="62900",
                        suspected_issue=(
                            "Duplicate ORD NR printed in catalogue table: '62900' is printed for both "
                            "EMLTT/CH-25W (face dia. 1”/25mm) and EMLTT/CH-45W (face dia. 1-3/4”/44mm) in the "
                            f"Copper & Hide Mallet table (physical page {page_number}); EMLTT/CH-38W between them is "
                            "printed as 62901. The catalogue does not show which variant this order number belongs "
                            "to; confirmation from GROZ is needed."
                        ),
                        suggested_correction=None,
                        source_page_reference=f"{source_pdf} Physical Page {page_number}, Table column ORD NR.",
                        review_status="pending_review",
                    )
                )
            elif cat_nr == "EPAX-336F" and not ord_nr:
                editorial_notes.append(
                    EditorialReviewNote(
                        field_name="ord_nr",
                        published_value="[Not in table]",
                        suspected_issue=(
                            "Catalogue omission: ordering table for Pulaski Axe EPAX-336F contains "
                            "CAT NR., HEAD WEIGHT, and OVERALL LENGTH columns but omits the ORD NR. column entirely."
                        ),
                        suggested_correction=None,
                        source_page_reference=f"{source_pdf} Physical Page {page_number}, Table column ORD NR.",
                        review_status="pending_review",
                    )
                )

            # Decision D (approved 14 Oct 2026): kg and lb figures printed for the same net weight disagree.
            if cat_nr in ("TCHL/14-10D/2/BL/GRZ", "TCHL/14-10D/2/OR/GRZ") and specs.get("net_weight") == "4 KG (21 LBS)":
                editorial_notes.append(
                    EditorialReviewNote(
                        field_name="net_weight",
                        published_value="4 KG (21 LBS)",
                        suspected_issue="kg and lb figures are inconsistent (4 kg is about 8.8 lb)",
                        suggested_correction=None,
                        source_page_reference=f"{source_pdf} Physical Page {page_number}, capacity block of the TCHL/14-10D/2 panel",
                        review_status="pending_review",
                    )
                )

            # Add plug/power source and tool storage options if present in row
            if row.get("plug_type"):
                specs["plug_type"] = row["plug_type"]
            if row.get("power_source"):
                specs["power_source"] = row["power_source"]
            if row.get("top_options"):
                specs["top_options"] = row["top_options"]
            if row.get("colour"):
                specs["colour"] = row["colour"]
            if row.get("no_of_drawers"):
                specs["no_of_drawers"] = row["no_of_drawers"]
            for key, value in row.get("measured", {}).items():
                specs[key] = value
            if row.get("spring_steel_bars") is not None:
                specs["spring_steel_bars"] = row["spring_steel_bars"]
            if row.get("variant_label"):
                specs["variant_label"] = row["variant_label"]

            # Match images (pass text_region so unified spreads search across whole spread)
            matched_images = self.image_extractor.match_image_to_product(
                candidate_images, model_code, cat_nr, text_region,
                other_codes=page_codes, region_table_count=region_tables,
            )

            # Table bounding box
            t_bbox = row.get("table_bbox")
            bbox = None
            if t_bbox:
                bbox = BoundingBox(
                    x0=round(max(0.0, t_bbox[0]), 2),
                    y0=round(max(0.0, t_bbox[1]), 2),
                    x1=round(min(page.rect.width, max(0.0, t_bbox[2])), 2),
                    y1=round(min(page.rect.height, max(0.0, t_bbox[3])), 2),
                    page_width=round(page.rect.width, 2),
                    page_height=round(page.rect.height, 2),
                )

            # Calculate confidence score
            conf = calculate_product_confidence(
                cat_nr=cat_nr,
                ord_nr=ord_nr,
                product_name=product_name,
                description=desc,
                specifications=specs,
                extraction_method=extraction_method,
                images=matched_images,
            )

            status = determine_initial_status(conf, cat_nr, ord_nr)

            record = ProductRecord(
                product_name=product_name,
                cat_nr=cat_nr,
                ord_nr=ord_nr,
                sub_title=subtitle,
                description=desc,
                features=features,
                specifications=specs,
                dimensions_inch=dim_inch,
                dimensions_mm=dim_mm,
                box_qty=row.get("box_qty"),
                source_pdf=source_pdf,
                physical_page_number=page_number,
                catalog_page_label=catalog_label,
                bounding_box=bbox,
                extraction_method=extraction_method,
                confidence=conf,
                verification_status=status,
                images=matched_images,
                editorial_notes=editorial_notes,
                raw_text_snippet=row.get("raw_text")[:200] if row.get("raw_text") else None,
                source_row_text=row.get("source_row_text"),
            )
            products.append(record)

        return products

    def _extract_product_text_details(
        self, page: pymupdf.Page, model_code: str, text_region: str, mid_x: float
    ) -> Tuple[str, Optional[str], Optional[str], List[str]]:
        """Extracts product title, subtitle, descriptive text and feature bullets."""
        if text_region in ["full_spread", "full_page"]:
            clip = page.rect
        elif text_region == "left":
            clip = pymupdf.Rect(0, 0, mid_x, page.rect.height)
        else:
            clip = pymupdf.Rect(mid_x, 0, page.rect.width, page.rect.height)

        text = page.get_text("text", clip=clip).strip()
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        product_name = model_code
        subtitle = None
        features = []

        # Find headline block in banner region (y in [40, 140])
        banner_rect = pymupdf.Rect(clip.x0, 40, clip.x1, 140)
        banner_text = page.get_text("text", clip=banner_rect).strip()
        banner_lines = [
            l.strip() for l in banner_text.splitlines()
            if l.strip() and not l.strip().isdigit() and not any(k in l.lower() for k in ["groz", "info@", "www.", "estwing"])
        ]
        if banner_lines:
            sub_parts = [l for l in banner_lines if not re.match(r'^(?:LED-\d{3}|[A-Z0-9/\-]+$)', l)]
            if sub_parts:
                subtitle = " ".join(sub_parts[:3])

        # Fallback subtitle from lines
        if not subtitle:
            for line in lines:
                if any(term in line for term in ["Worklight", "Floodlight", "Sitelamp", "SQUARES", "HAMMERS", "ARBORS", "KNURLS", "BLOCK"]) and len(line) < 45:
                    subtitle = line
                    break

        # Extract features marked with a., b., c. or 1., 2., etc. or bullet •
        for line in lines:
            if re.match(r'^(?:[a-f]\.|\d+\.)\s+', line):
                features.append(line)
            elif line.startswith('•') or line.startswith('-'):
                clean_f = line.lstrip('•- \t')
                if clean_f and clean_f not in features:
                    features.append(clean_f)
            elif any(line.startswith(h) for h in ["Single button", "Impact-proof", "Protected against", "Compact and portable", "Drop forged", "Indestructible handle"]):
                features.append(line)

        # Extract clean introductory paragraph at standard lead position (y ~ 190..280)
        lead_rect = pymupdf.Rect(clip.x0 + 40, 180, clip.x0 + 350, 280)
        lead_text = page.get_text("text", clip=lead_rect).strip()
        lead_lines = [
            l.strip() for l in lead_text.splitlines()
            if l.strip() and not any(k in l for k in ["ORDERING", "CAT", "ORD", "www.", "info@"])
        ]
        description = " ".join(lead_lines) if lead_lines else None

        return product_name, subtitle, description, features

    @staticmethod
    def _is_lighting_context(cat_nr: Optional[str], region_text: str) -> bool:
        """Lighting specs (beam, lumens, run time, LED type, battery) only apply to lighting products."""
        return (cat_nr or "").startswith("LED/") or bool(re.search(r'lumen|light output', region_text, re.IGNORECASE))

    # Page-level specification keys and the context each one requires (see _extract_specifications).
    LIGHTING_KEYS = ("battery", "beam_distance", "beam_angle", "led_type", "lumens", "run_time")

    @staticmethod
    def _strip_beam_angle(page: pymupdf.Page, clip: pymupdf.Rect) -> Optional[str]:
        """Beam angle as printed in a lighting page's spec-icon strip, verbatim (e.g. "60˚").

        The catalogue prints no "BEAM ANGLE" text: the strip near the top of the page is a row of icon
        tiles (lumens, run time, beam distance, beam angle) whose values form one line of numbers and
        units ("1000  11 HRS  8 HRS  10M / 32'  60˚", or just "2100  110˚"). A degree value counts only
        when it sits on such a line in the top 30% of the page next to at least one other tile value,
        and the line holds no ordinary words. Degree values in titles or callouts ("270° Swivelling with
        Magnetic Base", "360° Rotation") are not beam angles. Two different strip angles (per-light-mode
        tiles, e.g. GL-10 p35) leave the value empty.
        """
        words = page.get_text("words", clip=clip)
        top = page.rect.height * 0.30
        degree = re.compile(r"\d{1,3}\s*[°˚]")

        def tile_value(t: str) -> bool:
            """Tile values and units, or the certification badges printed at the strip's height."""
            return bool(degree.fullmatch(t) or re.fullmatch(r"[\d.,/()'’\"-]+", t)
                        or re.fullmatch(r"\d+(?:\.\d+)?[A-Za-z]{1,3}['’]?", t)
                        or re.fullmatch(r"I[PK]\d{2}", t, re.IGNORECASE)
                        or t.upper() in ("HRS", "NM", "LM", "MAH", "A", "W", "V", "M", "ROHS", "CE"))

        mid = page.rect.width / 2.0
        side = (lambda o: (o[0] + o[2]) / 2.0 < mid) if page.rect.width > 800 else (lambda o: True)

        found = set()
        for w in words:
            if w[1] >= top or not degree.fullmatch(w[4]):
                continue
            # neighbours on the same visual line and, on a two-page spread, the same page of the spread
            others = [o for o in words if abs(o[1] - w[1]) < 4 and o is not w and side(o) == side(w)]
            # up to two all-capitals tile captions (e.g. "BLUETOOTH") are allowed; mixed-case words are prose
            captions = [o for o in others if re.fullmatch(r"[A-Z]{2,12}", o[4]) and not tile_value(o[4])]
            values = [o for o in others if tile_value(o[4])]
            if values and len(captions) <= 2 and len(values) + len(captions) == len(others):
                found.add(w[4])
        return found.pop() if len(found) == 1 else None

    _LABELLED_SPECS = (
        ("drawer_load_capacity", ("DRAWER", "LOAD", "CAPACITY")),
        ("overall_load_capacity", ("OVERALL", "LOAD", "CAPACITY")),
        ("net_weight", ("NET", "WEIGHT")),
    )
    _KG_LBS = re.compile(r"\d+(?:\.\d+)?\s*KG\s*\(\d+(?:\.\d+)?\s*LBS\)", re.IGNORECASE)

    @staticmethod
    def _labelled_specs_in(page: pymupdf.Page, rect: pymupdf.Rect) -> Dict[str, str]:
        """Labelled capacity/weight values inside `rect`; a key is returned only if exactly one value is found."""
        found = defaultdict(set)
        for b in ProductBuilder._labelled_blocks(page, rect):
            found[b["key"]].add(b["value"])
        return {k: v.pop() for k, v in found.items() if len(v) == 1}

    @staticmethod
    def _labelled_blocks(page: pymupdf.Page, rect: pymupdf.Rect) -> List[Dict[str, Any]]:
        """Capacity/weight blocks: each printed label (e.g. OVERALL LOAD CAPACITY) with the value printed
        directly above it ("225 KG (500 LBS)", "4.5 KG (10 LBS)", possibly wrapped over two lines).
        Value words go to the nearest label on that label line. Returns [{key, value, x, y}].
        """
        words = sorted(page.get_text("words", clip=rect), key=lambda w: (round(w[1]), w[0]))
        cx = lambda w: (w[0] + w[2]) / 2.0
        labels = []
        for key, seq in ProductBuilder._LABELLED_SPECS:
            for w in words:
                if w[4].upper() != seq[0]:
                    continue
                chain = [w]
                for nxt in seq[1:]:
                    cands = [o for o in words if o[4].upper() == nxt and abs(o[1] - chain[-1][1]) < 3
                             and -4 <= o[0] - chain[-1][2] < 20]
                    if not cands:
                        break
                    chain.append(min(cands, key=lambda o: o[0]))
                if len(chain) == len(seq):
                    labels.append((key, chain[0][0], chain[-1][2], w[1]))
        blocks = []
        for key, x0, x1, y in labels:
            line = [l for l in labels if abs(l[3] - y) < 3]
            mine = [o for o in words if y - 24 <= o[1] < y - 1 and x0 - 15 <= cx(o) <= x1 + 15
                    and min(line, key=lambda l: abs((l[1] + l[2]) / 2 - cx(o)))[1:] == (x0, x1, y)]
            text = " ".join(o[4] for o in mine).strip()
            if ProductBuilder._KG_LBS.fullmatch(text):
                blocks.append({"key": key, "value": text, "x": (x0 + x1) / 2.0, "y": y})
        return blocks

    @staticmethod
    def _base_cat(cat_nr: Optional[str]) -> str:
        """Base model of a top-option variant (RTC/27-20/1B/GRZ -> RTC/27-20/1/GRZ), as used for images."""
        return re.sub(r'([1-4])[A-C]/', r'\1/', cat_nr or '')

    @staticmethod
    def _assign_labelled_blocks(page: pymupdf.Page, codes: List[str]) -> List[Dict[str, Any]]:
        """All labelled capacity blocks on the page, each tagged with the product panel it sits in.

        Tool-storage spreads print one panel per variant: the variant's CAT NR alone at the start of a
        line (no ORD number on that line, so it is not a table row), followed lower down by that
        variant's capacity block. A block belongs to the nearest such heading above it in the same
        half page; blocks with no heading above them are left untagged (heading=None).
        """
        mid = page.rect.width / 2.0
        half = lambda w: "L" if (w[0] + w[2]) / 2.0 < mid or page.rect.width <= 800 else "R"
        words = page.get_text("words")
        clean = lambda t: re.sub(r'^[^A-Za-z0-9]+', '', t).rstrip('.,;:')
        headings = []
        for w in words:
            code = clean(w[4])
            if code not in codes:
                continue
            line = [o for o in words if abs(o[1] - w[1]) < 3 and half(o) == half(w)]
            if any(re.fullmatch(r'\d{5}', clean(o[4])) for o in line):
                continue  # a table row, not a panel heading
            if min(line, key=lambda o: o[0]) is not w:
                continue  # the code is mentioned inside a sentence
            headings.append((code, half(w), w[1]))
        blocks = ProductBuilder._labelled_blocks(page, page.rect)
        for b in blocks:
            bh = "L" if b["x"] < mid or page.rect.width <= 800 else "R"
            above = [h for h in headings if h[1] == bh and h[2] < b["y"]]
            b["half"] = bh
            b["heading"] = max(above, key=lambda h: h[2])[0] if above else None
        return blocks

    @staticmethod
    def _storage_specs_for(row: Dict[str, Any], cat_nr: Optional[str], blocks: List[Dict[str, Any]],
                           region: pymupdf.Rect, region_tables: int) -> Dict[str, str]:
        """Capacity specs for one product, from the blocks of its own panel only.

        1. Blocks under a panel heading equal to this product's CAT NR or its base model.
        2. Otherwise untagged blocks in the product's page region -- and, when several tables share the
           region, only blocks inside this product's own table area.
        A key is filled only when exactly one value is found; anything ambiguous stays empty.
        """
        own = [b for b in blocks if b["heading"] and b["heading"] in (cat_nr, ProductBuilder._base_cat(cat_nr))]
        if not own:
            own = [b for b in blocks if b["heading"] is None and region.contains(pymupdf.Point(b["x"], b["y"]))]
            if region_tables > 1:
                tb = pymupdf.Rect(row["table_bbox"]) if row.get("table_bbox") else None
                own = [b for b in own if tb is not None and tb.contains(pymupdf.Point(b["x"], b["y"]))]
        found = defaultdict(set)
        for b in own:
            found[b["key"]].add(b["value"])
        return {k: v.pop() for k, v in found.items() if len(v) == 1}

    def _extract_specifications(self, page: pymupdf.Page, clip: pymupdf.Rect,
                                lighting_context: bool = True, single_table_region: bool = True) -> Dict[str, Any]:
        """Extracts page-level technical specifications from region text.

        These values are printed in the page's feature graphics, not in a product's table row, so
        they are attached only where they cannot belong to a different product:
        - lighting keys (beam angle, lumens, ...) only for lighting products;
        - all page-level keys only when the page region holds a single ordering table, i.e. every
          product in the region is a variant of the one family the graphics describe.
        """
        if not single_table_region:
            return {}
        text = page.get_text("text", clip=clip)
        specs: Dict[str, Any] = {}

        # IP / IK ratings: only when the region shows a single rating. Two different ratings (e.g. an
        # "IP54 COMPLIANT" and an "IP65 COMPLIANT" variant group) cannot be attributed page-wide.
        for key, pattern in (("ip_rating", r'\b(IP\s*[0-9]{2})\b'), ("ik_rating", r'\b(IK\s*[0-9]{2})\b')):
            found = {m.replace(" ", "") for m in re.findall(pattern, text)}
            if len(found) == 1:
                specs[key] = found.pop()

        # Battery / Power
        battery = re.search(r'([0-9.]+\s*V\s+[0-9.]+\s*mAh(?:\s+Li-Ion)?)', text, re.IGNORECASE)
        if battery:
            specs["battery"] = battery.group(1).replace("\n", " ").strip()

        # Beam Distance
        beam = re.search(r'(\d+\s*M\s*\/\s*\d+[\'’])', text)
        if beam:
            specs["beam_distance"] = beam.group(1)

        # Beam Angle: only the value printed in the spec-icon strip (see _strip_beam_angle), verbatim
        angle = self._strip_beam_angle(page, clip)
        if angle:
            specs["beam_angle"] = angle

        # LED Type (e.g. 10W COB, 20W COB, 36W 72 SMD)
        led_type = re.search(r'(\d+\s*W(?:\s+\d+)?\s+(?:COB|SMD))', text, re.IGNORECASE)
        if led_type:
            specs["led_type"] = led_type.group(1)

        # Lumens
        lumen_match = re.search(r'\b([1-4]\d{3})\b(?=\s*(?:Lumens|LUMEN|LUMENS))', text, re.IGNORECASE)
        if not lumen_match:
            lumen_match = re.search(r'(?:LUMEN|LUMENS|Lumens)\s*\n*(\d+)', text, re.IGNORECASE)
        if lumen_match:
            specs["lumens"] = lumen_match.group(1)

        # Operating / Run Time
        runtime_match = re.search(r'(\d+(?:\.\d+)?\s*(?:hours|HRS))\s*(?:at lowest intensity)?', text)
        if runtime_match:
            specs["run_time"] = runtime_match.group(0).strip()

        # Overall / drawer load capacity and net weight are read per product panel in process_page
        # (_storage_specs_for), not page-wide: multi-variant spreads print one block per variant.

        # Steel Gauge (Tool Storage)
        gauge = re.search(r'([0-9.]+\s*mm\s*\([0-9.]+\s*[Gg]auge\))', text, re.IGNORECASE)
        if gauge:
            specs["steel_gauge"] = gauge.group(1)

        # Series (Tool Storage)
        series = re.search(r'(S\d+[A-Z]?\s*Series)', text, re.IGNORECASE)
        if series:
            specs["series"] = series.group(1)

        if not lighting_context:
            for key in self.LIGHTING_KEYS:
                specs.pop(key, None)
        return specs
