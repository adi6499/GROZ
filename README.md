# GROZ Product Catalogue — extraction pipeline

Extracts product records (CAT NR, ORD NR, dimensions, box quantity, specifications, images) from the
official GROZ catalogue PDFs, with full source traceability. The printed catalogue is the source of
truth: values are never silently corrected, and no record is ever marked `verified` automatically.

> Status (14 Oct 2026): handed over from Google Antigravity. See `PROJECT_HANDOFF_AUDIT.md` for the
> audit of the inherited data. Recovery work is in progress; this README will be updated with it.

## Setup (Windows)

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
```

- Tested with Python 3.13.14 on Windows 11 and Python 3.12.3 on Linux (original run).
- The `venv/` folder in this project is the original **Linux** environment. It does not work on
  Windows; use `.venv/` instead. Both are git-ignored.
- OCR (`rapidocr-onnxruntime`) is optional, needs Python <= 3.12, and is not used by the batch scripts.

## Run the tests

```bash
.venv/Scripts/python.exe -m pytest -q
```

Run every command from the project root. All paths in the code are relative to it.

## Source PDFs (project root)

| PDF | Pages | Status |
|---|---:|---|
| `tools_storage.pdf` | 35 | Batch 1 |
| `GROZ_LIGHTING_GL-10_1.pdf` | 48 | Pilot (p6–10) + Batch 1 (p11–48) |
| `Estwing_Hammer_E-03_Interactive_1.pdf` | 20 | Batch 2 |
| `Precision_Catalogue_CA_03.pdf` | 88 | Batch 2 |
| `Hand_Tool_Catalogue_low_res_with_cover.pdf` | 260 | Not processed |
| `Fluid_Handling_Catalogue_spread.pdf` | 372 | Not processed |
| `Workshop_mini-compress.pdf` | 68 | Supplementary brochure (no ORD numbers) |
| `Fluid_Handling_mini_min_2.pdf` | 64 | Supplementary brochure (no ORD numbers) |

## Legacy outputs in `output/` (do not overwrite)

| File | Contents |
|---|---|
| `extracted_products.json` | 813 records: pilot (11) + Batch 1 (138) + Batch 2 (664) |
| `batch_1_products.json`, `batch_2_products.json` | Per-batch records |
| `batch_1_review.html`, `batch_2_review.html` | Review dashboards (open in a browser) |
| `batch_*_summary.md` | Summaries (their metric tables are hard-coded text) |
| `images/` | Product image crops referenced by the JSON |
| `previews/` | Page previews |
| `test_*` folders, `review_report.*`, `data_quality_audit.md` | Development and pilot leftovers |

## Legacy scripts: hazards

The original runners write straight into `output/`:

- `run_prototype.py` overwrites `output/extracted_products.json` with only 11 records.
- `run_batch_1.py` overwrites it with 149 records, which **deletes all Batch 2 records**.
- `run_batch_2.py` rebuilds it from the Batch 1 records already in that file.

Do not run them until the recovery work replaces them with safe runners.
