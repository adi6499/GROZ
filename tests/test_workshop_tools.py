"""Workshop Tools CB-05, the pages after the hammers (rules 3.3.0, batch_3_workshop, 27 Nov 2026).

Every expected value below was read on the printed catalogue page (Hand_Tool_Catalogue_low_res_with_cover.pdf,
physical page = printed page + 2). The tables are read with the column reader of batch_3_striking; rules 3.3.0
add the catalogue's sets and kits printed as tiles, tables printed side by side, tall rows, set rows and the
picture rules 7 (limited), 8 and 9 (backend/extractor/image_sections.py).
"""

import re

import pymupdf
import pytest

from backend.extractor.grid_tables import extract_grid_rows, extract_set_tiles
from backend.extractor.image_extractor import ImageExtractor
from backend.extractor.product_builder import ProductBuilder
from backend.extractor.table_extractor import TableExtractor
from backend.pipeline.batches import BATCHES, RESTRICTED_SOURCES
from backend.site.catalogue_export import HT_PDF, category_for, workshop_repeats
from backend.validator.coverage import _five_digit, _printed_words

HT = "Hand_Tool_Catalogue_low_res_with_cover.pdf"


@pytest.fixture(scope="module")
def doc():
    d = pymupdf.open(HT)
    yield d
    d.close()


@pytest.fixture(scope="module")
def page_products(tmp_path_factory, doc):
    """Process a page once per module; crops go to a temporary folder, never to output/."""
    builder = ProductBuilder(ImageExtractor(str(tmp_path_factory.mktemp("out") / "images")))
    cache = {}

    def get(n):
        if n not in cache:
            cache[n] = builder.process_page(doc[n - 1], HT, n)
        return cache[n]

    return get


def rows_of(doc, n):
    return TableExtractor.extract_ordering_records(doc[n - 1], HT, n)


def one(items, cat_nr):
    hits = [p for p in items if (p["cat_nr"] if isinstance(p, dict) else p.cat_nr) == cat_nr]
    assert len(hits) == 1, f"{cat_nr}: {len(hits)}"
    return hits[0]


def xref(p):
    return int(re.search(r"_xref(\d+)_", p.images[0].image_id).group(1)) if p.images else None


def test_the_batch_covers_the_product_pages_after_the_hammers():
    b = BATCHES["batch_3_workshop"]
    assert b.approved and b.output_dir is None
    assert [(s.pdf, s.pages) for s in b.sources] == [(HT, tuple(range(48, 254)))]
    assert set(RESTRICTED_SOURCES[HT]) == set(range(8, 254))  # the index (254-257) and covers stay closed


def test_every_printed_order_number_is_read_and_none_is_added(doc):
    # Five-digit numbers printed on these pages that are not order numbers: lifting capacities in kg of the
    # bottle jacks (p127), "IEC 60900" and "10000 Volt" (p132), and the label printed on a blade in a
    # photo (p86; the table lists the blades 30460-30483).
    not_products = {127: {"10886", "18144", "29030", "45359"}, 132: {"10000", "60900"}, 86: {"30473"}}
    for n in range(48, 254):
        printed = _five_digit(_printed_words(doc[n - 1]))
        got = {r["ord_nr"] for r in rows_of(doc, n) if r.get("ord_nr")}
        assert got <= printed, f"p{n}: order numbers not printed on the page: {got - printed}"
        assert printed - got == not_products.get(n, set()), f"p{n}: not read: {printed - got}"


def test_sets_and_kits_printed_as_tiles(doc):
    # p150 (printed 148): HEX SOCKET SET / KIT/SKT/H/1-4/19/UG / ORD NR. 40193 / BOX QTY. 10, its DESCRIPTION box.
    r = one(rows_of(doc, 150), "KIT/SKT/H/1-4/19/UG")
    assert (r["ord_nr"], r["box_qty"], r["description"]) == ("40193", 10, "HEX SOCKET SET")
    assert r["column_specs"]["DESCRIPTION"].startswith("13 pcs Hex Sockets: 4, 4.5, 5, 5.5, 6, 7, 8, 9, 10, 11, 12, 13, 14 mm; 1 pc Ratchet Handle")
    # p67 (printed 65): KIT/26/ST, "26 pc punch & chisel set", Ord Nr. 33004, Box Qty. 6.
    r = one(rows_of(doc, 67), "KIT/26/ST")
    assert (r["ord_nr"], r["box_qty"], r["description"]) == ("33004", 6, "26 pc punch & chisel set")
    # p129 (printed 127): the name printed under the code.
    r = one(rows_of(doc, 129), "ALN/HX-BL/9EL/GRZ")
    assert (r["ord_nr"], r["box_qty"], r["description"]) == ("36103", 48, "9 Hex Keys with Ball End - Extra Long - Metric")
    # p152 (printed 150): DESCRIPTION boxes side by side each stay with their own column of sets.
    assert one(rows_of(doc, 152), "KIT/SKT/H/3-8/8L/UG")["column_specs"]["DESCRIPTION"] == "8 pcs Sockets: 6, 8, 10, 12, 13, 14, 17, 19 mm"
    assert one(rows_of(doc, 152), "KIT/SKT/H/1-4/9LH/UG")["column_specs"]["DESCRIPTION"] == (
        "8 pcs Hex Sockets : 4, 4.5, 5, 5.5, 6, 7, 8, 10 mm; 1 pc Ratchet Handle")
    # the tiles are read only in this catalogue
    assert extract_set_tiles(doc[149], set())  # and the function itself works on the page


