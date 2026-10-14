"""Tests for table parsing, SKU extraction, exact dimension audit, and image-to-product association."""

import pytest
import os
import pymupdf
from backend.extractor.table_extractor import TableExtractor
from backend.extractor.image_extractor import ImageExtractor
from backend.extractor.product_builder import ProductBuilder
from backend.validator.schema import BoundingBox


def test_table_sku_parsing():
    """Test parsing of table lines with CAT NR and 5-digit ORD NR."""
    sample_lines = [
        "ORDERING INFORMATION",
        "CAT ORD SIZE (LÐH) BOX",
        "NR. NR. QTY.",
        "(INCH) (MM)",
        "LED/550 55046 6-11/16 × 5 170 × 125 10",
    ]
    parsed = TableExtractor._parse_table_lines(sample_lines, None, None)
    assert len(parsed) == 1
    row = parsed[0]
    assert row["ord_nr"] == "55046"
    assert row["cat_nr"] == "LED/550"
    assert row["model_code"] == "LED-550"
    assert row["dimensions_inch"] == "6-11/16 × 5"
    assert row["dimensions_mm"] == "170 × 125"
    assert row["box_qty"] == 10


def test_table_multi_row_parsing_with_tripod():
    """Test parsing of spread table with standalone and tripod models."""
    sample_lines = [
        "ORDERING INFORMATION",
        "CAT ORD DESCRIPTION SIZE (LÐHÐD) BOX",
        "NR. NR. QTY.",
        "(INCH) (MM)",
        "LED/670 55050 Worklight 9.5 x 10 x 5 24 x 26 x 13 4",
        "LED/670T 55077 Worklight complete 46 × (48 to 75-1/2) × 46 117 × (122 - 192) × 117 4",
        "with tripod",
    ]
    parsed = TableExtractor._parse_table_lines(sample_lines, None, None)
    assert len(parsed) == 2
    assert parsed[0]["ord_nr"] == "55050"
    assert parsed[0]["cat_nr"] == "LED/670"
    assert parsed[0]["box_qty"] == 4
    assert parsed[0]["dimensions_inch"] == "9.5 x 10 x 5"
    assert parsed[0]["dimensions_mm"] == "24 x 26 x 13"

    assert parsed[1]["ord_nr"] == "55077"
    assert parsed[1]["cat_nr"] == "LED/670T"
    assert parsed[1]["dimensions_inch"] == "46 × (48 to 75-1/2) × 46"
    assert parsed[1]["dimensions_mm"] == "117 × (122 - 192) × 117"
    assert parsed[1]["box_qty"] == 4
    assert "tripod" in parsed[1]["description"].lower()


def test_telescopic_range_dimension_parsing():
    """Regression test for telescopic heights on LED-680T."""
    sample_lines = [
        "ORDERING INFORMATION",
        "CAT ORD DESCRIPTION SIZE (L×H×D) BOX",
        "NR. NR. QTY.",
        "(INCH) (MM)",
        "LED/680 55089 Floodlight 11-3/16 × 7 × 5-1/8 288 × 176 × 131 1",
        "LED/680T 55090 Floodlight complete 11-3/16 × (27-1/2 to 67) × 5-1/8 288 × (699 to 1702) × 131 1",
        "with tripod",
    ]
    parsed = TableExtractor._parse_table_lines(sample_lines, None, None)
    assert len(parsed) == 2
    assert parsed[1]["cat_nr"] == "LED/680T"
    assert parsed[1]["ord_nr"] == "55090"
    assert parsed[1]["dimensions_inch"] == "11-3/16 × (27-1/2 to 67) × 5-1/8"
    assert parsed[1]["dimensions_mm"] == "288 × (699 to 1702) × 131"
    assert parsed[1]["box_qty"] == 1


