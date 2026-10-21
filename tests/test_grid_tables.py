"""The column reader for Fluid Handling CC-07 and FUEL CAT 400 (rules 3.0.0, batch_3_fluid), checked
against pages of the real catalogues. Read-only: nothing is written."""

import json
import re

import pymupdf
import pytest

from backend.extractor.grid_tables import (contents_entries, extract_grid_rows, extract_tile_rows, printed_page_number,
                                           tag_match)
from backend.extractor.printed_titles import PageTitles

FH = "Fluid_Handling_Catalogue_spread.pdf"
FUEL = "FUEL.pdf"


@pytest.fixture(scope="module")
def fh():
    with pymupdf.open(FH) as d:
        yield d


@pytest.fixture(scope="module")
def fuel():
    with pymupdf.open(FUEL) as d:
        yield d


def rows(doc, page):
    return extract_grid_rows(doc[page - 1])


def test_paired_bsp_npt_table_with_best_seller_marks(fh):
    r = rows(fh, 11)  # G1-HD .. G18-HD: two CAT/ORD pairs, shared columns, a mark before some codes
    assert len(r) == 16
    first = r[0]
    assert (first["cat_nr"], first["ord_nr"], first["box_qty"]) == ("G1R/HD/B", "42700", 16)
    assert first["variant_label"] == '6" (150 MM) STEEL EXTENSION & COUPLER'
    assert first["column_specs"] == {"CARTRIDGE CAPACITY (OZ.)": "14", "CARTRIDGE CAPACITY (GMS)": "400",
                                     "BULK CAPACITY (CM3)": "500", "THREADS": '1/8" BSPT'}
    g4 = next(x for x in r if x["cat_nr"] == "G4R/HD/B")
    assert "CARTRIDGE CAPACITY (OZ.)" not in g4["column_specs"]  # printed "-": left out
    assert next(x for x in r if x["cat_nr"] == "G18F/HD/M")["ord_nr"] == "42763"


def test_section_rows_name_the_rows_below_them(fh):
    r = rows(fh, 17)
    assert len(r) == 18
    assert {x["table_section"] for x in r} == {"STEEL HEAD", "ALUMINUM DIE CAST HEAD", "POWDER COATED ALUMINUM DIE CAST HEAD"}


def test_two_tables_side_by_side_and_thread_labels(fh):
    r = rows(fh, 70)
    assert len(r) == 27
    m = next(x for x in r if x["cat_nr"] == "GHC-8/M")
    assert (m["ord_nr"], m["box_qty"], m["variant_label"]) == ("43611", 500, "M10 × 1")
    assert m["column_specs"] == {"LENGTH (END TO END) (INCH)": "8", "LENGTH (END TO END) (MM)": "200"}
    right = next(x for x in r if x["cat_nr"] == "GHC-12/HC/14/4/B")
    assert right["table_section"] == "HOSE WITH PROFESSIONAL 4 JAW COUPLER"
    assert right["column_specs"]["THREADS"] == '1/8" BSPT'


def test_headers_over_four_lines(fh):
    r = rows(fh, 203)
    assert len(r) == 24
    assert r[0]["column_specs"] == {
        "MAX. PRESSURE (PSI)": "300", "MAX. PRESSURE (BAR)": "21", "INLET / OUTLET THREADS (INCH)": "3/8",
        "HOSE ID (INCH)": "3/8", "HOSE ID (MM)": "9.5", "HOSE OD (INCH)": "5/8", "HOSE OD (MM)": "15.9",
        "HOSE LENGTH (M)": "10", "HOSE LENGTH (FEET)": "32.8"}
    assert (r[0]["variant_label"], r[0]["table_section"]) == ("BSPT", "AIR WATER - LOW PRESSURE HOSE REELS")


def test_sub_columns_and_sizes(fh):
    p100 = rows(fh, 100)[0]["column_specs"]
    assert p100["FOLLOWER PLATE DIMENSIONS O.D. PLATE (INCH)"] == "10-1/8"
    assert p100["FOLLOWER PLATE DIMENSIONS O.D. STEEL END (MM)"] == "230"
    reel = rows(fh, 337)[0]
    assert (reel["dimensions_inch"], reel["dimensions_mm"]) == ("14-7/8 × 7-1/4 × 13-1/4", "378 × 185 × 335")


