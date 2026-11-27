"""Workshop Tools CB-05 hammer pages (rules 3.2.0, batch_3_striking, 24 Nov 2026).

Every expected value below was read on the printed catalogue page (Hand_Tool_Catalogue_low_res_with_cover.pdf,
physical page = printed page + 2). The pages print their ordering tables in the GROZ column style
(HEAD WEIGHT over (LBS) (KG)), read with the column reader; the pictures follow the rules of batches 1-2.
"""

import re

import pymupdf
import pytest

from backend.extractor.image_extractor import ImageExtractor
from backend.extractor.product_builder import ProductBuilder
from backend.pipeline.batches import BATCHES, RESTRICTED_SOURCES

HT = "Hand_Tool_Catalogue_low_res_with_cover.pdf"


@pytest.fixture(scope="module")
def page_products(tmp_path_factory):
    """Process a page once per module; crops go to a temporary folder, never to output/."""
    builder = ProductBuilder(ImageExtractor(str(tmp_path_factory.mktemp("out") / "images")))
    doc = pymupdf.open(HT)
    cache = {}

    def get(page_no):
        if page_no not in cache:
            cache[page_no] = builder.process_page(doc[page_no - 1], HT, page_no)
        return cache[page_no]

    yield get
    doc.close()


def product(products, cat_nr):
    hits = [p for p in products if p.cat_nr == cat_nr]
    assert len(hits) == 1, f"{cat_nr}: {len(hits)} records"
    return hits[0]


def xref(p):
    return int(re.search(r"_xref(\d+)_", p.images[0].image_id).group(1)) if p.images else None


def test_the_batch_covers_the_striking_tools_pages_and_nothing_else():
    batch = BATCHES["batch_3_striking"]
    assert batch.approved and batch.output_dir is None  # part of the main dataset (output_v2)
    assert [(s.pdf, s.pages) for s in batch.sources] == [(HT, tuple(range(8, 48)))]
    assert set(range(8, 254)) == set(RESTRICTED_SOURCES[HT])  # with batch_3_workshop's pages 48-253; index and covers closed


def test_every_printed_column_is_read_with_its_printed_heading(page_products):
    # p11 (printed 9): Club Hammers, HEAD WEIGHT (LBS)(KG), OVERALL LENGTH (INCH)(MM), BOX QTY.
    p = product(page_products(11), "CHID/2.5/12")
    assert (p.ord_nr, p.box_qty, p.sub_title) == ("34500", 8, "Club Hammers Indestructible Handle")
    assert p.specifications == {"HEAD_WEIGHT_(LBS)": "2.5", "HEAD_WEIGHT_(KG)": "1.1",
                                "OVERALL_LENGTH_(INCH)": "12", "OVERALL_LENGTH_(MM)": "300"}
    # p14 (printed 12): DIN hammers print two handle lengths, L1 and L2.
    p = product(page_products(14), "SHID/DIN/3K/24")
    assert p.specifications == {"HEAD_WEIGHT_(GMS)": "3000", "HEAD_WEIGHT_(KG)": "3",
                                "HANDLE_LENGTH_L1_(INCH)": "24", "HANDLE_LENGTH_L1_(MM)": "600",
                                "HANDLE_LENGTH_L2_(INCH)": "22", "HANDLE_LENGTH_L2_(MM)": "550"}
    # p46 (printed 44): rubber mallets print a colour column and a section row per handle type.
    p = product(page_products(46), "MLTR/16B/FG")
    assert p.specifications["HEAD_COLOUR"] == "Black" and p.specifications["table_section"] == "FIBREGLASS HANDLE"


def test_a_unit_printed_without_its_opening_bracket_is_that_unit(page_products):
    # p12 (printed 10) prints "INCH)" over the length column; every other page prints "(INCH)".
    p = product(page_products(12), "SHID/6/16")
    assert p.specifications["OVERALL_LENGTH_(INCH)"] == "16" and "OVERALL_LENGTH_INCH)" not in p.specifications


def test_each_hammer_page_takes_its_main_picture(page_products):
    # The large picture of the product family on its page (checked by eye on every hammer page).
    for page, code, pic in ((11, "CHID/2.5/12", 263), (14, "SHID/DIN/3K/24", 314), (17, "MHID/DIN/300G/13", 405),
                            (18, "BPID/16/14", 421), (34, "MAUL/FG/4.5/36", 2210), (44, "AXE/HW/1.25/14", 2340),
                            # p41 prints two photos of the hammer in use right above its table (rule 7)
                            (41, "DHHW/2/11", 2302)):
        p = product(page_products(page), code)
        assert (p.images[0].association_type, xref(p)) == ("product_family", pic), code


def test_a_left_page_without_a_picture_takes_the_facing_pages_picture(page_products):
    # p12 prints the title "Sledge Hammer Indestructible Handle" and the heavy-duty table, no picture;
    # the facing p13 prints no title and the picture of both heads (heavy duty and soft face).
    p = product(page_products(12), "SHID/6/16")
    assert (p.images[0].association_type, xref(p)) == ("product_family", 289)
    assert "facing right-hand page (PDF page 13)" in p.images[0].evidence
    assert xref(product(page_products(13), "SHID/SF/6/30")) == 289


def test_no_record_without_an_order_number_and_none_invented(page_products):
    words = lambda n: {w[4] for w in pymupdf.open(HT)[n - 1].get_text("words")}
    for n in (11, 12, 13, 22, 46, 47):
        printed = words(n)
        for p in page_products(n):
            assert p.ord_nr in printed and p.cat_nr in {re.sub(r"^[^A-Z0-9]+", "", w) for w in printed}, (n, p.cat_nr)
