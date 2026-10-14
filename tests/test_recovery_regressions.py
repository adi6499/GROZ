"""Regression tests for the defects confirmed in PROJECT_HANDOFF_AUDIT.md (recovery, 14 Oct 2026).

Every expected value below was read from the printed PDF page (see tools/dump_page.py), not from
the extractor's own output.
"""

import re

import pymupdf
import pytest

from backend.extractor.image_extractor import ImageExtractor, _code_in, pdf_slug
from backend.extractor.product_builder import ProductBuilder
from backend.extractor.table_extractor import TableExtractor

PRECISION = "Precision_Catalogue_CA_03.pdf"
LIGHTING = "GROZ_LIGHTING_GL-10_1.pdf"
STORAGE = "tools_storage.pdf"
ESTWING = "Estwing_Hammer_E-03_Interactive_1.pdf"


@pytest.fixture(scope="module")
def page_products(tmp_path_factory):
    """Process a page once per module; crops go to a temporary folder, never to output/."""
    builder = ProductBuilder(ImageExtractor(str(tmp_path_factory.mktemp("out") / "images")))
    docs, cache = {}, {}

    def get(pdf, page_no):
        if (pdf, page_no) not in cache:
            doc = docs.setdefault(pdf, pymupdf.open(pdf))
            cache[(pdf, page_no)] = builder.process_page(doc[page_no - 1], pdf, page_no)
        return cache[(pdf, page_no)]

    yield get
    for d in docs.values():
        d.close()


def by_cat(products, cat_nr):
    hits = [p for p in products if p.cat_nr == cat_nr]
    assert len(hits) == 1, f"expected exactly one {cat_nr}, got {len(hits)}"
    return hits[0]


def printed_ord_numbers(pdf, page_no):
    with pymupdf.open(pdf) as doc:
        tokens = (re.sub(r"^[^0-9]+", "", w[4]).rstrip(".,") for w in doc[page_no - 1].get_text("words"))
        return {t for t in tokens if re.fullmatch(r"\d{5}", t)}


# --- Defect 1: two-column (paired) tables lost the right-hand CAT/ORD pair -------------------------

@pytest.mark.parametrize("page_no,expected", [(8, 18), (17, 12), (56, 96), (57, 100), (62, 28)])
def test_paired_tables_extract_every_printed_order_number(page_products, page_no, expected):
    products = page_products(PRECISION, page_no)
    extracted = {p.ord_nr for p in products if p.ord_nr}
    assert extracted == printed_ord_numbers(PRECISION, page_no)
    assert len(products) == expected


def test_paired_table_variants_keep_their_printed_column_label(page_products):
    tb_h = by_cat(page_products(PRECISION, 57), "TB/H/3-75M")
    assert tb_h.ord_nr == "12600"
    assert tb_h.specifications["variant_label"] == "GRADE B"
    assert by_cat(page_products(PRECISION, 57), "TB/3-75M").specifications["variant_label"] == "GRADE A"

    dsw = by_cat(page_products(PRECISION, 62), "DSW/2-1")
    assert (dsw.ord_nr, dsw.box_qty, dsw.specifications["variant_label"]) == ("08520", 100, "WORKSHOP GRADE")

    ke = by_cat(page_products(PRECISION, 8), "KE/12")
    assert (ke.ord_nr, ke.box_qty, ke.specifications["variant_label"]) == ("02550", 24, "KNIFE EDGES")


def test_side_by_side_independent_tables_in_one_half(page_products):
    """Precision p17 prints an inch table and a metric table side by side, each with its own BOX QTY."""
    mm_metric = by_cat(page_products(PRECISION, 17), "MM/0-25")
    assert (mm_metric.ord_nr, mm_metric.box_qty) == ("16104", 25)
    assert "variant_label" not in mm_metric.specifications
    assert by_cat(page_products(PRECISION, 17), "MM/0-1").ord_nr == "16112"


def test_captions_next_to_a_table_header_are_not_products(page_products):
    """Precision p39: photo captions EST/2/ST and EST/1/ST sit beside a table that has an ORD column.

    Found during the recovery re-extraction: the caption grouped into the header line hid the
    ORD column, so two caption codes became records without an ORD. Rows without an ORD in a
    table that has an ORD column are never records.
    """
    products = page_products(PRECISION, 39)
    assert not [p.cat_nr for p in products if not p.ord_nr]
    assert {p.ord_nr for p in products} == printed_ord_numbers(PRECISION, 39)


# --- Defect 2: single-letter CAT prefix truncated (G/10/M1 -> 10/M1) -----------------------------

