"""The website's data export must be a faithful, read-only view of the extraction dataset."""

import hashlib
import json
import os

import pytest

from backend.site.catalogue_export import CATALOGUES, DATASET, SITE_DATA, build, load_pending_corrections


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