def test_image_association_rules(tmp_path):
    """Ensure images are matched to products strictly based on spatial evidence and labels."""
    extractor = ImageExtractor(output_dir=str(tmp_path / "test_images"))

    candidates = [
        {
            "xref": 101,
            "crop_filename": "tripod.png",
            "crop_path": "/tmp/tripod.png",
            "source_pdf": "test.pdf",
            "physical_page_number": 7,
            "bounding_box": BoundingBox(x0=600, y0=200, x1=850, y1=550, page_width=1190, page_height=842),
            "nearby_text": "LED-670T Telescopic Tripod Stand Mounting",
            "region": "right",
            "area": 87500,
            "width": 250,
            "height": 350,
        },
        {
            "xref": 102,
            "crop_filename": "standalone.png",
            "crop_path": "/tmp/standalone.png",
            "source_pdf": "test.pdf",
            "physical_page_number": 7,
            "bounding_box": BoundingBox(x0=280, y0=200, x1=520, y1=450, page_width=1190, page_height=842),
            "nearby_text": "LED-670 Worklight Dual Power",
            "region": "left",
            "area": 60000,
            "width": 240,
            "height": 250,
        },
    ]

    # Standalone model LED-670 must match standalone image, never tripod image
    matched_standalone = extractor.match_image_to_product(
        candidates, product_code="LED-670", cat_nr="LED/670", product_region="full_spread"
    )
    # Recovery 14 Oct 2026: image IDs are now the crop filename stem (unique across PDFs) and
    # direct_hero was renamed direct_product. The images chosen are unchanged.
    assert len(matched_standalone) == 1
    assert matched_standalone[0].image_id == "standalone"
    assert matched_standalone[0].association_type == "direct_product"

    # Tripod model LED-670T must match tripod image
    matched_tripod = extractor.match_image_to_product(
        candidates, product_code="LED-670T", cat_nr="LED/670T", product_region="full_spread"
    )
    assert len(matched_tripod) == 1
    assert matched_tripod[0].image_id == "tripod"
    assert matched_tripod[0].association_type == "direct_product"


def test_live_page_7_exact_dimensions():
    """Verify live extraction against original GROZ_LIGHTING_GL-10_1.pdf Page 7."""
    pdf_path = "GROZ_LIGHTING_GL-10_1.pdf"
    assert os.path.exists(pdf_path)

    doc = pymupdf.open(pdf_path)
    page_7 = doc[6]
    ordering = TableExtractor.extract_ordering_records(page_7, pdf_path, 7)
    assert len(ordering) == 2

    # LED-670
    assert ordering[0]["cat_nr"] == "LED/670"
    assert ordering[0]["ord_nr"] == "55050"
    assert ordering[0]["dimensions_inch"] == "9.5 x 10 x 5"
    assert ordering[0]["dimensions_mm"] == "24 x 26 x 13"
    assert ordering[0]["box_qty"] == 4

    # LED-670T
    assert ordering[1]["cat_nr"] == "LED/670T"
    assert ordering[1]["ord_nr"] == "55077"
    assert ordering[1]["dimensions_inch"] == "46 × (48 to 75-1/2) × 46"
    assert ordering[1]["dimensions_mm"] == "117 × (122 - 192) × 117"
    assert ordering[1]["box_qty"] == 4

    doc.close()


def test_live_page_8_exact_dimensions():
    """Verify live extraction against original GROZ_LIGHTING_GL-10_1.pdf Page 8."""
    pdf_path = "GROZ_LIGHTING_GL-10_1.pdf"
    assert os.path.exists(pdf_path)

    doc = pymupdf.open(pdf_path)
    page_8 = doc[7]
    ordering = TableExtractor.extract_ordering_records(page_8, pdf_path, 8)
    assert len(ordering) == 2

    # LED-680
    assert ordering[0]["cat_nr"] == "LED/680"
    assert ordering[0]["ord_nr"] == "55089"
    assert ordering[0]["dimensions_inch"] == "11-3/16 × 7 × 5-1/8"
    assert ordering[0]["dimensions_mm"] == "288 × 176 × 131"
    assert ordering[0]["box_qty"] == 1

    # LED-680T
    assert ordering[1]["cat_nr"] == "LED/680T"
    assert ordering[1]["ord_nr"] == "55090"
    assert ordering[1]["dimensions_inch"] == "11-3/16 × (27-1/2 to 67) × 5-1/8"
    assert ordering[1]["dimensions_mm"] == "288 × (699 to 1702) × 131"
    assert ordering[1]["box_qty"] == 1

    doc.close()


