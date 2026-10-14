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
"""

from typing import List, Dict, Any, Optional, Sequence
import os
import re
import pymupdf
from ..validator.schema import BoundingBox, ProductImageRef

_EVIDENCE_RANK = {"direct_product": 0, "product_family": 1, "unresolved": 2}


def pdf_slug(source_pdf: str) -> str:
    """Short, filename-safe identifier for a source PDF (e.g. 'tools_storage')."""
    stem = os.path.splitext(os.path.basename(source_pdf))[0].lower()
    return re.sub(r'[^a-z0-9]+', '_', stem).strip('_')


def _code_in(code: Optional[str], text: str) -> bool:
    """True if `code` appears in `text` as a whole code (not as the prefix of a longer code)."""
    if not code:
        return False
    return re.search(r'(?<![A-Z0-9])' + re.escape(code) + r'(?![A-Z0-9])', text) is not None


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
    ) -> List[Dict[str, Any]]:
        """Extracts candidate product images from page with bounding boxes and nearby labels."""
        candidates = []
        page_rect = page.rect
        mid_x = page_rect.width / 2.0
        slug = pdf_slug(source_pdf)

        for img_info in page.get_images():
            xref = img_info[0]
            rects = page.get_image_rects(xref)
            for r in rects:
                # Filter out small decorative icons, buttons, badges, QR codes (< 40pt or area < 5000)
                if r.width < 40 or r.height < 40 or (r.width * r.height < 5000):
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
                    "region": region,
                    "area": r.width * r.height,
                    "width": r.width,
                    "height": r.height,
                    "aspect_ratio": r.height / r.width if r.width > 0 else 1.0,
                })

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

        # Base model for tool storage option variants (e.g. RTC/42-20/1B/GRZ -> RTC/42-20/1/GRZ)
        base_cat_nr = re.sub(r'([1-4])[A-C]/', r'\1/', cat_nr or '')
        base_code = re.sub(r'([1-4])[A-C]-', r'\1-', product_code or '')
        own_codes = {c for c in (product_code, cat_nr, base_code, base_cat_nr) if c}
        others = [c for c in (other_codes or []) if c and c not in own_codes]
        is_option_variant = "/" in (cat_nr or "") and any(
            v in (cat_nr or "") for v in ["EU", "US", "/1A", "/1B", "/1C", "/2A", "/2B", "/2C", "/3A", "/3B", "/3C", "/4A", "/4B", "/4C"]
        )

        # Sort candidate images by area descending so primary hero images are evaluated first
        sorted_candidates = sorted(candidate_images, key=lambda c: c["area"], reverse=True)

        accepted = []
        for order, cand in enumerate(sorted_candidates):
            nearby = cand["nearby_text"]
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

            exact = _code_in(product_code, nearby) or _code_in(cat_nr, nearby)
            family = (not exact) and (
                (base_code != product_code and _code_in(base_code, nearby))
                or (base_cat_nr != cat_nr and _code_in(base_cat_nr, nearby))
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
                if same_region and cand["area"] >= min_hero_area:
                    score += 0.5
                    region_hero = True

            if same_region:
                score += 0.2
            if cand["area"] > 40000:
                score += 0.1

            # Only accept if evidence score meets the threshold (score >= 0.5)
            if score < 0.5:
                continue

            other_labelled = [o for o in others if _code_in(o, nearby)]
            code_shown = cat_nr if _code_in(cat_nr, nearby) else product_code
            if exact and not other_labelled and not is_option_variant:
                assoc, evidence = "direct_product", f"product code {code_shown} printed beside the image"
            elif exact and other_labelled:
                assoc, evidence = "product_family", (
                    f"image labelled with {code_shown} and other product codes ({', '.join(sorted(other_labelled)[:3])})"
                )
            elif exact:
                assoc, evidence = "product_family", f"image labelled {code_shown}, shared by its plug/option variants"
            elif family:
                base_shown = base_cat_nr if _code_in(base_cat_nr, nearby) else base_code
                assoc, evidence = "product_family", f"base model {base_shown} printed beside the image (this is a variant)"
            elif tripod_evidence:
                assoc, evidence = "product_family", "tripod model image identified by nearby tripod text (no code label)"
            elif region_hero and region_table_count == 1:
                assoc, evidence = "product_family", (
                    "largest product image in the same page region as the only ordering table there (layout evidence)"
                )
            else:
                assoc, evidence = "unresolved", "only page/region proximity links this image to the product"

            accepted.append((_EVIDENCE_RANK[assoc], order, cand, assoc, evidence, score))

        if not accepted:
            return []
        _, _, cand, assoc, evidence, score = min(accepted, key=lambda t: (t[0], t[1]))
        return [
            ProductImageRef(
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
        ]
