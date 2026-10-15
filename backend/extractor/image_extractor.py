"""Product image extraction and spatial association module.

Crops product regions at high resolution, tracks physical bounding boxes,
and enforces evidence-based association without hallucinated image links.

Recovery changes (14 Oct 2026):
- Crop filenames and image IDs carry a slug of the source PDF, so crops from different
  catalogues can never overwrite each other or share an ID.
- Stored file paths always use forward slashes (identical JSON on Windows and Linux).
- Each association states its evidence: direct_product (own code printed beside the image),
  product_family (family/base-model label, shared label, or the single product image beside
  the only ordering table in that region), or unresolved (page/region proximity only).
- Code labels must match as whole codes: LED-670 no longer matches the text "LED-670T".

Rules 2.3.0 (image evidence):
- A code is a label only when it is not a cell of an ordering table: the CAT NR / ORD NR words of the
  table rows next to a picture are excluded (they made "code printed beside the image" true for the
  first rows of a table under a picture and false for the rest).
- Each candidate also records its caption (the words printed directly below it) and its position,
  for the caption and section rules in image_sections.py.
- Each printed word labels one picture only: the nearest (a code under the picture, not at the top
  edge of the one below), never across the fold of a spread. A picture placed inside another
  picture's box keeps the codes printed in its column; where a code lies inside several overlapping
  cut-out boxes, the picture actually drawn next to it (its visible pixels) wins.
- Codes printed in white on a coloured tag: a page tab (page header) labels no picture; a panel
  tag in the page body (tool storage) labels the picture under it, not the series photo above it.
- Codes match as whole codes, segment by segment: "MS/7" is not a label for "MS/7/AL".
- Tall, thin pictures of upright tools (tweezers, scribers: at least 15 pt wide and three times
  as tall) are product pictures, not icons.
- A picture labelled for this product beats one linked only by layout, however large; the layout
  rule ("largest picture in the region") applies only to the region's largest picture and never
  when that picture is labelled for another product.
- Option variants are whole code segments (RTC/27-20/1B/GRZ): FLG/13A/100 and PV/1A are not.
"""

from typing import List, Dict, Any, Optional, Sequence
import os
import re
import pymupdf
from ..validator.schema import BoundingBox, ProductImageRef

_EVIDENCE_RANK = {"direct_product": 0, "product_family": 1, "unresolved": 2}


def _inside(inner: Sequence[float], outer: Sequence[float], tol: float = 2.0) -> bool:
    """`inner` lies within `outer` (x0, y0, x1, y1) and is smaller."""
    return (outer[0] - tol <= inner[0] and outer[1] - tol <= inner[1] and inner[2] <= outer[2] + tol
            and inner[3] <= outer[3] + tol
            and (inner[2] - inner[0]) * (inner[3] - inner[1]) < (outer[2] - outer[0]) * (outer[3] - outer[1]))


def pdf_slug(source_pdf: str) -> str:
    """Short, filename-safe identifier for a source PDF (e.g. 'tools_storage')."""
    stem = os.path.splitext(os.path.basename(source_pdf))[0].lower()
    return re.sub(r'[^a-z0-9]+', '_', stem).strip('_')


def _code_in(code: Optional[str], text: str) -> bool:
    """True if `code` appears in `text` as a whole code (not as the prefix of a longer code)."""
    if not code:
        return False
    # Not part of a longer code either: "MS/7" is not in "MS/7/AL", "LED-670" is not in "LED-670T".
    return re.search(r'(?<![A-Z0-9])(?<![A-Z0-9][/-])' + re.escape(code) + r'(?![A-Z0-9]|[/-][A-Z0-9])', text) is not None


def _norm_word(t: str) -> str:
    return re.sub(r"^[^0-9A-Za-z]+", "", t).rstrip(".,;:")


def table_cell_rects(page: pymupdf.Page, rows: Sequence[Dict[str, Any]]) -> List[pymupdf.Rect]:
    """Where the CAT NR and ORD NR of each ordering-table row are printed (words inside the row's table)."""
    words = page.get_text("words")
    cells = []
    for row in rows:
        bb = row.get("table_bbox")
        if not bb:
            continue
        area = pymupdf.Rect(bb) + (-3, -3, 3, 3)
        hits = lambda code: [w for w in words if code and _norm_word(w[4]) == code and pymupdf.Rect(w[:4]).intersects(area)]
        # One cell per code: the detected table area can be loose and contain a picture label with the
        # same code. The CAT NR cell is the leftmost occurrence (first column); the ORD NR cell is on
        # the same printed line.
        cat = min(hits(row.get("cat_nr")), key=lambda w: w[0], default=None)
        if cat is not None:
            cells.append(pymupdf.Rect(cat[:4]))
        ords = hits(row.get("ord_nr"))
        if ords:
            o = min(ords, key=lambda w: abs(w[1] - cat[1]) if cat is not None else w[0])
            cells.append(pymupdf.Rect(o[:4]))
    return cells


