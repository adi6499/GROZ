"""Unit tests for Pydantic product schema, validation integrity, editorial notes, and anti-hallucination rules."""

import pytest
from pydantic import ValidationError
from backend.validator.schema import ProductRecord, BoundingBox, ProductImageRef, EditorialReviewNote
from backend.validator.confidence import calculate_product_confidence, determine_initial_status


def test_schema_prevents_auto_verified_status():
    """Ensure records cannot be instantiated with 'verified' status directly."""
    with pytest.raises(ValidationError) as exc_info:
        ProductRecord(
            product_name="LED-550",
            source_pdf="test.pdf",
            physical_page_number=6,
            extraction_method="native_pdf",
            confidence=0.9,
            verification_status="verified",  # strictly forbidden
        )
    assert "Automated extraction cannot assign 'verified' status directly" in str(exc_info.value)


def test_schema_defaults_and_missing_fields():
    """Ensure missing fields remain None without hallucinating placeholder values."""
    record = ProductRecord(
        product_name="LED-550",
        source_pdf="test.pdf",
        physical_page_number=6,
        extraction_method="native_pdf",
        confidence=0.85,
    )
    assert record.verification_status == "unverified"
    assert record.cat_nr is None
    assert record.ord_nr is None
    assert record.description is None
    assert record.dimensions_inch is None
    assert record.box_qty is None
    assert record.specifications == {}
    assert record.images == []
    assert record.editorial_notes == []


def test_bounding_box_coordinate_validation():
    """Ensure bounding boxes reject inverted or negative coordinates."""
    # Negative coordinates
    with pytest.raises(ValidationError):
        BoundingBox(x0=-5, y0=10, x1=50, y1=60, page_width=500, page_height=700)

    # Inverted x coordinates (x1 < x0)
    with pytest.raises(ValidationError):
        BoundingBox(x0=100, y0=10, x1=50, y1=60, page_width=500, page_height=700)

    # Inverted y coordinates (y1 < y0)
    with pytest.raises(ValidationError):
        BoundingBox(x0=10, y0=100, x1=50, y1=60, page_width=500, page_height=700)

    # Valid bbox
    bbox = BoundingBox(x0=10, y0=20, x1=150, y1=200, page_width=595, page_height=842)
    assert bbox.x1 > bbox.x0
    assert bbox.y1 > bbox.y0


def test_editorial_review_notes_attachment():
    """Ensure editorial review notes can be attached without altering published source values."""
    note = EditorialReviewNote(
        field_name="dimensions_mm",
        published_value="24 x 26 x 13",
        suspected_issue="Upstream unit mismatch in printed catalogue",
        suggested_correction="241 × 254 × 127 mm",
        source_page_reference="GROZ_LIGHTING_GL-10_1.pdf Physical Page 7",
    )
    record = ProductRecord(
        product_name="LED-670",
        cat_nr="LED/670",
        ord_nr="55050",
        dimensions_inch="9.5 x 10 x 5",
        dimensions_mm="24 x 26 x 13",  # verbatim published value unchanged
        source_pdf="GROZ_LIGHTING_GL-10_1.pdf",
        physical_page_number=7,
        extraction_method="native_pdf",
        confidence=1.0,
        editorial_notes=[note],
    )
    assert record.dimensions_mm == "24 x 26 x 13"
    assert len(record.editorial_notes) == 1
    assert record.editorial_notes[0].field_name == "dimensions_mm"
    assert record.editorial_notes[0].review_status == "pending_review"


def test_confidence_and_status_determination():
    """Test confidence scoring and initial status assignment."""
    # Missing SKU / ORD number -> status must be 'needs_review'
    conf_low = calculate_product_confidence(
        cat_nr=None,
        ord_nr=None,
        product_name="Unknown Lamp",
        description=None,
        specifications={},
        extraction_method="native_pdf",
        images=[],
    )
    status_low = determine_initial_status(conf_low, None, None)
    assert status_low == "needs_review"
    assert conf_low < 0.5

    # Full data -> status 'unverified', never 'verified'
    conf_high = calculate_product_confidence(
        cat_nr="LED/550",
        ord_nr="55046",
        product_name="LED-550",
        description="Powerful rechargeable COB worklight designed for the professional user",
        specifications={"lumens": "1000", "battery": "3.7V 4400 mAh"},
        extraction_method="native_pdf",
        images=[],
    )
    status_high = determine_initial_status(conf_high, "LED/550", "55046")
    assert status_high == "unverified"
    assert conf_high >= 0.8