def test_live_page_9_image_hero_isolation(tmp_path):
    """Verify that LED-685 links to primary hero image xref 3656 (not secondary lifestyle image)."""
    pdf_path = "GROZ_LIGHTING_GL-10_1.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_9 = doc[8]
    products = builder.process_page(page_9, pdf_path, 9)
    assert len(products) == 2

    # LED-685
    p_685 = next(p for p in products if p.ord_nr == "55118")
    assert len(p_685.images) == 1
    assert "p9_xref3656" in p_685.images[0].file_path, f"Expected hero xref3656, got {p_685.images[0].file_path}"
    assert p_685.dimensions_inch == "25-63/64 × 2-31/32 × 3-3/16"
    assert p_685.dimensions_mm == "660 × 75.5 × 81"
    assert p_685.box_qty == 1

    # LED-685T
    p_685t = next(p for p in products if p.ord_nr == "55119")
    assert len(p_685t.images) == 1
    assert "p9_xref3675" in p_685t.images[0].file_path
    assert p_685t.dimensions_inch == "28-17/64 × 6-27/64 × 19-9/16"
    assert p_685t.dimensions_mm == "718 × 1630 × 497"
    assert p_685t.box_qty == 1

    doc.close()


def test_live_page_10_diameter_dimensions(tmp_path):
    """Verify LED-800 diameter dimension capture and LED-660 dimensions."""
    pdf_path = "GROZ_LIGHTING_GL-10_1.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_10 = doc[9]
    products = builder.process_page(page_10, pdf_path, 10)
    assert len(products) == 3

    # LED-660
    p_660 = next(p for p in products if p.ord_nr == "55043")
    assert p_660.dimensions_inch == "8.7 × 8.7 × 12.2"
    assert p_660.dimensions_mm == "223 × 223 × 309"
    assert p_660.box_qty == 8

    # LED-800-EU
    p_800_eu = next(p for p in products if p.ord_nr == "55048")
    assert "12-1/64" in p_800_eu.dimensions_inch
    assert "305 mm" in p_800_eu.dimensions_mm
    assert p_800_eu.box_qty == 1
    assert p_800_eu.specifications.get("plug_type") == "EU"

    doc.close()


def test_tool_storage_p4_cabinets(tmp_path):
    """Verify tool storage extraction on Page 4 (drawers, box quantity, hero image)."""
    pdf_path = "tools_storage.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_4 = doc[3]
    products = builder.process_page(page_4, pdf_path, 4)
    assert len(products) == 2

    # RTC/27-10D/1/GRZ
    p1 = next(p for p in products if p.ord_nr == "75000")
    assert p1.cat_nr == "RTC/27-10D/1/GRZ"
    assert p1.box_qty == 1
    assert p1.specifications.get("no_of_drawers") == 7
    assert p1.specifications.get("overall_load_capacity") == "300 KG (660 LBS)"
    assert len(p1.images) >= 1
    # Recovery 14 Oct 2026: the page prints RTC/27-10D/1/GRZ beside its own cabinet image (xref63),
    # which now wins over the larger family feature photo (xref55) that was chosen by size alone.
    assert "xref63" in p1.images[0].file_path
    assert p1.images[0].association_type == "direct_product"

    # RTC/27-10D/2/GRZ
    p2 = next(p for p in products if p.ord_nr == "75001")
    assert p2.cat_nr == "RTC/27-10D/2/GRZ"
    assert p2.box_qty == 1
    assert p2.specifications.get("no_of_drawers") == 5
    # No image is labelled with this code: only a family image is claimed, never a direct one.
    assert p2.images and p2.images[0].association_type == "product_family"

    doc.close()


def test_tool_storage_p5_top_options(tmp_path):
    """Verify tool storage top options parsing on Page 5."""
    pdf_path = "tools_storage.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_5 = doc[4]
    products = builder.process_page(page_5, pdf_path, 5)
    assert len(products) == 8

    p_mat = next(p for p in products if p.ord_nr == "75035")
    assert p_mat.specifications.get("top_options") == "Rubberized Mat"
    assert p_mat.box_qty == 1

    p_foam = next(p for p in products if p.ord_nr == "75036")
    assert p_foam.specifications.get("top_options") == "Thermofoam"

    p_wood = next(p for p in products if p.ord_nr == "75037")
    assert p_wood.specifications.get("top_options") == "Wooden"

    p_steel = next(p for p in products if p.ord_nr == "75038")
    assert p_steel.specifications.get("top_options") == "Stainless Steel"

    doc.close()


