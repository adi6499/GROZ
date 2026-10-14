"""Safety rules of the batch pipeline (recovery, 14 Oct 2026)."""

import json
import os

import pytest

from backend.pipeline import batches as batches_mod
from backend.pipeline import runner as runner_mod
from backend.pipeline.batches import Batch, Source
from backend.pipeline.cumulative import build_cumulative
from backend.pipeline.runner import UnsafeOutputError, run_batch
from backend.reports.change_report import match_records
from backend.reports.summary import compute_metrics, write_summary_md


def _rec(pdf="a.pdf", page=1, cat="X/1", ord_nr="10001", batch="batch_1", **extra):
    r = {"source_pdf": pdf, "physical_page_number": page, "cat_nr": cat, "ord_nr": ord_nr,
         "extraction_batch": batch, "verification_status": "unverified", "images": [], "editorial_notes": [],
         "specifications": {}, "box_qty": None, "dimensions_inch": None, "dimensions_mm": None}
    r.update(extra)
    return r


def _write_batch(out, name, records):
    os.makedirs(os.path.join(out, "batches"), exist_ok=True)
    with open(os.path.join(out, "batches", f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(records, f)


def test_runner_refuses_the_legacy_output_folder():
    with pytest.raises(UnsafeOutputError):
        run_batch("batch_1", out_dir="output")
    with pytest.raises(UnsafeOutputError):
        run_batch("batch_1", out_dir=os.path.abspath("output"))


def test_unapproved_batch_does_not_run(tmp_path):
    with pytest.raises(PermissionError):
        run_batch("batch_3_pilot", out_dir=str(tmp_path / "out"))
    assert not (tmp_path / "out" / "batches").exists()


def test_supplementary_sources_never_create_records(tmp_path, monkeypatch):
    fake = {"brochure": Batch("brochure", "test", (Source("Workshop_mini-compress.pdf", (2,)),))}
    monkeypatch.setattr(runner_mod, "BATCHES", fake)
    with pytest.raises(UnsafeOutputError):
        run_batch("brochure", out_dir=str(tmp_path / "out"))


def test_batch_rerun_that_loses_records_is_refused(tmp_path, monkeypatch):
    out = str(tmp_path / "out")
    _write_batch(out, "tiny", [_rec(), _rec(ord_nr="10002")])
    # tools_storage.pdf page 1 is the cover: it yields no records, i.e. fewer than the 2 on file
    monkeypatch.setattr(runner_mod, "BATCHES", {"tiny": Batch("tiny", "test", (Source("tools_storage.pdf", (1,)),))})
    with pytest.raises(UnsafeOutputError):
        run_batch("tiny", out_dir=out, log=lambda *_: None)
    with open(os.path.join(out, "batches", "tiny.json"), encoding="utf-8") as f:
        assert len(json.load(f)) == 2  # existing batch file kept


def test_cumulative_keeps_every_batch_and_refuses_to_drop_one(tmp_path):
    out = str(tmp_path / "out")
    _write_batch(out, "batch_1", [_rec(page=1), _rec(page=2, ord_nr="10002")])
    _write_batch(out, "batch_2", [_rec(pdf="b.pdf", batch="batch_2")])
    assert len(build_cumulative(out, log=lambda *_: None)) == 3

    os.remove(os.path.join(out, "batches", "batch_2.json"))
    with pytest.raises(UnsafeOutputError):
        build_cumulative(out, log=lambda *_: None)
    with open(os.path.join(out, "extracted_products.json"), encoding="utf-8") as f:
        assert len(json.load(f)) == 3  # previous cumulative kept


def test_cumulative_refuses_the_same_page_from_two_batches(tmp_path):
    out = str(tmp_path / "out")
    _write_batch(out, "batch_1", [_rec(page=7)])
    _write_batch(out, "batch_2", [_rec(page=7, ord_nr="10009", batch="batch_2")])
    with pytest.raises(UnsafeOutputError):
        build_cumulative(out, log=lambda *_: None)


def test_batch_definitions():
    assert batches_mod.BATCHES["batch_3_pilot"].approved is False
    assert batches_mod.BATCHES["batch_3_pilot"].sources[0].pages == (8, 11, 12, 53, 224)
    lighting = [s for s in batches_mod.BATCHES["batch_1"].sources if s.pdf.startswith("GROZ_LIGHTING")][0]
    assert lighting.pages is None  # every page, so page 5 (LED/695) cannot be skipped again
    for b in batches_mod.BATCHES.values():
        assert not {s.pdf for s in b.sources} & set(batches_mod.SUPPLEMENTARY_SOURCES)


def test_summary_numbers_are_computed_from_data(tmp_path):
    recs = [_rec(), _rec(ord_nr="10002"), _rec(ord_nr=None, verification_status="needs_review"),
            _rec(ord_nr="10002", cat="X/2")]
    m = compute_metrics(recs)
    assert (m["records"], m["unique_ords"], m["records_with_ord"]) == (4, 2, 3)
    assert m["duplicate_ords"] == {"10002": [("a.pdf", 1, "X/1"), ("a.pdf", 1, "X/2")]}
    assert m["verification_status"] == {"unverified": 3, "needs_review": 1}
    path = tmp_path / "summary.md"
    write_summary_md(str(path), recs, {}, {}, [])
    text = path.read_text(encoding="utf-8")
    assert "| **Total** | **4** |" in text and "3 unverified, 1 needs_review" in text


def test_change_matching_follows_corrected_cat_numbers():
    legacy = [_rec(cat="10/M1", ord_nr="07700"), _rec(cat="LED/1", ord_nr=None), _rec(cat="OLD/1", ord_nr="20000")]
    new = [_rec(cat="G/10/M1", ord_nr="07700"), _rec(cat="LED/1", ord_nr=None), _rec(cat="NEW/1", ord_nr="30000")]
    pairs, missing, added = match_records(legacy, new)
    assert {(o["cat_nr"], n["cat_nr"]) for o, n, _ in pairs} == {("10/M1", "G/10/M1"), ("LED/1", "LED/1")}
    assert [r["cat_nr"] for r in missing] == ["OLD/1"] and [r["cat_nr"] for r in added] == ["NEW/1"]