def test_single_letter_cat_prefix_is_kept(page_products):
    products = page_products(PRECISION, 61)
    assert by_cat(products, "G/10/M1").ord_nr == "07700"
    assert by_cat(products, "G/24/M5").ord_nr == "07719"
    assert not [p.cat_nr for p in products if re.fullmatch(r"\d+/M\d", p.cat_nr or "")]
    with pymupdf.open(PRECISION) as doc:
        printed = {re.sub(r"^[^A-Za-z0-9]+", "", w[4]).rstrip(".,") for w in doc[60].get_text("words")}
    assert {p.cat_nr for p in products} <= printed


# --- Defect 3: box quantity shifted by a value whitelist / taken from other columns --------------

def test_box_quantity_read_from_its_own_column(page_products):
    p10 = page_products(PRECISION, 10)
    assert [by_cat(p10, c).box_qty for c in ("ID/3", "ID/8", "ID/10", "ID/12", "OD/4")] == [200, 90, 60, 60, 200]
    assert {p.box_qty for p in page_products(PRECISION, 33) if p.cat_nr.startswith("EF/") and "/ST" not in p.cat_nr} == {400}
    assert by_cat(page_products(LIGHTING, 15), "LED/370").box_qty == 15


def test_no_box_quantity_when_table_has_no_box_column(page_products):
    """Precision p57 tool-bit tables have SQUARE SIZE and LENGTH columns but no BOX QTY column."""
    tb = by_cat(page_products(PRECISION, 57), "TB/3-75M")
    assert tb.box_qty is None


# --- Defect 4: dimensions beginning with a bare fraction lost it ---------------------------------

def test_dimensions_starting_with_a_fraction(page_products):
    cob1 = by_cat(page_products(PRECISION, 57), "COB/0-1")
    assert (cob1.dimensions_inch, cob1.dimensions_mm) == ("1/16 × 5/16 × 3-1/2", "1.52 × 7.93 × 88.9")
    cob2 = by_cat(page_products(PRECISION, 57), "COB/0-2")
    assert (cob2.dimensions_inch, cob2.dimensions_mm) == ("3/32 × 1/ 2 × 4", "2.38 × 12.7 × 101.6")


@pytest.mark.parametrize("text,expected", [
    ("1/16 × 5/16 × 3-1/2", ["1/16 × 5/16 × 3-1/2"]),
    ("46 × (48 to 75-1/2) × 46 117 × (122 - 192) × 117", ["46 × (48 to 75-1/2) × 46", "117 × (122 - 192) × 117"]),
    ("9.5 x 10 x 5 24 x 26 x 13", ["9.5 x 10 x 5", "24 x 26 x 13"]),
    ("4×1.5LR44", []),  # a battery spec, not a dimension
])
def test_dimension_pattern(text, expected):
    assert [d.strip() for d in re.findall(TableExtractor.DIM_PATTERN, text)] == expected


# --- Defect 5: specifications leaking between unrelated products ---------------------------------

def test_lighting_specs_not_attached_to_non_lighting_products(page_products):
    assert "beam_angle" not in by_cat(page_products(STORAGE, 21), "TCHL/11-10D/1/BL/GRZ").specifications
    squares = page_products(PRECISION, 5)
    assert not [p.cat_nr for p in squares if {"beam_angle", "overall_length"} & set(p.specifications)]


def test_row_specs_require_their_column_header(page_products):
    assert "head_weight" not in by_cat(page_products(STORAGE, 9), "RTC/42-20/2B/GRZ").specifications
    assert "head_weight" not in by_cat(page_products(PRECISION, 14), "RNG/4").specifications
    assert "top_options" not in by_cat(page_products(LIGHTING, 16), "LED/360").specifications
    assert by_cat(page_products(LIGHTING, 32), "LED/131").dimensions_inch is None  # "4×1.5LR44" is a battery
    # Hammer columns are still read where the table has them.
    esh = by_cat(page_products(ESTWING, 4), "ESH-624X")
    assert esh.specifications["head_weight"] == "6lb/2.7kg"


def test_drawer_count_only_from_a_drawers_column(page_products):
    """tools_storage p6 has a '7 DRAWER' caption but no NO. OF DRAWERS column (found during recovery)."""
    assert "no_of_drawers" not in by_cat(page_products(STORAGE, 6), "RTC/27-20/1/GRZ").specifications
    assert "no_of_drawers" not in by_cat(page_products(STORAGE, 22), "TCHL/11-10D/3/BL/GRZ").specifications
    assert by_cat(page_products(STORAGE, 4), "RTC/27-10D/1/GRZ").specifications["no_of_drawers"] == 7