def test_tool_storage_p20_cantilever_boxes(tmp_path):
    """Verify cantilever tool boxes on Page 20 and fraction-interference-free box quantity."""
    pdf_path = "tools_storage.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_20 = doc[19]
    products = builder.process_page(page_20, pdf_path, 20)
    assert len(products) == 4

    p_mtb5 = next(p for p in products if p.ord_nr == "40002")
    assert p_mtb5.cat_nr == "MTB/5"
    assert p_mtb5.box_qty == 1, f"Expected box_qty=1, got {p_mtb5.box_qty} (check fraction interference)"

    p_mtb5t = next(p for p in products if p.ord_nr == "40003")
    assert p_mtb5t.cat_nr == "MTB/5T"
    assert p_mtb5t.box_qty == 1
    # Decision F (rules 2.2.0): the heading is the printed title; the row's own description cell is
    # kept verbatim as a specification (was: sub_title == "Tool Box with Trolley").
    assert p_mtb5t.sub_title == "Cantilever Tool Box"
    assert p_mtb5t.specifications.get("table_description") == "Tool Box with Trolley"

    doc.close()


def test_tool_storage_p21_color_variants(tmp_path):
    """Verify 7 color variants on Page 21."""
    pdf_path = "tools_storage.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_21 = doc[20]
    products = builder.process_page(page_21, pdf_path, 21)
    assert len(products) == 7

    p_black = next(p for p in products if p.ord_nr == "75401")
    assert p_black.specifications.get("colour") == "Classic Black"
    assert p_black.box_qty == 4

    p_orange = next(p for p in products if p.ord_nr == "75400")
    assert p_orange.specifications.get("colour") == "Vibrant Orange"
    assert p_orange.box_qty == 4

    doc.close()


def test_lighting_p11_plug_variants_and_cross_normalization(tmp_path):
    """Verify plug variants on Page 11 and Î character normalization to ×."""
    pdf_path = "GROZ_LIGHTING_GL-10_1.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_11 = doc[10]
    products = builder.process_page(page_11, pdf_path, 11)
    assert len(products) == 4

    p_602_us = next(p for p in products if p.ord_nr == "55075")
    assert p_602_us.specifications.get("plug_type") == "US"
    assert p_602_us.box_qty == 8

    p_612_us = next(p for p in products if p.ord_nr == "55076")
    assert p_612_us.dimensions_mm == "940 × 1730 × 940"
    assert p_612_us.box_qty == 2

    doc.close()


def test_lighting_p12_missing_ord_nr_flagged(tmp_path):
    """Verify that LED/616 with omitted ORD NR column is captured and flagged with pending_review editorial note."""
    pdf_path = "GROZ_LIGHTING_GL-10_1.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_12 = doc[11]
    products = builder.process_page(page_12, pdf_path, 12)
    assert len(products) == 3

    p_616_us = next(p for p in products if p.cat_nr == "LED/616/US")
    assert p_616_us.ord_nr is None
    assert p_616_us.box_qty == 2
    assert len(p_616_us.editorial_notes) == 1
    assert p_616_us.editorial_notes[0].field_name == "ord_nr"
    assert p_616_us.editorial_notes[0].review_status == "pending_review"

    doc.close()


def test_lighting_p14_dual_table_spread(tmp_path):
    """Verify dual table spread on Page 14 with drycell and Li-Po variants."""
    pdf_path = "GROZ_LIGHTING_GL-10_1.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_14 = doc[13]
    products = builder.process_page(page_14, pdf_path, 14)
    assert len(products) == 2

    p_385 = next(p for p in products if p.ord_nr == "55086")
    assert p_385.cat_nr == "LED/385"
    assert p_385.box_qty == 10

    p_385rm = next(p for p in products if p.ord_nr == "55087")
    assert p_385rm.cat_nr == "LED/385RM"
    assert p_385rm.box_qty == 10

    doc.close()


def test_led_685t_editorial_note_compliance(tmp_path):
    """Requirement 1 compliance test: LED-685T verbatim dimensions, pending_review, suggested_correction=None."""
    pdf_path = "GROZ_LIGHTING_GL-10_1.pdf"
    assert os.path.exists(pdf_path)

    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open(pdf_path)
    page_9 = doc[8]
    products = builder.process_page(page_9, pdf_path, 9)
    p_685t = next(p for p in products if p.ord_nr == "55119")

    # Verbatim published values preserved
    assert p_685t.dimensions_inch == "28-17/64 × 6-27/64 × 19-9/16"
    assert p_685t.dimensions_mm == "718 × 1630 × 497"
    assert p_685t.verification_status == "unverified"

    # Editorial note checks
    assert len(p_685t.editorial_notes) == 1
    note = p_685t.editorial_notes[0]
    assert note.field_name == "dimensions_inch"
    assert note.published_value == "28-17/64 × 6-27/64 × 19-9/16"
    assert note.review_status == "pending_review"
    assert note.suggested_correction is None, "Per user requirement 1, suggested_correction must be empty (None)"
    assert "1630" in note.suspected_issue
    assert "27-1/2" in note.suspected_issue

    doc.close()


