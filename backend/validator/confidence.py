"""Confidence scoring and verification status rules for extracted product data."""

from typing import Dict, Any, List, Optional
from .schema import BoundingBox, ProductImageRef


def calculate_product_confidence(
    cat_nr: Optional[str],
    ord_nr: Optional[str],
    product_name: str,
    description: Optional[str],
    specifications: Dict[str, Any],
    extraction_method: str,
    images: List[ProductImageRef],
) -> float:
    """Computes a principled confidence score between 0.0 and 1.0."""
    score = 0.0

    # Model and identifiers
    if product_name and len(product_name.strip()) > 1:
        score += 0.15
    if cat_nr and len(cat_nr.strip()) > 2:
        score += 0.20
    if ord_nr and ord_nr.strip().isdigit() and len(ord_nr.strip()) >= 4:
        score += 0.20

    # Content richness
    if description and len(description.strip()) > 20:
        score += 0.15
    if specifications and len(specifications) > 0:
        score += 0.15

    # Extraction method
    if extraction_method == "native_pdf":
        score += 0.10
    elif extraction_method == "ocr":
        score += 0.05

    # Image evidence: unresolved (page-proximity-only) candidates do not raise confidence
    if images and any(
        img.confidence >= 0.7 and img.association_type in ("direct_product", "product_family") for img in images
    ):
        score += 0.05

    return min(1.0, round(score, 2))


def determine_initial_status(confidence: float, cat_nr: Optional[str], ord_nr: Optional[str]) -> str:
    """Determines initial verification state: either 'needs_review' or 'unverified'.

    NOTE: Per requirement, records are NEVER automatically marked as 'verified'.
    """
    if not cat_nr or not ord_nr or confidence < 0.65:
        return "needs_review"
    return "unverified"
