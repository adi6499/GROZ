"""Safety rules of the batch pipeline (recovery, 14 Oct 2026)."""

import json
import os

import pytest

import dataclasses

from backend.pipeline import batches as batches_mod
from backend.pipeline import runner as runner_mod
from backend.pipeline.batches import BATCHES, Batch, Source
from backend.pipeline.cumulative import build_cumulative
from backend.pipeline.runner import UnsafeOutputError, check_sources, run_batch, sha256_file
from backend.reports.change_report import match_records, write_change_report
from backend.reports.editorial import index_discrepancies, load_decisions
from backend.reports.pilot_report import analyse
from backend.reports.summary import compute_metrics, write_summary_md
from backend.validator.coverage import coverage_report
import run_extraction

HAND_TOOL = "Hand_Tool_Catalogue_low_res_with_cover.pdf"


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


@pytest.fixture
def no_extraction(monkeypatch):
    """Make any page extraction fail loudly, so a gate test can never produce pilot records."""
    from backend.extractor.product_builder import ProductBuilder

    def refuse(*_a, **_k):
        raise AssertionError("extraction must not start in a gate test")
    monkeypatch.setattr(ProductBuilder, "process_page", refuse)


def test_unapproved_batch_does_not_run(no_extraction):
    pilot_dir = BATCHES["batch_3_pilot"].output_dir
    existed = os.path.exists(pilot_dir)
    with pytest.raises(PermissionError):
        run_batch("batch_3_pilot")
    assert os.path.exists(pilot_dir) == existed  # nothing created


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


# --- Hand Tool pilot preparation (14 Oct 2026): safety properties, checked without extracting it ---

def _approved_pilot(monkeypatch):
    patched = dict(runner_mod.BATCHES)
    patched["batch_3_pilot"] = dataclasses.replace(patched["batch_3_pilot"], approved=True)
    monkeypatch.setattr(runner_mod, "BATCHES", patched)


def test_pilot_is_unapproved_and_has_its_own_output_folder():
    pilot = BATCHES["batch_3_pilot"]
    assert pilot.approved is False
    assert pilot.output_dir == "output_pilot_handtool"
    assert {runner_mod.batch_output_dir(BATCHES[n]) for n in ("batch_1", "batch_2")} == {"output_v2"}


@pytest.mark.parametrize("target", ["output_v2", "output", "some_other_folder"])
def test_pilot_cannot_write_anywhere_else_even_when_approved(monkeypatch, no_extraction, target):
    _approved_pilot(monkeypatch)
    with pytest.raises(UnsafeOutputError):
        run_batch("batch_3_pilot", out_dir=target)


def test_main_batches_cannot_write_into_the_pilot_folder(no_extraction):
    with pytest.raises(UnsafeOutputError):
        run_batch("batch_1", out_dir="output_pilot_handtool")


def test_command_line_has_no_approval_bypass(no_extraction, capsys):
    with pytest.raises(SystemExit):  # the old --allow-unapproved flag no longer exists
        run_extraction.main(["batch", "batch_3_pilot", "--allow-unapproved"])
    with pytest.raises(PermissionError):
        run_extraction.main(["batch", "batch_3_pilot"])
    run_extraction.main(["status"])
    out = capsys.readouterr().out
    assert "batch_3_pilot   BLOCKED" in out and "not approved" in out


@pytest.mark.parametrize("pdf,pages", [
    (HAND_TOOL, (13,)),                                 # a Hand Tool page outside the pilot = Batch 3
    (HAND_TOOL, None),                                  # the whole Hand Tool catalogue = Batch 3
    ("Fluid_Handling_Catalogue_spread.pdf", (10,)),     # Fluid Handling = Batch 3
    ("Workshop_mini-compress.pdf", (2,)),               # brochure
    ("Fluid_Handling_mini_min_2.pdf", (2,)),            # brochure
])
def test_batch_3_and_brochures_cannot_run(pdf, pages):
    with pytest.raises(UnsafeOutputError):
        check_sources(Batch("x", "test", (Source(pdf, pages),)))


def test_pilot_pages_pass_the_source_check():
    check_sources(BATCHES["batch_3_pilot"])  # allowed pages only; approval is a separate gate


def test_cumulative_never_merges_the_pilot(tmp_path):
    out = str(tmp_path / "out")
    _write_batch(out, "batch_1", [_rec()])
    _write_batch(out, "batch_3_pilot", [_rec(pdf=HAND_TOOL, batch="batch_3_pilot")])
    with pytest.raises(UnsafeOutputError):
        build_cumulative(out, log=lambda *_: None)