def test_batch_1_sku_uniqueness_and_traceability(tmp_path):
    """Verify Batch 1 extraction produces exact record counts, unique SKUs, and complete lineage."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    # 1. Tools storage (all 35 pages)
    doc_storage = pymupdf.open("tools_storage.pdf")
    storage_prods = []
    for pno in range(len(doc_storage)):
        storage_prods.extend(builder.process_page(doc_storage[pno], "tools_storage.pdf", pno + 1))
    assert len(storage_prods) == 82, f"Expected 82 tool storage products, got {len(storage_prods)}"

    storage_ords = [p.ord_nr for p in storage_prods if p.ord_nr]
    assert len(set(storage_ords)) == 82, f"Expected 82 unique ORDs in tool storage, got {len(set(storage_ords))}"

    for p in storage_prods:
        assert p.source_pdf == "tools_storage.pdf"
        assert p.physical_page_number >= 1
        assert p.catalog_page_label is not None
        assert p.verification_status in ["unverified", "needs_review"]
        assert p.verification_status != "verified"

    # 2. Lighting pages 11-48
    doc_light = pymupdf.open("GROZ_LIGHTING_GL-10_1.pdf")
    light_prods = []
    for pno in range(10, len(doc_light)):
        light_prods.extend(builder.process_page(doc_light[pno], "GROZ_LIGHTING_GL-10_1.pdf", pno + 1))
    assert len(light_prods) == 56, f"Expected 56 lighting products in pages 11-48, got {len(light_prods)}"

    light_ords = [p.ord_nr for p in light_prods if p.ord_nr]
    assert len(set(light_ords)) == 54, f"Expected 54 unique ORDs in lighting pages 11-48, got {len(set(light_ords))}"

    # Verify zero ORD collisions between lighting and tool storage
    collision = set(storage_ords).intersection(set(light_ords))
    assert len(collision) == 0, f"Unexpected cross-catalogue collision: {collision}"

    doc_storage.close()
    doc_light.close()


def test_led_670_and_670t_dimension_discrepancy_compliance(tmp_path):
    """Verify LED-670 and LED-670T preserve published values and leave suggested_correction empty (None)."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open("GROZ_LIGHTING_GL-10_1.pdf")
    p7 = doc[6]
    prods = builder.process_page(p7, "GROZ_LIGHTING_GL-10_1.pdf", 7)
    assert len(prods) == 2

    p_670 = [p for p in prods if p.cat_nr == "LED/670"][0]
    p_670t = [p for p in prods if p.cat_nr == "LED/670T"][0]

    # Verbatim published values
    assert p_670.dimensions_inch == "9.5 x 10 x 5"
    assert p_670.dimensions_mm == "24 x 26 x 13"
    assert p_670.verification_status == "unverified"
    assert len(p_670.editorial_notes) == 1
    assert p_670.editorial_notes[0].field_name == "dimensions_mm"
    assert p_670.editorial_notes[0].suggested_correction is None, "Must be None pending technical drawing interpretation"
    assert p_670.editorial_notes[0].review_status == "pending_review"

    assert p_670t.dimensions_inch == "46 × (48 to 75-1/2) × 46"
    assert p_670t.dimensions_mm == "117 × (122 - 192) × 117"
    assert p_670t.verification_status == "unverified"
    assert len(p_670t.editorial_notes) == 1
    assert p_670t.editorial_notes[0].field_name == "dimensions_mm"
    assert p_670t.editorial_notes[0].suggested_correction is None, "Must be None pending technical drawing interpretation"
    assert p_670t.editorial_notes[0].review_status == "pending_review"
    assert "39-1/2" in p_670t.editorial_notes[0].suspected_issue

    doc.close()