def test_metric_and_imperial_tables_printed_side_by_side(doc):
    # p200 (printed 198): METRIC CAT/ORD/SIZE (MM) beside IMPERIAL CAT/ORD/SIZE (INCH), LENGTH, BOX QTY.
    rows = rows_of(doc, 200)
    r = one(rows, "CSP/XRT/5-16/UG")
    assert (r["ord_nr"], r["dimensions_inch"], r["box_qty"], r["table_section"]) == ("33961", "5/16", 200, "IMPERIAL SIZES")
    assert r["column_specs"] == {"LENGTH (L) (MM)": "148", "LENGTH (L) (INCH)": "5-27/32"}
    r = one(rows, "CSP/XRT/8/UG")
    assert (r["ord_nr"], r["dimensions_mm"], r["table_section"]) == ("33862", "8", "METRIC SIZES")
    # a sentence printed across the row is the row's description (spelt as printed)
    assert one(rows, "CSS/XRT/7ST/UG")["description"] == "Set of 7 extra long Ratching Spanners in metric sizes, 8- 19 mm"
    assert "CSP/XRT/12/UG" in {x["cat_nr"] for x in rows} and len(rows) == 14  # "-" in the imperial column: no product


def test_tall_rows_with_their_contents(doc):
    # p235 (printed 233): tap & die sets; each set's CONSTITUENTS run over many lines, its code and order
    # number centred in the row (TDE/41/M/ST's ORD 10014 is printed two lines below its code).
    rows = rows_of(doc, 235)
    i, m = one(rows, "TDE/41/I/ST"), one(rows, "TDE/41/M/ST")
    assert (i["ord_nr"], i["box_qty"], m["ord_nr"], m["box_qty"]) == ("10015", 10, "10014", 10)
    assert i["column_specs"]["CONSTITUENTS"].startswith('T handle Tap Wrench 0 - 1/4"')
    assert i["column_specs"]["CONSTITUENTS"].endswith('7/16"-20 NF, 1/2"-13 NC, 1/2"-20 NF')
    assert m["column_specs"]["CONSTITUENTS"].startswith('T handle Tap Wrench 0 - 1/4"')
    assert m["column_specs"]["CONSTITUENTS"].endswith('12mm - 1.75mm, 1/8" - 28mm BSP')


def test_set_rows_read_as_one_description(doc):
    # p55 (printed 53): "5 pc set - packed in a vinyl pouch" over the sizes printed across the columns.
    r = one(rows_of(doc, 55), "DFP/5B/ST")
    assert r["description"] == '5 pc set - packed in a vinyl pouch: 1/4" (6mm), 3/8" (10mm), 1/2" (12mm), 5/8" (16mm), 3/4" (19mm)'
    assert r["column_specs"] == {} and r["box_qty"] == 20
    # p114 (printed 112): a set sentence printed in a length column, over two lines.
    r = one(rows_of(doc, 114), "HPR/6/ST")
    assert r["description"] == '6 Pc Set: 8" (200 mm), 12" (300 mm), 18" (450 mm), 24" (600 mm), 32" (800 mm) & 36" (900 mm)'
    # p28 (a hammer page, batch_3_striking): the hammer sets' sentence is no longer cut into head weights.
    r = one(rows_of(doc, 28), "BPFG/ST/3")
    assert r["description"] == "3 pc set Includes sizes - 24, 32, 48oz." and r["column_specs"] == {}