class ImageExtractor:
    """Extracts and verifies product image crops from PDF catalogue pages."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def extract_page_product_images(
        self,
        page: pymupdf.Page,
        source_pdf: str,
        page_number: int,
        dpi: int = 200,
        table_cells: Sequence[pymupdf.Rect] = (),
    ) -> List[Dict[str, Any]]:
        """Extracts candidate product images from page with bounding boxes and nearby labels."""
        candidates = []
        page_rect = page.rect
        mid_x = page_rect.width / 2.0
        slug = pdf_slug(source_pdf)
        words = page.get_text("words")
        in_table = lambda w: any(pymupdf.Rect(w[:4]).intersects(c) for c in table_cells)
        reading = lambda ws: " ".join(w[4] for w in sorted(ws, key=lambda w: (round(w[1]), w[0])))

        for img_info in page.get_images():
            xref = img_info[0]
            smask = img_info[1]
            for r, placement in page.get_image_rects(xref, transform=True):
                # Filter out small decorative icons, buttons, badges, QR codes (< 40pt or area < 5000).
                # Long, thin tools pictured upright (tweezers, scribers) are product pictures: a picture
                # at least 15 pt wide and three times as tall, lying entirely on the page, is kept.
                small = r.width < 40 or r.height < 40 or (r.width * r.height < 5000)
                upright = (r.width >= 15 and r.height >= 3 * r.width and r.width * r.height >= 5000
                           and r.x0 >= 0 and r.x1 <= page_rect.width)
                if small and not upright:
                    continue

                # Exclude header/footer areas (y < 60 or y > 810)
                if r.y1 < 60 or r.y0 > 810:
                    continue

                # Examine nearby text (within 40 points around image boundary)
                nearby_rect = pymupdf.Rect(
                    max(0, r.x0 - 40),
                    max(0, r.y0 - 30),
                    min(page_rect.width, r.x1 + 40),
                    min(page_rect.height, r.y1 + 40),
                )
                nearby_text = page.get_text("text", clip=nearby_rect).strip()
                # Labels may be printed a little further below a picture (codes under gauge pictures).
                label_rect = pymupdf.Rect(nearby_rect.x0, nearby_rect.y0, nearby_rect.x1, min(page_rect.height, r.y1 + 60))
                # Caption: words printed directly below. Labels are assigned after all pictures are known.
                caption_text = reading(w for w in words if r.y1 - 2 <= w[1] <= r.y1 + 22 and w[2] > r.x0 and w[0] < r.x1)

                # Determine spread region
                region = "left" if r.x1 <= mid_x + 30 else ("right" if r.x0 >= mid_x - 30 else "center_spread")

                # Crop high-resolution image from page
                crop_filename = f"{slug}_p{page_number}_xref{xref}_{int(r.x0)}_{int(r.y0)}.png"
                crop_path = os.path.join(self.output_dir, crop_filename)

                # Add 4pt safety padding for aesthetic border
                padded_rect = pymupdf.Rect(
                    max(0, r.x0 - 4),
                    max(0, r.y0 - 4),
                    min(page_rect.width, r.x1 + 4),
                    min(page_rect.height, r.y1 + 4),
                )
                pix = page.get_pixmap(clip=padded_rect, dpi=dpi)
                pix.save(crop_path)

                candidates.append({
                    "xref": xref,
                    "crop_filename": crop_filename,
                    "crop_path": crop_path,
                    "source_pdf": source_pdf,
                    "physical_page_number": page_number,
                    "bounding_box": BoundingBox(
                        x0=round(max(0.0, r.x0), 2),
                        y0=round(max(0.0, r.y0), 2),
                        x1=round(min(page_rect.width, max(0.0, r.x1)), 2),
                        y1=round(min(page_rect.height, max(0.0, r.y1)), 2),
                        page_width=round(page_rect.width, 2),
                        page_height=round(page_rect.height, 2),
                    ),
                    "nearby_text": nearby_text,
                    "label_text": "",
                    "caption_text": caption_text,
                    "rect": (r.x0, r.y0, r.x1, r.y1),
                    "_nearby": label_rect,
                    "_placement": placement,
                    "_smask": smask,
                    "region": region,
                    "area": r.width * r.height,
                    "width": r.width,
                    "height": r.height,
                    "aspect_ratio": r.height / r.width if r.width > 0 else 1.0,
                })

        # Labels: each printed word near a picture belongs to the one nearest picture (a code printed
        # between two pictures labels the closer one, not both). Words that are ordering-table cells
        # are never labels, and on a two-page spread a label never crosses the fold.
        spread = page_rect.width > 900
        half = lambda x0, x1: (x0 + x1) / 2 < mid_x

        def box_gap(w, c):
            x0, y0, x1, y1 = c["rect"]
            dx = max(0.0, x0 - w[2], w[0] - x1)
            dy = max(0.0, y0 - w[3], w[1] - y1)
            return (dx * dx + dy * dy) ** 0.5

        def visible(c):
            """Page points where a cut-out picture (an image with a transparency mask) is actually drawn."""
            if "_visible" not in c:
                pts = None
                if c["_smask"]:
                    try:
                        mask = pymupdf.Pixmap(page.parent, c["_smask"])
                        W, H, n, px = mask.width, mask.height, mask.n, mask.samples
                        step, m = max(1, max(W, H) // 120), c["_placement"]
                        pts = [((u + 0.5) / W * m.a + (v + 0.5) / H * m.c + m.e, (u + 0.5) / W * m.b + (v + 0.5) / H * m.d + m.f)
                               for v in range(0, H, step) for u in range(0, W, step) if px[(v * W + u) * n] > 64]
                    except Exception:
                        pts = None
                c["_visible"] = pts or None
            return c["_visible"]

        def visible_gap(w, c):
            pts = visible(c)
            if not pts:
                return box_gap(w, c)
            return min(((max(0.0, w[0] - x, x - w[2])) ** 2 + (max(0.0, w[1] - y, y - w[3])) ** 2) ** 0.5 for x, y in pts)

        def gap(w, c):
            x0, y0, x1, y1 = c["rect"]
            dx = max(0.0, x0 - w[2], w[0] - x1)
            dy = max(0.0, y0 - w[3], w[1] - y1)
            # A word at (or above) a picture's top edge is more likely the caption of the picture
            # above it: codes are printed under their pictures.
            above = 12.0 if (w[1] + w[3]) / 2 < y0 + 6 else 0.0
            # Between overlapping pictures, the one centred over the word wins (a wide group photo can
            # reach over the caption of the narrow picture next to it).
            off_centre = 0.1 * abs((w[0] + w[2]) / 2 - (x0 + x1) / 2)
            # A picture placed inside another picture's box is a separate item (a group canvas around
            # several tools): a code printed in the inner picture's column belongs to the inner one.
            wx = (w[0] + w[2]) / 2
            outer = 50.0 if any(d is not c and d["rect"][0] <= wx <= d["rect"][2] and _inside(d["rect"], c["rect"])
                                for d in candidates) else 0.0
            return (dx * dx + dy * dy) ** 0.5 + above + off_centre + outer

        # Text printed in white sits on a coloured tag. A page tab (the code tab in the page header,
        # above y 110 pt) names the page's product, not one of its pictures: it labels none. A tag in
        # the page body heads a panel (tool storage): it labels the picture printed on it or in the
        # panel below it (starting within 60 pt under the tag), never the picture above it.
        white = [s["bbox"] for b in page.get_text("dict")["blocks"] for line in b.get("lines", []) for s in line["spans"]
                 if s["color"] == 0xFFFFFF and s["text"].strip()]
        on_white = lambda w: next((sb for sb in white if sb[0] - 1 <= (w[0] + w[2]) / 2 <= sb[2] + 1
                                   and sb[1] - 1 <= (w[1] + w[3]) / 2 <= sb[3] + 1), None)

        owned: Dict[int, List[Any]] = {}
        for w in words:
            if in_table(w):
                continue
            tag = on_white(w)
            if tag and tag[1] < 110:
                continue
            if tag:
                under = [i for i, c in enumerate(candidates)
                         if (box_gap(w, c) == 0 or w[1] - 2 <= c["rect"][1] <= w[3] + 60) and box_gap(w, c) <= 200
                         and (not spread or half(w[0], w[2]) == half(c["rect"][0], c["rect"][2]))]
                if under:
                    owned.setdefault(min(under, key=lambda i: (box_gap(w, candidates[i]), candidates[i]["area"])), []).append(w)
                continue
            near = [i for i, c in enumerate(candidates) if pymupdf.Rect(w[:4]).intersects(c["_nearby"])
                    and (not spread or half(w[0], w[2]) == half(c["rect"][0], c["rect"][2]))]
            if near:
                inside = [i for i in near if box_gap(w, candidates[i]) <= 2]
                if len(inside) > 1 and any(visible(candidates[i]) for i in inside):
                    # The word is printed inside several overlapping picture boxes (cut-outs set
                    # diagonally): it labels the picture actually drawn next to it (visible pixels).
                    best = min(inside, key=lambda i: (visible_gap(w, candidates[i]), candidates[i]["area"]))
                else:
                    best = min(near, key=lambda i: (gap(w, candidates[i]), candidates[i]["area"]))
                owned.setdefault(best, []).append(w)
        for i, c in enumerate(candidates):
            c["label_text"] = reading(owned.get(i, []))
            for k in ("_nearby", "_placement", "_smask", "_visible"):
                c.pop(k, None)
        return candidates

    def match_image_to_product(
        self,
        candidate_images: List[Dict[str, Any]],
        product_code: str,
        cat_nr: Optional[str],
        product_region: str,
        other_codes: Optional[Sequence[str]] = None,
        region_table_count: Optional[int] = None,
    ) -> List[ProductImageRef]:
        """Matches at most one candidate image to a product and states the evidence for it.

        Never associates an image if no spatial or label link exists. Candidates linked only by
        page/region proximity are returned as `unresolved`, never as the product's own image.
        """
        is_lighting = (cat_nr or "").startswith("LED") or product_code.startswith("LED")
        is_tripod_variant = (
            ("tripod" in (cat_nr or "").lower())
            or ("tripod" in product_code.lower())
            or (is_lighting and bool(re.search(r'LED/\d{3}T\b', cat_nr or '')))
            or (is_lighting and bool(re.search(r'LED-\d{3}T\b', product_code or '')))
            or ("612" in (cat_nr or ""))
        )

        has_tripod_on_page = any(
            any(w in c["nearby_text"].lower() for w in ["tripod", "telescopic", "0.8m - 1.72m", "1m - 1.68m", "0.7m – 1.3m"])
            for c in candidate_images
        )

        # Base model for tool storage option variants (e.g. RTC/42-20/1B/GRZ -> RTC/42-20/1/GRZ); the
        # option is a whole code segment, so FLG/13A/100 and PV/1-4A/ST are not variants.
        base_cat_nr = re.sub(r'(?<=/)([1-4])[A-C]/', r'\1/', cat_nr or '')
        base_code = re.sub(r'(?<=-)([1-4])[A-C]-', r'\1-', product_code or '')
        own_codes = {c for c in (product_code, cat_nr, base_code, base_cat_nr) if c}
        others = [c for c in (other_codes or []) if c and c not in own_codes]
        # Plug variants (EU/US) and tool storage option variants (a base model with a 1A-4C option).
        # Codes like PV/1A (pin vices) end the same way but are not variants of another code.
        is_option_variant = "/" in (cat_nr or "") and (
            base_cat_nr != cat_nr or any(v in (cat_nr or "") for v in ["EU", "US"])
        )

        # Sort candidate images by area descending so primary hero images are evaluated first
        sorted_candidates = sorted(candidate_images, key=lambda c: c["area"], reverse=True)

        accepted = []
        hero_seen = False  # only the largest picture in the region is its layout hero
        for order, cand in enumerate(sorted_candidates):
            nearby = cand["nearby_text"]
            labels = cand.get("label_text", nearby)  # codes count only when they are not table cells
            page_w = cand["bounding_box"].page_width
            is_single_page = page_w <= 800

            same_region = (
                (cand["region"] == product_region)
                or (product_region in ["center_spread", "full_spread", "full_page"])
                or (cand["region"] in ["center_spread", "full_spread", "full_page"])
                or (is_single_page and len(candidate_images) == 1)
            )
            ar = cand.get("aspect_ratio", (cand["height"] / cand["width"]) if cand.get("width", 0) > 0 else 1.0)
            has_tripod_text = (
                any(w in nearby.lower() for w in ["tripod", "telescopic stand", "tripod stand", "complete with tripod"])
                or ("telescopic" in nearby.lower() and any(u in nearby.lower() for u in ["m -", "m –", "inch"]))
            )
            is_vertical_pole = ar > 1.8

            exact = _code_in(product_code, labels) or _code_in(cat_nr, labels)
            family = (not exact) and (
                (base_code != product_code and _code_in(base_code, labels))
                or (base_cat_nr != cat_nr and _code_in(base_cat_nr, labels))
            )
            tripod_evidence = False
            min_hero_area = 5500 if is_single_page else 20000
            region_hero = False

            score = 0.0
            if exact or family:
                score += 0.5

            # Strict Tripod Separation (lighting only)
            if is_tripod_variant:
                # Tripod model MUST be a tripod image
                if has_tripod_text:
                    score += 0.7
                    tripod_evidence = True
                elif is_vertical_pole and same_region and has_tripod_on_page:
                    score += 0.5
                    tripod_evidence = True
                else:
                    # Non-tripod image cannot match tripod SKU
                    continue
            else:
                # Standalone lighting model must NEVER match a tripod image
                if is_lighting and has_tripod_on_page and (has_tripod_text or is_vertical_pole):
                    continue
                # Primary product image in region (scaled for single-page portrait vs spread)
                if same_region and cand["area"] >= min_hero_area and not hero_seen:
                    score += 0.5
                    region_hero = hero_seen = True

            if same_region:
                score += 0.2
            if cand["area"] > 40000:
                score += 0.1

            # Only accept if evidence score meets the threshold (score >= 0.5)
            if score < 0.5:
                continue

            other_labelled = [o for o in others if _code_in(o, labels)]
            code_shown = cat_nr if _code_in(cat_nr, labels) else product_code
            # A picture labelled only for other products shows those products: layout alone never
            # makes it this product's picture, and no smaller picture takes its place (rules 2.3.0).
            if region_hero and other_labelled and not (exact or family):
                region_hero = False
            if exact and not other_labelled and not is_option_variant:
                assoc, evidence = "direct_product", f"product code {code_shown} printed beside the image"
            elif exact and other_labelled:
                assoc, evidence = "product_family", (
                    f"image labelled with {code_shown} and other product codes ({', '.join(sorted(other_labelled)[:3])})"
                )
            elif exact:
                assoc, evidence = "product_family", f"image labelled {code_shown}, shared by its plug/option variants"
            elif family:
                base_shown = base_cat_nr if _code_in(base_cat_nr, labels) else base_code
                assoc, evidence = "product_family", f"base model {base_shown} printed beside the image (this is a variant)"
            elif tripod_evidence:
                assoc, evidence = "product_family", "tripod model image identified by nearby tripod text (no code label)"
            elif region_hero and region_table_count == 1:
                assoc, evidence = "product_family", (
                    "largest product image in the same page region as the only ordering table there (layout evidence)"
                )
            else:
                assoc, evidence = "unresolved", "only page/region proximity links this image to the product"

            # Within the same association type, a picture labelled for this product (its code, base
            # model or tripod text) beats one linked only by layout, however large.
            labelled = exact or family or tripod_evidence
            accepted.append((_EVIDENCE_RANK[assoc], 0 if labelled else 1, order, cand, assoc, evidence, score))

        if not accepted:
            return []
        _, _, _, cand, assoc, evidence, score = min(accepted, key=lambda t: (t[0], t[1], t[2]))
        return [self.make_ref(cand, assoc, evidence, score)]

    def make_ref(self, cand: Dict[str, Any], assoc: str, evidence: str, score: float) -> ProductImageRef:
        return ProductImageRef(
            image_id=os.path.splitext(cand["crop_filename"])[0],
            file_path=os.path.relpath(cand["crop_path"], os.path.dirname(self.output_dir)).replace(os.sep, "/"),
            source_pdf=cand["source_pdf"],
            physical_page_number=cand["physical_page_number"],
            bounding_box=cand["bounding_box"],
            association_type=assoc,
            evidence=evidence,
            confidence=round(min(1.0, score), 2),
            caption_or_label=nearby[:100] if (nearby := cand["nearby_text"]) else None,
        )