def test_slender_penlight_and_option_variant_image_associations(tmp_path):
    """Verify slender penlights and cabinet option variants retain hero image associations."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    # Tool storage page 9: RTC/42-20/1B/GRZ should match family image
    doc_ts = pymupdf.open("tools_storage.pdf")
    prods_p9 = builder.process_page(doc_ts[8], "tools_storage.pdf", 9)
    p_1b = [p for p in prods_p9 if p.cat_nr == "RTC/42-20/1B/GRZ"][0]
    assert len(p_1b.images) >= 1
    assert p_1b.images[0].association_type == "product_family"
    doc_ts.close()

    # GL-10 page 28: LED/336 slender penlight should match hero image
    doc_gl = pymupdf.open("GROZ_LIGHTING_GL-10_1.pdf")
    prods_p28 = builder.process_page(doc_gl[27], "GROZ_LIGHTING_GL-10_1.pdf", 28)
    p_336 = [p for p in prods_p28 if p.cat_nr == "LED/336"][0]
    assert len(p_336.images) >= 1
    # Recovery 14 Oct 2026: no product code is printed beside this image, so the link is layout
    # evidence (only table in the region) and is classed product_family, not a direct product image.
    assert "xref4823" in p_336.images[0].file_path
    assert p_336.images[0].association_type == "product_family"

    # GL-10 page 12: LED/621 swivelling light should match hero image
    prods_p12 = builder.process_page(doc_gl[11], "GROZ_LIGHTING_GL-10_1.pdf", 12)
    p_621 = [p for p in prods_p12 if p.cat_nr == "LED/621"][0]
    assert len(p_621.images) >= 1
    assert "xref3836" in p_621.images[0].file_path
    assert p_621.images[0].association_type == "product_family"
    doc_gl.close()


def test_cumulative_reconciliation_exact_metrics():
    """Verify Batch 1 baseline metrics and overall cumulative reconciliation (813 products)."""
    import json
    with open("output/extracted_products.json", "r", encoding="utf-8") as f:
        cumulative = json.load(f)

    # 1. Total cumulative count: 813 products (149 Batch 1 + 664 Batch 2)
    assert len(cumulative) == 813

    # 2. Batch 1 slice reconciliation
    b1_slice = [p for p in cumulative if p["source_pdf"] in ["tools_storage.pdf", "GROZ_LIGHTING_GL-10_1.pdf"]]
    assert len(b1_slice) == 149
    b1_ords = [p.get("ord_nr") for p in b1_slice if p.get("ord_nr")]
    assert len(b1_ords) == 147
    assert len(set(b1_ords)) == 147
    b1_null_ords = [p for p in b1_slice if not p.get("ord_nr")]
    assert len(b1_null_ords) == 2
    for p in b1_null_ords:
        assert p["cat_nr"] in ["LED/616/US", "LED/616/EU"]
        assert p["verification_status"] == "needs_review"

    # 3. Batch 2 slice reconciliation
    b2_slice = [p for p in cumulative if p["source_pdf"] in ["Estwing_Hammer_E-03_Interactive_1.pdf", "Precision_Catalogue_CA_03.pdf"]]
    assert len(b2_slice) == 664

    # 4. Overall cumulative status metrics
    status_counts = {
        "unverified": len([p for p in cumulative if p["verification_status"] == "unverified"]),
        "needs_review": len([p for p in cumulative if p["verification_status"] == "needs_review"]),
        "verified": len([p for p in cumulative if p["verification_status"] == "verified"]),
    }
    assert status_counts["unverified"] == 810
    assert status_counts["needs_review"] == 3
    assert status_counts["verified"] == 0


def test_batch_2_page_counts_inspection():
    """Verify actual physical page counts and assess differences from earlier estimates."""
    doc_estwing = pymupdf.open("Estwing_Hammer_E-03_Interactive_1.pdf")
    doc_precision = pymupdf.open("Precision_Catalogue_CA_03.pdf")

    estwing_pages = len(doc_estwing)
    precision_pages = len(doc_precision)

    doc_estwing.close()
    doc_precision.close()

    assert estwing_pages == 20, f"Expected 20 pages for Estwing, got {estwing_pages}"
    assert precision_pages == 88, f"Expected 88 pages for Precision, got {precision_pages}"

    # Delta compared to layout assessment (Estwing estimated 28, Precision estimated 52)
    assert estwing_pages - 28 == -8
    assert precision_pages - 52 == +36


def test_estwing_single_page_column_partitioning_p4(tmp_path):
    """Verify Estwing Page 4 extracts 29 products across 3 distinct table boxes with hammer specifications."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open("Estwing_Hammer_E-03_Interactive_1.pdf")
    p4 = doc[3]
    prods = builder.process_page(p4, "Estwing_Hammer_E-03_Interactive_1.pdf", 4)
    doc.close()

    assert len(prods) == 29

    # Sledgehammers (ESH-624X: ORD 62202)
    esh_624x = [p for p in prods if p.cat_nr == "ESH-624X"][0]
    assert esh_624x.ord_nr == "62202"
    assert esh_624x.specifications.get("head_weight") == "6lb/2.7kg"
    assert esh_624x.specifications.get("overall_length") == "24”/600mm"
    assert esh_624x.specifications.get("spring_steel_bars") == 6
    assert esh_624x.verification_status == "unverified"

    # Soft face sledgehammers (ESH/SF-624X: ORD 62232)
    esh_sf = [p for p in prods if p.cat_nr == "ESH/SF-624X"][0]
    assert esh_sf.ord_nr == "62232"
    assert esh_sf.specifications.get("head_weight") == "6lb/2.7kg"
    assert esh_sf.specifications.get("overall_length") == "24”/600mm"

    # Club hammers (ECH-416X: ORD 62282)
    ech_416x = [p for p in prods if p.cat_nr == "ECH-416X"][0]
    assert ech_416x.ord_nr == "62282"
    assert ech_416x.specifications.get("spring_steel_bars") == 4


