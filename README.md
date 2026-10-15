# GROZ Product Catalogue — extraction pipeline

Extracts product records (CAT NR, ORD NR, dimensions, box quantity, specifications, images) from the
official GROZ catalogue PDFs, with full source traceability. The printed catalogue is the source of
truth: values are never silently corrected, suspected catalogue errors go into `editorial_notes`, and
no record is ever marked `verified` automatically.

- `PROJECT_HANDOFF_AUDIT.md`: audit of the project as received from Google Antigravity.
- `RECOVERY_REPORT.md`: the defect fixes, re-extraction results and open review items (14 Oct 2026).
- `site/`: the local catalogue website built on `output_v2` (see [Website](#website-local-only)).

**Public code repository** (https://github.com/adi6499/GROZ): it holds the code, tests, website and review notes only. These are kept out of it because they are GROZ's catalogue material or data extracted from it:

- the catalogue PDFs;
- `output/` and `output_v2/`;
- `site/data/catalogue.json`.

To recreate them, put the PDFs in the project root, run the extraction batches, then run `build_site_data.py`. Tests that read the PDFs or the datasets need those files.

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
| `tests/test_site_data.py` | Website data export: every record exported once with its own values, nothing invented, unresolved images never shown, pending corrections withheld, display titles printed on their cited page (with page-checked examples), `site/data/catalogue.json` and `review/display_titles.csv` not stale |

Website logic (search, filters, sorting, titles, image labels, previous/next, comparison, quotation) has its own tests, run with Node.js 18 or later:

```bash
node --test "site/tests/*.test.mjs" "verify/tests/*.test.mjs"
```

## Extraction commands

```bash
.venv/Scripts/python.exe run_extraction.py list
.venv/Scripts/python.exe run_extraction.py status
.venv/Scripts/python.exe run_extraction.py batch batch_1
.venv/Scripts/python.exe run_extraction.py preview batch_1
.venv/Scripts/python.exe run_extraction.py compare
.venv/Scripts/python.exe run_extraction.py pilot-report batch_3_pilot
.venv/Scripts/python.exe run_extraction.py recovery
```

- `list` shows the batches, their approval status and output folders.
- `status` runs every safety check for every batch without reading any page (shows READY or BLOCKED and why).
- `batch NAME` extracts one batch into its own folder and rebuilds that folder's reports. Main batches also rebuild `output_v2/extracted_products.json`. `run_batch_1.py` and `run_batch_2.py` do the same for their batch.
- `preview NAME` re-extracts an approved main batch into a temporary folder and writes `review/preview_NAME.md/.csv` listing every difference from `output_v2`. Nothing in `output_v2` changes.
- `compare` writes the change report against the legacy 813-record dataset, including the editorial decision log and the index discrepancy list.
- `pilot-report NAME` rebuilds a dedicated-folder batch's report from its existing files.
- `recovery` runs batch_1 and batch_2, then the cumulative build, the comparison and the reports.

Options: `--out DIR` (main dataset folder, default `output_v2`), `--allow-shrink`. There is deliberately no option that bypasses the approval gate.

### Safe execution rules (enforced by the code, all checked before any page is read)

1. Nothing ever writes into the legacy `output/` folder; the runner refuses it.
2. Each batch writes only to its own folder:
   - batch_1 and batch_2 write to `output_v2/batches/`;
   - `batch_3_pilot` writes only to `output_pilot_handtool/`;
   - no batch may write into another batch's folder;
   - the pilot is never merged into `output_v2`.
3. Unapproved batches refuse to run. To approve one, set `approved=True` for it in `backend/pipeline/batches.py`, in its own commit, after written approval.
4. Batch 3 catalogues (`Hand_Tool_…`, `Fluid_Handling_Catalogue_spread.pdf`) only allow the pages listed in `RESTRICTED_SOURCES`: the five pilot pages, and no Fluid pages.
5. Supplementary brochures (`Workshop_mini-compress.pdf`, `Fluid_Handling_mini_min_2.pdf`) can never create product records.
6. Extraction commands refuse to run while the extraction code has uncommitted changes. Every manifest records the pipeline version, git commit, source-PDF SHA-256, pages processed and approval state.
7. The cumulative file is rebuilt from the batch files. It refuses to drop or shrink a batch, or to take one page from two batches. A batch re-run that would produce fewer records is refused. `--allow-shrink` overrides both, only for an intended reduction.
8. A replaced batch file is first copied to `batches/history/`; nothing is discarded.
9. Every report number is computed from the data when the report is generated.

Safe order: `batch batch_1` and `batch batch_2` (any order, independently) → `compare` → review.

Pipeline version: `2.3.0` (`backend/pipeline/runner.py`). Bump it whenever an extraction rule changes. The `output_v2` dataset was produced by rules version 2.3.0 (commits `2033b7e`, `57d279a` and `135592b`, 15 Oct 2026), after the owner approved decision G (product pictures). The previous version, 2.2.0, applied decisions A–F. Every changed value is listed in `review/applied/2026-10-14_rules-2.2.0/` and `review/applied/2026-10-15_rules-2.3.0/`.

## Batches

| Batch | Scope | Status |
|---|---|---|
| `batch_1` | `tools_storage.pdf` + `GROZ_LIGHTING_GL-10_1.pdf`, all pages (includes the former pilot p6–10 and p5 / LED/695) | approved |
| `batch_2` | `Estwing_Hammer_E-03_Interactive_1.pdf` + `Precision_Catalogue_CA_03.pdf`, all pages | approved |
| `batch_3_pilot` | `Hand_Tool_Catalogue_low_res_with_cover.pdf` pages 8, 11, 12, 53, 224 → `output_pilot_handtool/` | prepared, **not approved, not run** |

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
| `reports/change_report.md` | Change report vs the legacy dataset. `.csv` has one row per changed field and opens in Excel. Also renders the editorial decision log and the index discrepancy list |
| `reports/index_discrepancies.csv` | Catalogue index vs printed pages (source issues, not extraction defects) |

### `output_pilot_handtool/`: Hand Tool pilot (created only when the pilot is approved and run)

| File | Contents |
|---|---|
| `batches/batch_3_pilot.json`, `.manifest.json` | Pilot records and provenance |
| `reports/batch_3_pilot_report.md`, `_records.csv` | Records, missing values, ambiguous matches, unresolved images, gates, counterparts in output_v2/legacy (compared, never merged), changes since the previous run |
| `review.html` | Review dashboard for the pilot |

### `review/`: review documents

- `editorial_decisions.json`: decision log (evidence, current data, proposed treatment, status).
- `preview_<batch>.md/.csv`: effect of not-yet-applied extraction-rule changes on a batch, written by `preview`. There are none at the moment; the website withholds any value such a file lists as changed.
- `applied/<date>_rules-<version>/`: what an approved rules change did. Each folder holds a before/after list of every changed field, the previews and the old headings.
- `display_titles.csv`: products whose printed title differs from `sub_title`. It is empty since rules 2.2.0.

### `output/`: legacy Antigravity outputs (read-only, kept for comparison)

- `extracted_products.json`: the 813 legacy records.
- `batch_*_products.json`, `batch_*_review.html`, `batch_*_summary.md`, `images/`, `previews/`: the legacy batch files, dashboards, summaries (with hard-coded numbers), crops and page previews.

## Record fields worth knowing

- `verification_status`: `unverified` or `needs_review` (missing CAT/ORD or low confidence). `verified` can only be set by a person.
- `sub_title` (from rules 2.2.0, decision F): the title printed for the product's own ordering table, in the catalogue's title type (`backend/extractor/printed_titles.py`):
  1. the nearest title above the table, in the same column or half spread;
  2. else the only title on the page or spread;
  3. else the facing page's only title.
- `specifications.variant_label`: the printed header above a CAT/ORD column pair in two-column tables (e.g. `GRADE B`, `WORKSHOP GRADE`, `KNIFE EDGES`), or above a knurl matrix column set (e.g. `COARSE LEFT`).
- `specifications.table_caption`: the orange caption printed at the top of the product's table, verbatim, when it is more than "ORDERING INFORMATION" (e.g. `TAPER SHANK ARBORS - DIN 238`).
- `specifications.table_description`: the description printed in the product's own table row (e.g. `Tool Box with Trolley`). It is kept only when its words are printed in that row.
- `specifications.diameter`: LED/800 only; the diagram's diameter callout, verbatim (decision A).
- Weight and length keys follow the printed column header, and values are kept only when they carry a unit:
  - `head_weight` (HEAD WEIGHT), `weight` (WEIGHT)
  - `overall_length` (OVERALL LENGTH), `length` (LENGTH), `handle_length` (HANDLE LENGTH)
- `images[].association_type`, each with an `evidence` sentence:
  - `direct_product`: this product's code is printed beside the image.
  - `product_family`: one of:
    - a label shared with other codes, or the base model's label;
    - the picture captioned with the product's table caption;
    - the only (or clearly largest) picture printed above the product's table under its printed title, or on the facing page;
    - the picture of the one variant pictured in the same table;
    - the largest picture in the region of the only ordering table there, when it is labelled for no other product.
  - `unresolved`: page position only. A review candidate; never show it as the product's image.
- From rules version 2.3.0 (decision G, `backend/extractor/image_extractor.py` and `image_sections.py`):
  - A printed code labels only its nearest picture. Codes in ordering-table cells never count, and labels never cross a spread's fold.
  - Codes on white tags: a page-header tab labels no picture; a panel's code tag (tool storage) labels the picture printed under it.
  - Codes match as whole codes ("MS/7" is not "MS/7/AL").
  - Where picture boxes overlap, the code belongs to the picture actually drawn next to it (its visible pixels).
  - Thin upright tool pictures (tweezers, scribers) are kept as product pictures.
  - A picture labelled for another product is never borrowed by layout.
- `source_row_text`: the verbatim words of the product's own table row. `raw_text_snippet`: the start of the table text.
- From rules version 2.1.0 (decision E, applied to `output_v2` with 2.2.0):
  - `drawer_load_capacity`, `overall_load_capacity`, `net_weight` are read from the product's own capacity block. Each printed label is paired with the value printed directly above it. A block belongs to the panel headed by the product's CAT NR, otherwise to its own table area. Ambiguous values stay empty.
  - `beam_angle` comes only from the lighting spec-icon strip, verbatim (e.g. `60˚`). Titles and callouts such as "270° Swivelling" never count.

## Website (local only)

A static catalogue website on top of `output_v2`, following the Apple-style reference design (`groz_catalogue_apple_v2.html`). It is meant for local development only: do not deploy or publish it. The catalogue PDFs and images belong to GROZ.

```bash
.venv/Scripts/python.exe build_site_data.py
.venv/Scripts/python.exe serve_site.py
```

Then open http://127.0.0.1:8962/site/. The server listens on this computer only (`--port N` changes the port). Opening `site/index.html` directly from disk does not work, because browsers block loading the data file from `file://` pages.

- `build_site_data.py` reads `output_v2/extracted_products.json` (never writes to it) and the catalogue PDFs, and writes `site/data/catalogue.json` and `review/display_titles.csv`. Re-run it whenever the dataset or the `review/preview_*.csv` files change; a test fails if either output is stale.
- What the site shows (`backend/site/catalogue_export.py`):
  - **Values** are the record's own values; an empty field shows "Not specified".
  - **Fields listed as changed in a pending correction preview** (`review/preview_*.csv`) show "Under review" instead of the current value, until the correction is applied to `output_v2`.
  - **Images:** only `direct_product` and `product_family` images are shown, each with its evidence. Family images are tagged "Family image". `unresolved` candidates are labelled "Image not confirmed" and never shown; products without any image say "Image unavailable".
  - **Verification:** cards and table rows show a badge only for products a person has checked ("Verified") or that need review; one note above the catalogue covers the rest. Every product's details show its status, including "Not yet verified". Nothing is marked verified by the site.
  - **Printed title:** the title the catalogue prints for the product's ordering table, in the catalogue's title type (Mont-Heavy 16 pt for GROZ, Futura-Bold 12 pt for Estwing). The rules are the same as for `sub_title` (shared module `backend/extractor/printed_titles.py`).
    - Since rules 2.2.0 the title and `sub_title` agree for all 941 products.
    - Product details name the rule and PDF page the title came from.
    - Any future difference is listed in `review/display_titles.csv`.
- Files:
  - `site/index.html`, `site/assets/site.css`
  - `site/assets/js/core.mjs`: pure logic, tested by Node.
  - `site/assets/js/app.mjs`: page behaviour.
  - `site/assets/js/art.mjs`: category icons from the reference design. `site/assets/js/icons.mjs`: interface icons (inline SVG).
- Responsive and touch:
  - Tested at 320, 375, 430, 768, 1024 and 1440 px with no horizontal page scrolling.
  - Touch screens get 44 px targets and 16 px form text (no zoom on focus).
  - On phones, filters and dialogs open as bottom sheets that respect the safe areas, and quote lines stack, with − / + quantity buttons.
- Motion and performance:
  - Only `transform` and `opacity` are animated, with CSS (no JavaScript animation loops, so displays at 60–144 Hz run them at their own rate).
  - The hero's looping motion pauses off screen. Hover effects apply only where a pointer can hover.
  - `prefers-reduced-motion` turns motion off.
  - A *lite* mode (data saver, ≤ 2 GB memory or ≤ 2 CPU cores, or a measured median frame time over 34 ms) turns off decorative motion and blur, keeping every function.
  - Cards render 36 at a time and "Show more" appends instead of rebuilding.
  - Images are lazy-loaded in fixed-size boxes; layout shift on load measured 0.
- Saved products, the quote list and the grid/table choice are kept in the browser (`localStorage`). Contact details typed into the quote form are not stored.
- **Quotations are prepared locally only.** They can be copied, downloaded (.txt / .csv) or printed. Nothing is emailed or sent anywhere: there is no backend.
- The untracked `index.html` in the project root is a separate "Local Portal" page for the review dashboards; the website does not use it.

## Verification tool (people check products against the catalogue)

```bash
.venv/Scripts/python.exe verify_server.py
```

Then open http://127.0.0.1:8963/verify/. The tool runs on this computer only and is not part of the website deployment.

- **Screen:** each product's extracted values sit beside its catalogue page, rendered from the PDF in one of three views:
  - **Row** (default): the table's column headings with the product's own printed row, CAT NR and ORD NR outlined.
  - **Table**: the whole ordering table.
  - **Whole page**: the full page, with the table outlined.
- **Decisions:** the reviewer marks the product **Verified** (every value matches the page, including "not extracted" values) or **flags a problem**. A flag needs the fields concerned and a comment.
  - Every decision records the reviewer's name and the time.
  - Keys: <kbd>V</kbd> verified, <kbd>F</kbd> flag, <kbd>J</kbd>/<kbd>K</kbd> next/previous, <kbd>T</kbd> switch view.
- **Records:**
  - `review/verifications.json` holds the current decision per product.
  - `review/verifications_log.jsonl` keeps every action, including undo, and is never rewritten.
  - `output_v2` is not modified.
- **Fingerprint:** each decision carries a fingerprint of the values checked: CAT NR, ORD NR, title, sizes, box quantity, specifications and the image shown. If a later extraction changes any of them, the decision is "changed since checked" and the product returns to the to-check list.
- **Catalogue site:** "Update catalogue site" in the tool (or `build_site_data.py`) applies the decisions.
  - A product shows **Verified**, with who and when, only while its values still match.
  - A flagged product shows **Needs review**, with the reviewer's comment as a review note.
- **Testing:** `verify_server.py --ledger <file> --log <file>` uses a separate test ledger. Such a server can never update the catalogue site.
- **Code:**
  - `backend/review/verification.py` (ledger rules), `verify_server.py` (local server).
  - `verify/` (page). Tests: `tests/test_verification.py` and `verify/tests/`.

## Tools

- `tools/dump_page.py <pdf> <page>`: prints a page's words line by line with x positions (read-only). Use it to check a table layout before changing the parser.