def test_manifest_records_provenance_and_previous_runs_are_archived(tmp_path, monkeypatch):
    out = str(tmp_path / "out")
    monkeypatch.setattr(runner_mod, "BATCHES", {"tiny": Batch("tiny", "test", (Source("tools_storage.pdf", (1,)),))})
    run_batch("tiny", out_dir=out, log=lambda *_: None)
    run_batch("tiny", out_dir=out, log=lambda *_: None)
    with open(os.path.join(out, "batches", "tiny.manifest.json"), encoding="utf-8") as f:
        mf = json.load(f)
    assert mf["pipeline_version"] == runner_mod.PIPELINE_VERSION and mf["code_version"]
    assert mf["source_pdfs"]["tools_storage.pdf"]["sha256"] == sha256_file("tools_storage.pdf")
    assert mf["pages_processed"] == {"tools_storage.pdf": [1]} and mf["approved"] is True
    history = os.listdir(os.path.join(out, "batches", "history"))
    assert any(h.endswith(".json") and not h.endswith(".manifest.json") for h in history)


def test_pilot_report_flags_counterparts_ambiguity_and_unresolved_images():
    unresolved = [{"association_type": "unresolved", "file_path": "images/x.png"}]
    pilot = [_rec(pdf=HAND_TOOL, page=224, cat="ID/3", ord_nr="01400", box_qty=100, images=unresolved),
             _rec(pdf=HAND_TOOL, page=12, cat="SHID/6/16", ord_nr="34521"),
             _rec(pdf=HAND_TOOL, page=12, cat="SHID/6/17", ord_nr="34521")]
    other = [_rec(pdf="Precision_Catalogue_CA_03.pdf", page=10, cat="ID/3", ord_nr="01400", box_qty=200)]
    res = analyse(pilot, {"output_v2": other})
    row = res["rows"][0]
    assert row["counterparts"] and "box_qty: 200 vs 100" in row["counterparts"][0][2]
    assert any("printed for 2 pilot records" in a for x in res["ambiguous"] for a in x["ambiguous"])
    assert [x["record"]["cat_nr"] for x in res["unresolved_images"]] == ["ID/3"]
    assert res["missing_counts"]["image"] == 2


def test_index_check_is_scoped_to_the_pages_processed():
    """Partial run: only ORDs the index places on the processed printed pages are expected."""
    import pymupdf
    pdf = "Precision_Catalogue_CA_03.pdf"
    with pymupdf.open(pdf) as doc:
        printed = {p: {w[4] for w in doc[p - 1].get_text("words") if w[4].isdigit() and len(w[4]) == 5} for p in (14, 77)}
    recs = [_rec(pdf=pdf, page=p, cat=f"X/{o}", ord_nr=o) for p, os_ in printed.items() for o in os_]
    idx = coverage_report(recs, {pdf: [14, 77]})[pdf]["index"]
    assert idx["scope"] == "printed pages ['12', '75']"
    assert set(idx["missing_from_dataset"]) == {"01217", "35044", "35045"}


def test_index_discrepancy_list_for_precision():
    with open(os.path.join("output_v2", "extracted_products.json"), encoding="utf-8") as f:
        records = json.load(f)
    rows = index_discrepancies(records, "Precision_Catalogue_CA_03.pdf")
    kinds = {}
    for r in rows:
        kinds.setdefault(r["type"], []).append(r["ord_nr"])
    assert sorted(kinds["in index, not printed on any product page"]) == ["01217", "35044", "35045"]
    assert len(kinds["printed on a product page, not in index"]) == 29
    pair = next(r for r in rows if r["ord_nr"] == "01227")
    assert "01217" in pair["note"]


def test_decision_log_is_complete():
    decisions = {d["id"]: d for d in load_decisions()}
    assert set(decisions) >= {"A", "B", "C"}
    for d in decisions.values():
        assert d["status"] and d["evidence"] and d["current"] and d["proposal"]


def test_change_report_documents_decisions_and_index_discrepancies(tmp_path):
    legacy, new = tmp_path / "legacy.json", tmp_path / "new.json"
    legacy.write_text(json.dumps([_rec(pdf="tools_storage.pdf", page=4, cat="RTC/27-10D/1/GRZ", ord_nr="75000")]))
    new.write_text(json.dumps([_rec(pdf="tools_storage.pdf", page=4, cat="RTC/27-10D/1/GRZ", ord_nr="75000")]))
    disc = [{"type": "in index, not printed on any product page", "source_pdf": "x.pdf", "ord_nr": "01217",
             "cat_nr": "", "physical_page": "14", "printed_page": "12", "index_page_ref": "12", "note": ""}]
    write_change_report(str(tmp_path), str(legacy), str(new), decisions=load_decisions(), discrepancies=disc)
    text = (tmp_path / "reports" / "change_report.md").read_text(encoding="utf-8")
    assert "## 15. Editorial decisions" in text and "## 16. Catalogue index discrepancies" in text
    assert (tmp_path / "reports" / "index_discrepancies.csv").exists()