def test_estwing_duplicate_published_ord_p11(tmp_path):
    """Verify Estwing Page 11 duplicate ORD 62900 preserves published value and attaches editorial review note."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open("Estwing_Hammer_E-03_Interactive_1.pdf")
    p11 = doc[10]
    prods = builder.process_page(p11, "Estwing_Hammer_E-03_Interactive_1.pdf", 11)
    doc.close()

    assert len(prods) == 6

    # Decision B (approved 14 Oct 2026): both variants printed with 62900 carry the same note, which
    # does not guess the intended number (was: a note on EMLTT/CH-45W only, suggesting 62902).
    for cat in ("EMLTT/CH-25W", "EMLTT/CH-45W"):
        p = [p for p in prods if p.cat_nr == cat][0]
        assert p.ord_nr == "62900"
        assert len(p.editorial_notes) == 1
        note = p.editorial_notes[0]
        assert note.field_name == "ord_nr"
        assert note.published_value == "62900"
        assert "Duplicate ORD NR" in note.suspected_issue and "62901" in note.suspected_issue
        assert "62902" not in note.suspected_issue
        assert note.suggested_correction is None
        assert note.review_status == "pending_review"
    assert not [p for p in prods if p.cat_nr == "EMLTT/CH-38W"][0].editorial_notes


def test_estwing_missing_ord_p15_pulaski_axe(tmp_path):
    """Verify Estwing Page 15 Pulaski Axe EPAX-336F has ord_nr=None, status needs_review, and editorial note."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open("Estwing_Hammer_E-03_Interactive_1.pdf")
    p15 = doc[14]
    prods = builder.process_page(p15, "Estwing_Hammer_E-03_Interactive_1.pdf", 15)
    doc.close()

    assert len(prods) == 3

    # EPAX-336F
    p_axe = [p for p in prods if p.cat_nr == "EPAX-336F"][0]
    assert p_axe.ord_nr is None
    assert p_axe.verification_status == "needs_review"
    assert len(p_axe.editorial_notes) == 1

    note = p_axe.editorial_notes[0]
    assert note.field_name == "ord_nr"
    assert note.published_value == "[Not in table]"
    assert "omits the ORD NR. column entirely" in note.suspected_issue
    assert note.suggested_correction is None


