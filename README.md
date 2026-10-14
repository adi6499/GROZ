# GROZ Product Catalogue — extraction pipeline

Extracts product records (CAT NR, ORD NR, dimensions, box quantity, specifications, images) from the
official GROZ catalogue PDFs, with full source traceability. The printed catalogue is the source of
truth: values are never silently corrected, suspected catalogue errors go into `editorial_notes`, and
no record is ever marked `verified` automatically.

- `PROJECT_HANDOFF_AUDIT.md`: audit of the project as received from Google Antigravity.
- `RECOVERY_REPORT.md`: the defect fixes, re-extraction results and open review items (14 Oct 2026).

## Setup (Windows)

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
```

- Tested with Python 3.13.14 on Windows 11, and Python 3.12.3 on Linux (original run).
- `venv/` is the original **Linux** environment and does not work on Windows; use `.venv/`. Both are git-ignored.
- OCR (`rapidocr-onnxruntime`) is optional, needs Python <= 3.12, and is only used by `run_prototype.py`.

Run every command from the project root (all paths are relative to it).

## Tests

```bash
.venv/Scripts/python.exe -m pytest -q
```

Tests never write into `output/` or `output_v2/`; image crops go to pytest temporary folders.

| File | What it covers |
|---|---|
| `tests/test_schema.py`, `tests/test_extraction.py` | Original 35 tests (4 image expectations updated during recovery, each commented) |
| `tests/test_recovery_regressions.py` | One or more tests per confirmed defect, with expected values read from the printed pages |
| `tests/test_pipeline_safety.py` | Output-folder guard, approval gate, no record loss, no double extraction, computed reports |

## Extraction commands

```bash
.venv/Scripts/python.exe run_extraction.py list
.venv/Scripts/python.exe run_extraction.py batch batch_1
.venv/Scripts/python.exe run_extraction.py batch batch_2
.venv/Scripts/python.exe run_extraction.py compare
.venv/Scripts/python.exe run_extraction.py recovery
```

- `list` shows the batches and whether each is approved.
- `batch NAME` extracts one batch, rebuilds the cumulative file and regenerates the reports. `run_batch_1.py` and `run_batch_2.py` do the same for their batch.
- `compare` writes the change report against the legacy 813-record dataset.
- `recovery` runs batch_1 and batch_2, then the cumulative build, the comparison and the reports.

Options: `--out DIR` (default `output_v2`), `--allow-shrink`, `--allow-unapproved`.

### Safe execution rules (enforced by the code)

1. Nothing ever writes into the legacy `output/` folder; the runner refuses it.
2. A batch writes only `output_v2/batches/<batch>.json` and its manifest (pages processed, code commit).
3. The cumulative file `output_v2/extracted_products.json` is rebuilt from the batch files. It refuses to drop a batch or lose records, and refuses the same page extracted by two batches. `--allow-shrink` overrides this only for an intended reduction.
4. Re-running a batch that would produce fewer records than its existing file is refused (same override).
5. A batch marked not approved (`batch_3_pilot`) refuses to run. On approval, set `approved=True` in `backend/pipeline/batches.py` and commit, then run it.
6. Supplementary brochures (`Workshop_mini-compress.pdf`, `Fluid_Handling_mini_min_2.pdf`) can never create product records.
7. Every report number is computed from the data when the report is generated.

Safe order: `batch batch_1` and `batch batch_2` (any order, independently) → `compare` → review.

## Batches

| Batch | Scope | Status |
|---|---|---|
| `batch_1` | `tools_storage.pdf` + `GROZ_LIGHTING_GL-10_1.pdf`, all pages (includes the former pilot p6–10 and p5 / LED/695) | approved |
| `batch_2` | `Estwing_Hammer_E-03_Interactive_1.pdf` + `Precision_Catalogue_CA_03.pdf`, all pages | approved |
| `batch_3_pilot` | `Hand_Tool_Catalogue_low_res_with_cover.pdf` pages 8, 11, 12, 53, 224 | prepared, **not approved** |

Supplementary sources (no product records by default; used later for images, features and descriptions; genuinely new products or specifications are flagged for review): `Workshop_mini-compress.pdf`, `Fluid_Handling_mini_min_2.pdf`.
Not yet scheduled: `Fluid_Handling_Catalogue_spread.pdf`, and the rest of the Hand Tool catalogue.

## Outputs

### `output_v2/`: corrected pipeline (current)

| File | Contents |
|---|---|
| `extracted_products.json` | Cumulative dataset (all batch files) |
| `batches/<batch>.json`, `batches/<batch>.manifest.json` | Per-batch records, pages processed, code commit |
| `images/` | Image crops, named `<pdf>_p<page>_xref<n>_<x>_<y>.png` |
| `review.html` | Review dashboard: filters by catalogue, image evidence, notes and changes. Serve the folder over HTTP to view it |
| `reports/summary.md` | Counts, image evidence, editorial notes, coverage checks against the PDFs |
| `reports/change_report.md` | Change report vs the legacy dataset. `.csv` has one row per changed field and opens in Excel |

### `output/`: legacy Antigravity outputs (read-only, kept for comparison)

- `extracted_products.json`: the 813 legacy records.
- `batch_*_products.json`, `batch_*_review.html`, `batch_*_summary.md`, `images/`, `previews/`: the legacy batch files, dashboards, summaries (with hard-coded numbers), crops and page previews.

## Record fields worth knowing

- `verification_status`: `unverified` or `needs_review` (missing CAT/ORD or low confidence). `verified` can only be set by a person.
- `specifications.variant_label`: the printed header above a CAT/ORD column pair in two-column tables (e.g. `GRADE B`, `WORKSHOP GRADE`, `KNIFE EDGES`).
- Weight and length keys follow the printed column header, and values are kept only when they carry a unit:
  - `head_weight` (HEAD WEIGHT), `weight` (WEIGHT)
  - `overall_length` (OVERALL LENGTH), `length` (LENGTH), `handle_length` (HANDLE LENGTH)
- `images[].association_type`, each with an `evidence` sentence:
  - `direct_product`: this product's code is printed beside the image.
  - `product_family`: a family or shared label, or the single image beside the only ordering table in its region.
  - `unresolved`: page position only. A review candidate; never show it as the product's image.
- `source_row_text`: the verbatim words of the product's own table row. `raw_text_snippet`: the start of the table text.

## Tools

- `tools/dump_page.py <pdf> <page>`: prints a page's words line by line with x positions (read-only). Use it to check a table layout before changing the parser.