def test_length_and_weight_columns_keep_their_printed_meaning(page_products):
    """Keys follow the printed header: OVERALL LENGTH, LENGTH, HEAD WEIGHT, WEIGHT (Estwing p11, p16, p17)."""
    est16 = page_products(ESTWING, 16)
    assert by_cat(est16, "EPB-12").specifications.get("length") == "12”/300mm"          # LENGTH column
    esab = by_cat(est16, "ESAB-72").specifications
    assert (esab.get("overall_length"), esab.get("weight")) == ("72”/1829mm", "17 lbs./7.73kg")
    assert "head_weight" not in esab                                                    # WEIGHT, not HEAD WEIGHT
    assert by_cat(page_products(ESTWING, 17), "EHDPR-46").specifications.get("length") == "46”/1170 mm"
    # Feature text beside the table (p17) and a kit heading below it (p13) must not block the values
    assert by_cat(page_products(ESTWING, 17), "EGBR-36").specifications.get("length") == "36”/914 mm"
    eax = by_cat(page_products(ESTWING, 13), "EAX-114X").specifications
    assert (eax.get("head_weight"), eax.get("overall_length")) == ("1.25 lb/0.5kg", "14”/350mm")
    # Mallets print FACE DIA. before OVERALL LENGTH; the length is read from its own column
    assert by_cat(page_products(ESTWING, 11), "EMLTT/CH-25W").specifications["overall_length"] == "11”/280mm"
    # Qualified columns get their own printed name (HANDLE LENGTH -> handle_length), never overall_length
    etm = by_cat(page_products(ESTWING, 18), "ETM/0808S").specifications
    assert etm.get("handle_length") == "45”/1143mm" and "overall_length" not in etm
    # A set description running across BLADE/STOCK LENGTH columns is prose, not a length value
    assert not [(p.cat_nr, k) for p in page_products(PRECISION, 5) for k in p.specifications if k.endswith("length")]


def test_ambiguous_page_ratings_are_not_attributed(page_products):
    """Precision p19 prints IP54 for MMED/1-2 and IP65 for MMED/1/65; neither is applied page-wide."""
    assert not [p.cat_nr for p in page_products(PRECISION, 19) if "ip_rating" in p.specifications]


def test_power_source_is_verbatim_and_never_derived(page_products):
    assert by_cat(page_products(LIGHTING, 12), "LED/616/US").specifications["power_source"] == "110V AC, 60 Hz"
    led602 = by_cat(page_products(LIGHTING, 11), "LED/602/US")
    assert led602.specifications["plug_type"] == "US"
    assert "power_source" not in led602.specifications  # table has PLUG TYPE but no POWER SOURCE column


# --- Defect 6: LED/695 on lighting physical page 5 was never processed ----------------------------

def test_led_695_extracted_from_page_5(page_products):
    led = by_cat(page_products(LIGHTING, 5), "LED/695")
    assert (led.ord_nr, led.box_qty, led.physical_page_number) == ("55117", 10, 5)
    assert led.dimensions_inch == "7-23/64 × 4-53/64 × 1-63/64"
    assert led.dimensions_mm == "187 × 122.5 × 50.5"
    assert led.verification_status == "unverified"


# --- Defect 7: image associations must state their evidence ---------------------------------------

def test_image_association_types_and_evidence(page_products):
    for pdf, page_no in ((PRECISION, 56), (PRECISION, 17), (STORAGE, 4), (LIGHTING, 7)):
        for p in page_products(pdf, page_no):
            for im in p.images:
                assert im.association_type in ("direct_product", "product_family", "unresolved")
                assert im.evidence
                if im.association_type == "direct_product":
                    # the evidence names this product's own code (CAT NR or its model-code spelling)
                    assert p.cat_nr in im.evidence or (p.cat_nr or "").replace("/", "-") in im.evidence


def test_proximity_only_images_are_unresolved(page_products):
    """Precision p17 has two tables side by side and no code labels: images are only candidates."""
    assert {im.association_type for p in page_products(PRECISION, 17) for im in p.images} == {"unresolved"}


def test_code_labels_match_whole_codes_only():
    assert _code_in("LED-670", "LED-670 Worklight")
    assert not _code_in("LED-670", "LED-670T Telescopic Tripod")


def test_crop_names_and_ids_are_unique_across_pdfs(page_products):
    """The original IDs img_508_16 / img_512_16 were shared by Estwing and tools_storage page 16."""
    ids = {}
    for pdf in (ESTWING, STORAGE):
        for p in page_products(pdf, 16):
            for im in p.images:
                assert im.file_path.startswith(f"images/{pdf_slug(pdf)}_p16_")
                assert "\\" not in im.file_path
                ids.setdefault(im.image_id, set()).add(pdf)
    assert all(len(v) == 1 for v in ids.values())