def test_precision_single_page_machinist_squares_p5(tmp_path):
    """Verify Precision Page 5 extracts 12 Machinist's Squares with clean CAT NRs and ORDs."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open("Precision_Catalogue_CA_03.pdf")
    p5 = doc[4]
    prods = builder.process_page(p5, "Precision_Catalogue_CA_03.pdf", 5)
    doc.close()

    assert len(prods) == 12

    # SS/2: ORD 01100
    p_ss2 = [p for p in prods if p.cat_nr == "SS/2"][0]
    assert p_ss2.ord_nr == "01100"
    assert p_ss2.verification_status == "unverified"

    # SS/4 (stripped of º best seller glyph): ORD 01102
    p_ss4 = [p for p in prods if p.cat_nr == "SS/4"][0]
    assert p_ss4.ord_nr == "01102"


def test_precision_p6_tolerance_matrix_omission(tmp_path):
    """Verify Precision Page 6 tolerance matrix (BS 939 Grade B) is not extracted as ordering rows."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open("Precision_Catalogue_CA_03.pdf")
    p6 = doc[5]
    prods = builder.process_page(p6, "Precision_Catalogue_CA_03.pdf", 6)
    doc.close()

    assert len(prods) == 0, f"Expected 0 ordering products from tolerance matrix page 6, got {len(prods)}"


def test_precision_p68_knurl_matrix_parsing(tmp_path):
    """Verify Precision Page 68 extracts 48 knurl products with Coarse/Medium/Fine pitches and pattern variants."""
    image_ext = ImageExtractor(str(tmp_path / "images"))
    builder = ProductBuilder(image_ext)

    doc = pymupdf.open("Precision_Catalogue_CA_03.pdf")
    p68 = doc[67]
    prods = builder.process_page(p68, "Precision_Catalogue_CA_03.pdf", 68)
    doc.close()

    assert len(prods) == 48

    # Coarse Left 5/8": K58/CL (ORD 12850)
    p_k58cl = [p for p in prods if p.cat_nr == "K58/CL"][0]
    assert p_k58cl.ord_nr == "12850"
    assert p_k58cl.dimensions_inch == '5/8"'

    # Coarse Diamond 1": K01/CD (ORD 13053)
    p_k01cd = [p for p in prods if p.cat_nr == "K01/CD"][0]
    assert p_k01cd.ord_nr == "13053"
    assert p_k01cd.dimensions_inch == '1"'


def test_batch_2_json_artifact_integrity():
    """Verify batch_2_products.json contains 664 records with complete source lineage."""
    import json
    with open("output/batch_2_products.json", "r", encoding="utf-8") as f:
        b2_data = json.load(f)

    assert len(b2_data) == 664

    # Estwing slice
    est_records = [p for p in b2_data if "Estwing" in p["source_pdf"]]
    assert len(est_records) == 131

    # Precision slice
    prec_records = [p for p in b2_data if "Precision" in p["source_pdf"]]
    assert len(prec_records) == 533

    # Zero verified
    assert len([p for p in b2_data if p["verification_status"] == "verified"]) == 0


def test_batch_2_page_coverage_and_excluded_pages():
    """Verify active vs excluded page counts for Estwing (13 active, 7 excluded) and Precision (68 active, 20 excluded)."""
    import json
    with open("output/batch_2_products.json", "r", encoding="utf-8") as f:
        b2_data = json.load(f)

    # Estwing
    e_prods = [p for p in b2_data if "Estwing" in p["source_pdf"]]
    e_active_pages = sorted(set(p["physical_page_number"] for p in e_prods))
    assert len(e_active_pages) == 13
    assert e_active_pages == [4, 5, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    e_excluded = [p for p in range(1, 21) if p not in e_active_pages]
    assert e_excluded == [1, 2, 3, 6, 8, 19, 20]

    # Precision
    p_prods = [p for p in b2_data if "Precision" in p["source_pdf"]]
    p_active_pages = sorted(set(p["physical_page_number"] for p in p_prods))
    assert len(p_active_pages) == 68
    p_excluded = [p for p in range(1, 89) if p not in p_active_pages]
    assert len(p_excluded) == 20
    assert p_excluded == [1, 2, 3, 4, 6, 18, 32, 41, 42, 55, 70, 80, 81, 82, 83, 84, 85, 86, 87, 88]


def test_precision_50_empty_image_records_audit():
    """Verify exactly 50 records in Precision have empty image arrays across 5 multi-family pages."""
    import json
    with open("output/batch_2_products.json", "r", encoding="utf-8") as f:
        b2_data = json.load(f)

    p_no_img = [p for p in b2_data if "Precision" in p["source_pdf"] and not p.get("images")]
    assert len(p_no_img) == 50

    by_page = {}
    for p in p_no_img:
        by_page[p["physical_page_number"]] = by_page.get(p["physical_page_number"], 0) + 1

    assert by_page == {23: 2, 44: 2, 45: 12, 49: 7, 61: 27}