def test_column_names_as_printed_and_meant(doc):
    # p175 (printed 173): units printed beside "TORQUE RANGE" belong to it.
    r = one(rows_of(doc, 175), "TQW/DI-M/3-8/135")
    assert r["column_specs"]["TORQUE RANGE (NM)"] == "6.8 - 135" and r["column_specs"]["TORQUE RANGE (KG-CM)"] == "69 - 1378"
    assert r["column_specs"]["SQUARE DRIVE (INCH)"] == "3/8"
    # p125 (printed 123): "(OZ)" and "(KG)" beside HEAD WT. over "(LB)"; BOX QTY. heads no column.
    r = one(rows_of(doc, 125), "BRH/6OZ")
    assert r["column_specs"] == {"HEAD WT. (OZ)": "6", "HEAD WT. (KG)": "0.170"} and r["box_qty"] == 80
    # p93 (printed 91) prints "(MM)S"; p107 prints "( MM)"; p236 "TPI (THREAD PER INCH)".
    assert one(rows_of(doc, 93), "BNV/F/100")["column_specs"]["JAW WIDTH (MM)"] == "100"
    assert one(rows_of(doc, 107), "KBC/12")["column_specs"]["CLAMPING CAPACITY (MM)"] == "300"
    assert one(rows_of(doc, 236), "TAP/1-16")["column_specs"] == {"NOMINAL SIZE (INCH)": "1/16", "TPI (THREAD PER INCH)": "60"}
    # p79 (printed 77): a description printed on past its column keeps all its words.
    r = one(rows_of(doc, 79), "HF/12/RB")
    assert r["description"] == "Black powder coated frame with red handle" and r["column_specs"]["OVERALL LENGTH (INCH)"] == "17-5/16"


def test_pictures(page_products):
    # p139: the deep hex socket's own photo above its table, not the "Professional Quality SOCKETS" photo beside it.
    assert xref(one(page_products(139), "SKT/H/1-2/10D/UG")) == 4695
    # p140: hex and bi-hex socket tables printed side by side each keep their own photo.
    assert xref(one(page_products(140), "SKT/H/3-4/22/MT")) == 4735
    assert xref(one(page_products(140), "SKT/BH/3-4/22/MT")) == 4739
    # p141: the 1" sockets above the "Socket Merchandiser" title take the photos over their tables.
    assert xref(one(page_products(141), "SKT/BH/0-1/36/MT")) == 4774
    # p151: each pair of sets takes the photo printed beside it.
    assert xref(one(page_products(151), "KIT/SKT/H/1-2/13/UG")) == 5230
    assert xref(one(page_products(151), "KIT/SKT/BH/1-2/27/UG")) == 5226
    # p88: the facing page's full-page chapter divider is never a product's photo (rules 3.3.0) ...
    assert "xref3450" not in one(page_products(88), "FSB/3/ST").images[0].image_id


def test_rows_of_upright_pictures_are_one_picture(page_products):
    # Rules 3.3.1: saw blades and rules are pictured upright, side by side (one blade's picture printed
    # several times in a row); the row is the product family's picture, cut out together.
    for page, code, row in ((87, "HB/C/01/ST", "row3397"), (88, "FSB/3/ST", "row3436"), (88, "CSB/170/ST", "row3444"),
                            (231, "SR/12", "row7180")):
        p = one(page_products(page), code)
        assert row in p.images[0].image_id and p.images[0].association_type == "product_family", code
    # the steel rules' row is three rules wide, not one strip
    bb = one(page_products(231), "SR/12").images[0].bounding_box
    assert bb.x1 - bb.x0 > 80 and bb.y1 - bb.y0 > 250


def test_chapters_are_categories():
    cat = lambda label: category_for({"source_pdf": HT_PDF, "catalog_page_label": label}, None)
    assert [cat(x) for x in ("9", "65", "77", "92", "113", "136", "158", "173", "185", "199", "210", "224", "236", "245")] == [
        "Striking Tools", "Striking Tools", "Hacksaw Frames & Blades", "Vices & Clamps", "Automotive Tools & Accessories",
        "Sockets & Accessories", "Impact & Ratchet Wrenches", "Torque Tools", "Tool Storage", "Spanners & Wrenches",
        "Pliers & Cutters", "Measuring & Marking", "Taps, Dies & Holders", "Specialty Hand Tools"]


def test_products_printed_again_are_shown_once():
    rec = lambda pdf, page, cat, ord_nr: {"source_pdf": pdf, "physical_page_number": page, "cat_nr": cat, "ord_nr": ord_nr}
    precision = rec("Precision_Catalogue_CA_03.pdf", 7, "SS/A/2", "01000")
    again = rec(HT, 226, "SS/A/2", "01000")
    blade1, blade2, blade3 = rec(HT, 218, "BLD/KNV/5/ST", "61511"), rec(HT, 218, "BLD/KNV/5/ST", "61511"), rec(HT, 220, "BLD/KNV/5/ST", "61511")
    own = rec(HT, 100, "SP/3", "37800")
    left_out = workshop_repeats([precision, again, blade3, blade1, blade2, own])
    assert again in left_out and own not in left_out and precision not in left_out
    assert sum(1 for r in left_out if r["cat_nr"] == "BLD/KNV/5/ST") == 2  # the first printing (p218) is shown