def test_codes_without_separators_and_tables_without_an_ord_header(fh):
    assert rows(fh, 313)[0]["cat_nr"] == "R13604"
    clamps = {x["cat_nr"]: x["ord_nr"] for x in rows(fh, 333)}
    assert clamps["A2P11"] == "60670" and clamps["A2C31"] == "60610"
    no_ord = rows(fh, 204)  # the catalogue prints no ORD NR. in this table
    assert len(no_ord) == 8 and all(x["ord_nr"] is None for x in no_ord)


def test_units_printed_above_column_names_are_not_guessed(fh):
    r = rows(fh, 183)
    assert r and all(x["columns_note"] for x in r if x["table_bbox"][1] < 200)
    top = [x for x in r if x["table_bbox"][1] < 200]
    assert all(not x["column_specs"] for x in top) and all(x["box_qty"] for x in top)


def test_accessory_tiles(fh):
    tiles = extract_tile_rows(fh[337], {x["ord_nr"] for x in rows(fh, 338)})
    assert [(t["cat_nr"], t["ord_nr"]) for t in tiles][:3] == [("PS/ABG/3", "61050"), ("NZL/RT1/ABG/3", "61053"),
                                                              ("NZL/RT2/ABG/3", "61054")]
    assert tiles[0]["description"] == '4" (100 mm) dia. Protective shield for ABG/3 series Air Blow Guns'


def test_fuel_cat_400_staggered_headers(fuel):
    r = rows(fuel, 27)
    assert r[0]["column_specs"] == {"FOR USE WITH": "Diesel & Gasoline", "SPOUT TYPE": "Straight",
                                    "INLET THREADS": '3/4" NPT (F)', "SPOUT DIA (OD)": '0.83" ( 21 mm)',
                                    "SPOUT DIA (ID)": '0.63" ( 16 mm)', "MAX. FLOW RATE": "15 GPM (57 LPM)"}
    meters = rows(fuel, 28)  # "ORDERING #" instead of ORD NR.
    assert [x["ord_nr"] for x in meters] == ["45660", "45661", "45665", "45666"]


def test_whole_catalogue_against_its_numerical_index(fh):
    """Every order number the index lists that is printed on a product page is read (the 49 listed in
    the index but printed nowhere else cannot be)."""
    index = {}
    for p in range(365, 370):
        words = fh[p - 1].get_text("words")
        for w in words:
            if re.fullmatch(r"\d{5}", w[4]):
                right = [o for o in words if abs(o[1] - w[1]) < 3 and 0 < o[0] - w[2] < 60 and re.fullmatch(r"\d{1,3}", o[4])]
                if right:
                    index.setdefault(w[4], right[0][4])
    got = set()
    for pno in range(1, 365):
        r = extract_grid_rows(fh[pno - 1])
        got |= {x["ord_nr"] for x in r}
        got |= {t["ord_nr"] for t in extract_tile_rows(fh[pno - 1], set(got))}
    texts = [fh[i].get_text() for i in range(364)]
    printed = {o for o in index if any(o in t for t in texts)}
    assert len(index) == 1942
    assert printed - got == set()
    assert len(printed) >= 1890


def test_family_tags_name_their_codes():
    assert tag_match("G1-HD", "G1R/HD/B") == 4 and tag_match("G10-HD", "G10R/HD/B") == 5
    assert tag_match("G10-HD", "G1R/HD/B") == 0 and tag_match("HD", "G1R/HD/B") == 0
    assert tag_match("G1-HD", "G10R/HD/B") < tag_match("G10-HD", "G10R/HD/B")  # the more specific tag wins


def test_page_numbers_contents_and_titles(fh, fuel):
    assert [printed_page_number(fh[p - 1]) for p in (11, 200, 337)] == ["9", "198", "335"]
    assert printed_page_number(fuel[26]) == "27"
    e = contents_entries(fh, (4, 5, 6, 7))
    assert e[0] == {"title": "Lever Grease Guns - Heavy Duty", "page": 8, "contents_page": 4}
    assert {"title": "Lever Grease Gun High Pressure / High Volume", "page": 10, "contents_page": 4} in e
    t = PageTitles(fuel, FUEL).title_for(27, (40, 560, 560, 720), "27")
    assert (t["text"], t["rule"]) == ("FUEL CONTROL NOZZLES - AUTOMATIC", "contents")
    t = PageTitles(fh, FH).title_for(11, (0, 606, 467, 781), "9")
    assert (t["text"], t["rule"]) == ("Lever Grease Guns Heavy Duty", "facing")
