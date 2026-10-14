"""Product image extraction and spatial association module.

Crops product regions at high resolution, tracks physical bounding boxes,
and enforces evidence-based association without hallucinated image links.
"""

from typing import List, Dict, Any, Optional
import os
import pymupdf
from ..validator.schema import BoundingBox, ProductImageRef


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
                crop_filename = f"p{page_number}_xref{xref}_{int(r.x0)}_{int(r.y0)}.png"
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
    ) -> List[ProductImageRef]:
        """Strictly matches candidate images to a product record based on spatial and label evidence.

        Never associates an image if no spatial or label link exists.
        """
        matched_refs = []
        import re
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

        # Sort candidate images by area descending so primary hero images are evaluated first
        sorted_candidates = sorted(candidate_images, key=lambda c: c["area"], reverse=True)

        for cand in sorted_candidates:
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

            score = 0.0
            assoc_type = "unverified"

            # Direct label or model code match
            if product_code in nearby or (cat_nr and cat_nr in nearby):
                score += 0.5
                assoc_type = "direct_hero"
            elif (base_code != product_code and base_code in nearby) or (base_cat_nr != cat_nr and base_cat_nr in nearby):
                score += 0.5
                assoc_type = "product_family"

            # Strict Tripod Separation (lighting only)
            if is_tripod_variant:
                # Tripod model MUST be a tripod image
                if has_tripod_text:
                    score += 0.7
                    assoc_type = "direct_hero"
                elif is_vertical_pole and same_region and has_tripod_on_page:
                    score += 0.5
                    assoc_type = "direct_hero"
                else:
                    # Non-tripod image cannot match tripod SKU
                    continue
            else:
                # Standalone lighting model must NEVER match a tripod image
                if is_lighting and has_tripod_on_page and (has_tripod_text or is_vertical_pole):
                    continue
                # Match primary hero image in region (scaled for single-page portrait vs spread)
                min_hero_area = 5500 if is_single_page else 20000
                if same_region and cand["area"] >= min_hero_area:
                    score += 0.5
                    if assoc_type == "unverified":
                        assoc_type = "product_family" if is_single_page else "direct_hero"

            if same_region:
                score += 0.2

            if cand["area"] > 40000:
                score += 0.1

            # Only accept if evidence score meets the threshold (score >= 0.5)
            if score >= 0.5:
                # If variant shares image with family (e.g. EU vs US plug variant, or cabinet options)
                if "/" in (cat_nr or "") and assoc_type == "direct_hero":
                    if any(v in (cat_nr or "") for v in ["EU", "US", "/1A", "/1B", "/1C", "/2A", "/2B", "/2C", "/3A", "/3B", "/3C", "/4A", "/4B", "/4C"]):
                        assoc_type = "product_family"

                matched_refs.append(
                    ProductImageRef(
                        image_id=f"img_{cand['xref']}_{cand['physical_page_number']}",
                        file_path=os.path.relpath(cand["crop_path"], os.path.dirname(self.output_dir)),
                        source_pdf=cand["source_pdf"],
                        physical_page_number=cand["physical_page_number"],
                        bounding_box=cand["bounding_box"],
                        association_type=assoc_type,
                        confidence=round(min(1.0, score), 2),
                        caption_or_label=nearby[:100] if nearby else None,
                    )
                )
                if len(matched_refs) >= 1:
                    break

        return matched_refs
