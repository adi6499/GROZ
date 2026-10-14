"""Regression tests for the image evidence rules 2.3.0 (decision G, 14 Oct 2026).

Every expected picture below was checked by eye against the printed catalogue page (overlay sheets
of the dry run): the product's code is printed under the picture, or the picture is its section's
only picture above the product's table, or the picture's caption repeats the table caption.
Products the page does not picture must stay unconfirmed.
"""

import re

import pymupdf
import pytest

from backend.extractor.image_extractor import ImageExtractor, _code_in
from backend.extractor.product_builder import ProductBuilder

PRECISION = "Precision_Catalogue_CA_03.pdf"
LIGHTING = "GROZ_LIGHTING_GL-10_1.pdf"
STORAGE = "tools_storage.pdf"
ESTWING = "Estwing_Hammer_E-03_Interactive_1.pdf"
SHOWN = ("direct_product", "product_family")


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


def product(products, cat_nr):
    hits = [p for p in products if p.cat_nr == cat_nr]
    assert len(hits) == 1, f"{cat_nr}: {len(hits)} records"
    return hits[0]


def pic(products, cat_nr):
    """(association type, image xref) of a product's picture; (None, None) without one."""
    p = product(products, cat_nr)
    if not p.images:
        return None, None
    im = p.images[0]
    return im.association_type, int(re.search(r"_xref(\d+)_", im.file_path).group(1))


def evidence(products, cat_nr):
    return product(products, cat_nr).images[0].evidence


def test_codes_match_only_as_whole_codes():
    assert not _code_in("MS/7", "MS/7/AL")
    assert not _code_in("TWZ/401", "TWZ/401XX")
    assert _code_in("MS/7", "MS/7 MS/380A")
    assert _code_in("MS/7/AL", "MS/380A MS/7/AL")


def test_thin_upright_pictures_keep_their_own_codes(page_products):
    # Precision p56-57: six tweezers per page, each 29-43 pt wide with its code printed under it.
    p58 = page_products(PRECISION, 58)
    for cat, xref in {"TWZ/401XX": 1118, "TWZ/403": 1122, "TWZ/408": 1126,
                      "TWZ/410": 1130, "TWZ/412": 1134, "TWZ/413": 1138}.items():
        assert pic(p58, cat) == ("direct_product", xref), cat
    p59 = page_products(PRECISION, 59)
    for cat, xref in {"TWZ/414": 1145, "TWZ/415": 1149, "TWZ/416": 1153, "TWZ/417": 1157,
                      "TWZ/423-3C": 1165, "TWZ/401AA": 1161}.items():
        assert pic(p59, cat) == ("direct_product", xref), cat
    # The 6-piece set is not pictured: no tweezer picture is borrowed for it.
    assert pic(p59, "TWZ/ST-6")[0] not in SHOWN


def test_picture_inside_another_pictures_box_keeps_its_code(page_products):
    # Precision p38: two thin scribers are placed inside the box of a wider cut-out.
    p40 = page_products(PRECISION, 40)
    for cat, xref in {"MS/7/AL": 791, "MS/380A": 795, "MS/380B": 799, "MS/3/ST": 803, "MS/4": 807}.items():
        assert pic(p40, cat) == ("direct_product", xref), cat


def test_overlapping_cutouts_are_told_apart_by_their_visible_pixels(page_products):
    # Precision p58: four pin vices set diagonally; each code is printed under its own tool, inside
    # the boxes of two pictures.
    p60 = page_products(PRECISION, 60)
    for cat, xref in {"PV/1A": 1187, "MPV/4A": 1183, "PVD/02A": 1179, "PV/93": 1173}.items():
        assert pic(p60, cat) == ("direct_product", xref), cat
    # Edge finders (Precision p31): one cut-out pictures EF/1 and EF/4 together, the next EF/7 alone.
    p33 = page_products(PRECISION, 33)
    assert pic(p33, "EF/7") == ("direct_product", 665)
    assert pic(p33, "EF/1") == ("product_family", 661)
    assert pic(p33, "EF/4") == ("product_family", 661)
    assert pic(p33, "EF/11") == ("product_family", 657)
    assert pic(p33, "EF/8") == ("product_family", 657)


