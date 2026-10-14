"""Pydantic schema definitions for GROZ Product Catalogue data extraction.

Enforces strict data integrity, source lineage, confidence scoring,
editorial review tracking, and anti-hallucination policies.
"""

from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class BoundingBox(BaseModel):
    """Spatial bounding box on a PDF page in points."""
    x0: float = Field(..., description="Left coordinate in points")
    y0: float = Field(..., description="Top coordinate in points")
    x1: float = Field(..., description="Right coordinate in points")
    y1: float = Field(..., description="Bottom coordinate in points")
    page_width: float = Field(..., description="Width of the page in points")
    page_height: float = Field(..., description="Height of the page in points")

    @model_validator(mode="after")
    def validate_coordinates(self):
        if self.x0 < 0 or self.y0 < 0:
            raise ValueError(f"Coordinates cannot be negative: ({self.x0}, {self.y0})")
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError(f"Invalid bounding box boundaries: x0={self.x0}, x1={self.x1}, y0={self.y0}, y1={self.y1}")
        return self


class ProductImageRef(BaseModel):
    """Reference to an extracted product image with verifiable source context."""
    image_id: str = Field(..., description="Unique image identifier")
    file_path: str = Field(..., description="Relative path to stored image asset")
    source_pdf: str = Field(..., description="Origin PDF catalogue filename")
    physical_page_number: int = Field(..., ge=1, description="1-indexed physical PDF sheet number")
    bounding_box: BoundingBox = Field(..., description="Spatial location on the page")
    association_type: Literal["direct_hero", "secondary", "product_family", "unverified"] = Field(
        ..., description="Nature of association with this product"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of association")
    caption_or_label: Optional[str] = Field(None, description="Nearby text or callout label")


class EditorialReviewNote(BaseModel):
    """Editorial observation or suspected upstream publisher error in source catalogue."""
    field_name: str = Field(..., description="Field with suspected catalogue error (e.g. 'dimensions_mm', 'dimensions_inch')")
    published_value: str = Field(..., description="Verbatim value as printed in the original PDF catalogue")
    suspected_issue: str = Field(..., description="Detailed description of the typographical or unit discrepancy")
    suggested_correction: Optional[str] = Field(None, description="Proposed corrected value if human reviewer approves")
    source_page_reference: str = Field(..., description="Exact catalogue file, physical sheet, and printed page number")
    review_status: Literal["pending_review", "approved", "rejected"] = Field(
        default="pending_review", description="Human editorial decision status"
    )


class SpecificationItem(BaseModel):
    """A technical specification key-value pair with source text."""
    key: str
    value: str
    unit: Optional[str] = None
    source_raw: Optional[str] = None


class ProductRecord(BaseModel):
    """Strict schema for an extracted GROZ product record."""

    # Core Identifiers
    product_name: str = Field(..., min_length=1, description="Extracted product family or model name")
    cat_nr: Optional[str] = Field(None, description="GROZ Catalogue Number (e.g. LED/550)")
    ord_nr: Optional[str] = Field(None, description="GROZ Order Number (e.g. 55046)")
    sub_title: Optional[str] = Field(None, description="Sub-headline or category type (e.g. Worklight Dual Power)")

    # Descriptions & Features
    description: Optional[str] = Field(None, description="Extracted product summary")
    features: List[str] = Field(default_factory=list, description="Extracted bullet points")

    # Specifications
    specifications: Dict[str, Any] = Field(default_factory=dict, description="Key-value specifications")
    dimensions_inch: Optional[str] = Field(None, description="Dimensions in inches if provided")
    dimensions_mm: Optional[str] = Field(None, description="Dimensions in mm if provided")
    box_qty: Optional[int] = Field(None, description="Packaging box quantity if provided")

    # Source Lineage & Provenance
    source_pdf: str = Field(..., description="Filename of source PDF")
    physical_page_number: int = Field(..., ge=1, description="Physical PDF sheet number (1-based)")
    catalog_page_label: Optional[str] = Field(None, description="Printed catalogue page number (e.g. '8', '11')")
    bounding_box: Optional[BoundingBox] = Field(None, description="Page region enclosing this product block")

    # Extraction Metadata
    extraction_method: Literal["native_pdf", "ocr"] = Field(
        ..., description="Method used to extract text: native digital PDF or OCR fallback"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score (0.0 - 1.0)")
    verification_status: Literal["unverified", "needs_review", "verified"] = Field(
        default="unverified",
        description="Verification state. Default is strictly 'unverified'. Never auto-marked as 'verified'."
    )

    # Associated Images
    images: List[ProductImageRef] = Field(default_factory=list, description="Images linked to this product")

    # Editorial Review Annotations (Separate from published source values)
    editorial_notes: List[EditorialReviewNote] = Field(
        default_factory=list, description="Observations of suspected publisher errors requiring review"
    )

    # Raw Reference
    raw_text_snippet: Optional[str] = Field(None, description="Snippet of raw extracted text for auditing")

    @field_validator("verification_status")
    @classmethod
    def prevent_auto_verified(cls, v: str) -> str:
        """Enforces that newly extracted records cannot be automatically marked as verified."""
        if v == "verified":
            raise ValueError(
                "Automated extraction cannot assign 'verified' status directly. "
                "Must be 'unverified' or 'needs_review' until human review."
            )
        return v
