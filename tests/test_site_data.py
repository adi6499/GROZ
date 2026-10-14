"""The website's data export must be a faithful, read-only view of the extraction dataset."""

import csv
import hashlib
import json
import os
import re

import pymupdf
import pytest

from backend.site.catalogue_export import (CATALOGUES, DATASET, SITE_DATA, TITLE_REVIEW, build, heading_text,
                                           load_pending_corrections, title_review_rows)
from backend.site.titles import relation


@pytest.fixture(scope="module")
def source():
    with open(DATASET, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def site(source):
    with open(DATASET, "rb") as f:
        before = hashlib.sha256(f.read()).hexdigest()
    data = build()
    with open(DATASET, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == before, "building site data must not modify the dataset"
    return data


def test_every_record_exported_once_with_its_own_identifiers(source, site):
    products = site["products"]
    assert len(products) == len(source) == site["meta"]["records"]
    assert len({p["id"] for p in products}) == len(products)
    for r, p in zip(source, products):
        assert (p["cat_nr"], p["ord_nr"], p["page"], p["catalogue"]["pdf"]) == (
            r["cat_nr"], r["ord_nr"], r["physical_page_number"], r["source_pdf"])
        assert (p["dimensions_inch"], p["dimensions_mm"], p["box_qty"]) == (r["dimensions_inch"], r["dimensions_mm"], r["box_qty"])


def test_no_specification_is_invented(source, site):
    for r, p in zip(source, site["products"]):
        shown = {s["key"]: s["value"] for s in p["specs"]}
        withheld = {u["key"] for u in p["under_review"]}
        assert set(shown) | withheld == {k for k, v in r["specifications"].items() if v not in (None, "")}
        for key, value in shown.items():
            assert value == str(r["specifications"][key])


def test_verification_status_and_review_notes_pass_through(source, site):
    for r, p in zip(source, site["products"]):
        assert p["status"] == r["verification_status"]
        assert len(p["notes"]) == len(r["editorial_notes"])
    assert site["meta"]["verified"] == sum(1 for r in source if r["verification_status"] == "verified")


def test_only_supported_image_associations_are_shown(source, site):
    for r, p in zip(source, site["products"]):
        allowed = [im for im in r["images"] if im["association_type"] in ("direct_product", "product_family")]
        if not allowed:
            assert p["image"] is None
            assert p["image_candidate_unconfirmed"] == any(im["association_type"] == "unresolved" for im in r["images"])
        else:
            assert p["image"]["evidence"] == allowed[0]["association_type"]
            path = p["image"]["src"].replace("../", "", 1)
            assert os.path.isfile(path)


def test_values_awaiting_a_pending_correction_are_withheld(site):
    pending = load_pending_corrections()
    by_key = {(p["catalogue"]["pdf"], p["page"], p["cat_nr"]): p for p in site["products"]}
    assert pending, "review/preview_*.csv should list the pending corrections"
    for (pdf, page, cat, key) in pending:
        p = by_key[(pdf, page, cat)]
        assert key not in {s["key"] for s in p["specs"]}
    led621 = by_key[("GROZ_LIGHTING_GL-10_1.pdf", 12, "LED/621")]
    assert "beam_angle" in {u["key"] for u in led621["under_review"]}  # dataset value "270°" is a callout
    led680 = by_key[("GROZ_LIGHTING_GL-10_1.pdf", 8, "LED/680")]
    assert {s["key"]: s["value"] for s in led680["specs"]}.get("beam_angle") == "120°"  # glyph-only change: shown


def test_categories_follow_the_source_catalogue(source, site):
    for r, p in zip(source, site["products"]):
        assert p["category"] == CATALOGUES[r["source_pdf"]]["category"]
    assert sum(c["records"] for c in site["categories"]) == len(source)


def test_committed_site_data_matches_the_dataset(site):
    """Guards against a stale site/data/catalogue.json: rebuild with `python build_site_data.py`."""
    with open(SITE_DATA, encoding="utf-8") as f:
        committed = json.load(f)
    assert committed["meta"]["dataset_sha256"] == site["meta"]["dataset_sha256"]
    assert committed["products"] == site["products"]


def test_committed_title_review_matches(site):
    with open(TITLE_REVIEW, encoding="utf-8-sig", newline="") as f:
        committed = list(csv.DictReader(f))
    expected = [{k: str(v) for k, v in row.items()} for row in title_review_rows(site)]
    assert committed == expected


# ---------------------------------------------------------------- display titles (read from the PDFs)

# Checked against the rendered catalogue pages (see review/editorial_decisions.json, decision F).
PRINTED_TITLES = [
    ("Estwing_Hammer_E-03_Interactive_1.pdf", "ECH-212X", "CLUB HAMMERS", "above"),
    ("Estwing_Hammer_E-03_Interactive_1.pdf", "ESH-1030X", "SLEDGE HAMMERS", "above"),
    ("Estwing_Hammer_E-03_Interactive_1.pdf", "ESH/SF-1030X", "SLEDGE HAMMERS - SOFT FACE", "above"),
    ("Estwing_Hammer_E-03_Interactive_1.pdf", "ETH-520X", "TIRE BEAD BREAK HAMMERS", "above"),
    ("Estwing_Hammer_E-03_Interactive_1.pdf", "EMH-0313X", "MACHINIST HAMMERS", "above"),
    ("Estwing_Hammer_E-03_Interactive_1.pdf", "ESAB-72", "SAN ANGELO BAR", "above"),
    ("Estwing_Hammer_E-03_Interactive_1.pdf", "EPHD-69", "POST HOLE DIGGING BAR", "above"),
    ("Precision_Catalogue_CA_03.pdf", "VB/C/2", "Vee Blocks Cast Iron", "above"),
    ("Precision_Catalogue_CA_03.pdf", "PAB/01/A", "Adjustable Angle Block 0-60°", "above"),
    ("Precision_Catalogue_CA_03.pdf", "SS/A/2", "Engineer’s Precision Squares", "facing"),
    ("Precision_Catalogue_CA_03.pdf", "COB/0-1", "Tool Bits & Cut Off Blades", "facing"),
    ("Precision_Catalogue_CA_03.pdf", "TB/0-1", "Tool Bits & Cut Off Blades", "above"),
    ("GROZ_LIGHTING_GL-10_1.pdf", "LED/550", "Worklight Impact Resistant", "above"),
    ("GROZ_LIGHTING_GL-10_1.pdf", "LED/621", "Worklight 270° Swivelling with Magnetic Base", "above"),
    ("GROZ_LIGHTING_GL-10_1.pdf", "LED/685T", "Cordless Sitelamp 3 Head Design", "spread"),
    ("tools_storage.pdf", "RTC/27-10/3/GRZ", '27" Rolling Tool Cabinets S10 Series', "spread"),
]


@pytest.mark.parametrize("pdf,cat_nr,title,rule", PRINTED_TITLES)
def test_display_title_is_the_title_printed_for_the_product(site, pdf, cat_nr, title, rule):
    p = next(p for p in site["products"] if p["catalogue"]["pdf"] == pdf and p["cat_nr"] == cat_nr)
    assert (p["title"], p["title_source"]["rule"]) == (title, rule)


def test_every_display_title_is_printed_on_its_cited_page(site):
    words = lambda s: re.findall(r"[0-9a-z]+", s.lower().replace("’", "'"))
    pages = {}
    for p in site["products"]:
        assert p["title"] and p["title_source"]["rule"] in {"above", "page", "spread", "facing"}
        key = (p["catalogue"]["pdf"], p["title_source"]["pdf_page"])
        if key not in pages:
            with pymupdf.open(key[0]) as doc:
                pages[key] = " ".join(words(doc[key[1] - 1].get_text()))
        assert " ".join(words(p["title"])) in pages[key], (p["cat_nr"], p["title"], key)
        assert f"PDF page {key[1]}" in p["title_source"]["evidence"]
        if p["title_source"]["rule"] != "facing":
            assert key[1] == p["page"]


def test_extracted_heading_is_kept_alongside_the_title(source, site):
    for r, p in zip(source, site["products"]):
        assert p["heading"] == heading_text(r)
        assert p["heading_relation"] == relation(r.get("sub_title"), p["title"])


@pytest.mark.parametrize("extracted,printed,expected", [
    ("Tweezers", "Tweezers", "same"),
    ("Machinist’s Squares Excellent range of general purpose", "Machinist's Squares", "cleaned"),
    ("Floodlight", "Floodlight 12W", "expanded"),
    ("BS 876 SLEDGE HAMMERS •", "CLUB HAMMERS", "different"),
    ("SLEDGE HAMMERS - SOFT FACE", "SLEDGE HAMMERS - BRASS", "different"),
    (None, "Tool Bits & Cut Off Blades", "added"),
    ("Anything", None, "none"),
])
def test_heading_relation(extracted, printed, expected):
    assert relation(extracted, printed) == expected