def test_layout_never_borrows_a_picture_labelled_for_another_product(page_products):
    # Steel body scribers are not pictured; every scriber picture is labelled for another code.
    assert pic(page_products(PRECISION, 40), "MS/MG/6")[0] not in SHOWN
    # Regular pin vices PV/2A-4A: only PV/1A is pictured.
    p60 = page_products(PRECISION, 60)
    assert pic(p60, "PV/2A")[0] not in SHOWN
    # Digital micrometers: the hero picture is labelled MMED/1/65 (the IP65 model) only.
    p19 = page_products(PRECISION, 19)
    assert pic(p19, "MMED/1/65") == ("direct_product", 336)
    assert pic(p19, "MMED/1")[0] not in SHOWN


def test_option_variants_are_whole_code_segments(page_products):
    assert pic(page_products(PRECISION, 11), "FLG/13A/100") == ("direct_product", 124)
    assert pic(page_products(PRECISION, 60), "PV/1A") == ("direct_product", 1187)
    p13 = page_products(STORAGE, 13)
    assert pic(p13, "RTC/27-30/1/GRZ") == ("direct_product", 402)
    assert pic(p13, "RTC/27-30/1B/GRZ") == ("product_family", 402)
    assert evidence(p13, "RTC/27-30/1B/GRZ").startswith("base model RTC/27-30/1/GRZ printed beside the image")


def test_label_goes_to_the_nearest_picture(page_products):
    p12 = page_products(PRECISION, 12)
    for cat, xref in {"RDG/17/1-7": 144, "RDG/16/7.5-15": 148, "RDG/15/15.5-25": 152}.items():
        assert pic(p12, cat) == ("direct_product", xref), cat
    assert pic(page_products(PRECISION, 16), "WG/R/6") == ("direct_product", 268)


def test_section_picture_above_the_products_table(page_products):
    # Estwing p4: two sections side by side; club hammers share a column with two pictures.
    e4 = page_products(ESTWING, 4)
    assert pic(e4, "ESH-624X") == ("product_family", 66)
    assert pic(e4, "ESH/SF-624X") == ("product_family", 70)
    assert pic(e4, "ECH-212X")[0] not in SHOWN
    # Estwing p5: machinist hammers are pictured as a family, not by code.
    assert pic(page_products(ESTWING, 5), "EMH-0313X") == ("product_family", 123)
    # Estwing p13: the kit is titled and pictured from its own column of a merged table.
    e13 = page_products(ESTWING, 13)
    assert pic(e13, "EKIT-2F") == ("product_family", 430)
    assert product(e13, "EKIT-2F").sub_title == "POWER DUO - 2PC KIT"
    # Tool storage: work bench and tool kit sections (not the facing lifestyle photo, p53).
    assert pic(page_products(STORAGE, 26), "WBN/79-20/2/GRZ") == ("product_family", 911)
    t27 = page_products(STORAGE, 27)
    assert pic(t27, "RTC/27-10D/65/GRZ") == ("product_family", 1093)
    assert "Automotive Tool Kit 65 Piece" in evidence(t27, "RTC/27-10D/65/GRZ")
    # Lighting p5: the speaker light, not the chapter divider photo printed on the left page.
    assert pic(page_products(LIGHTING, 5), "LED/695") == ("product_family", 3323)


def test_caption_picture(page_products):
    p61 = page_products(PRECISION, 61)
    assert pic(p61, "GAT/11") == ("product_family", 1194)
    assert "“JACOBS TAPER ARBORS”" in evidence(p61, "GAT/11")
    assert pic(p61, "G/10/M1") == ("product_family", 1206)
    assert "“TAPER SHANK ARBORS - DIN 238”" in evidence(p61, "G/10/M1")


def test_facing_page_picture(page_products):
    p57 = page_products(PRECISION, 57)
    assert pic(p57, "TB/3-75M") == ("product_family", 1098)
    assert evidence(p57, "TB/3-75M").endswith("printed on the facing page (PDF page 56)")
    assert "_p56_xref1098_" in product(p57, "TB/3-75M").images[0].file_path
    # Cut-off blades share the page but have no picture of their own.
    assert pic(p57, "COB/0-1")[0] not in SHOWN


def test_sibling_picture_only_when_one_variant_is_pictured(page_products):
    p7 = page_products(PRECISION, 7)
    assert pic(p7, "SS/A/2-3-4-6/ST") == ("direct_product", 35)
    assert pic(p7, "SS/A/2") == ("product_family", 35)
    assert "picture labelled SS/A/2-3-4-6/ST, a variant printed in the same table" in evidence(p7, "SS/A/2")
