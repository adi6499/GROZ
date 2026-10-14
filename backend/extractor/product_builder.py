"""Product Builder module.

Combines ordering tables, spatial text blocks, technical specifications,
editorial review notes, and candidate images into strictly validated ProductRecord models.
"""

from typing import List, Dict, Any, Optional, Tuple
import pymupdf
import re

from ..validator.schema import ProductRecord, BoundingBox, ProductImageRef, EditorialReviewNote
from ..validator.confidence import calculate_product_confidence, determine_initial_status
from .table_extractor import TableExtractor
from .image_extractor import ImageExtractor


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

        # Every code on the page: an image labelled with several of them is a family image.
        page_codes = sorted({c for r in ordering_rows for c in (r.get("cat_nr"), r.get("model_code")) if c})

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
            if row.get("description"):
                if "tripod" in row["description"].lower():
                    product_name = f"{model_code} (With Tripod)"
                    subtitle = row["description"]
                elif not model_code.startswith("LED"):
                    subtitle = row["description"]

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

            # Special case for circular/diameter products (LED-800 on page 10)
            dim_inch = row.get("dimensions_inch")
            dim_mm = row.get("dimensions_mm")
            editorial_notes: List[EditorialReviewNote] = []

            if not dim_inch and "800" in model_code:
                dia_match = re.search(r'Dia\.\s*\n*(\d+-[0-9/]+"?)\s*\n*\(([\d\s]+mm)\)', full_text)
                if dia_match:
                    dim_inch = f"{dia_match.group(1)} (Dia.)"
                    dim_mm = f"{dia_match.group(2)} (Dia.)"
                    editorial_notes.append(
                        EditorialReviewNote(
                            field_name="dimensions_inch",
                            published_value="[Not in table]",
                            suspected_issue="Ordering table omitted SIZE column for circular cable reel worklight. Dimension extracted from graphic callout.",
                            suggested_correction=f"{dim_inch} / {dim_mm}",
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
            elif ord_nr == "62900" and cat_nr == "EMLTT/CH-45W":
                editorial_notes.append(
                    EditorialReviewNote(
                        field_name="ord_nr",
                        published_value="62900",
                        suspected_issue=(
                            "Duplicate ORD NR printed in catalogue table: '62900' is printed for both "
                            "EMLTT/CH-25W (1\" dia) and EMLTT/CH-45W (1-3/4\" dia). Suspected typographical "
                            "error in published catalogue; likely intended as 62902 following sequence, pending human review."
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
            if row.get("head_weight"):
                specs["head_weight"] = row["head_weight"]
            if row.get("overall_length"):
                specs["overall_length"] = row["overall_length"]
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

        # Beam Angle
        angle = re.search(r'(\d+)\s*[°˚]', text)
        if angle:
            specs["beam_angle"] = f"{angle.group(1)}°"

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

        # Overall Load Capacity (Tool Storage)
        olc = re.search(r'(\d+\s*KG\s*\(\d+\s*LBS\))\s*\n*OVERALL LOAD CAPACITY', text, re.IGNORECASE)
        if olc:
            specs["overall_load_capacity"] = olc.group(1)

        # Drawer Load Capacity (Tool Storage)
        dlc = re.search(r'(\d+\s*KG\s*\(\d+\s*LBS\))\s*\n*DRAWER LOAD CAPACITY', text, re.IGNORECASE)
        if dlc:
            specs["drawer_load_capacity"] = dlc.group(1)

        # Net Weight (Tool Storage)
        nw = re.search(r'(\d+\s*KG\s*\(\d+\s*LBS\))\s*\n*NET WEIGHT', text, re.IGNORECASE)
        if nw:
            specs["net_weight"] = nw.group(1)

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
