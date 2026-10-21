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

Pipeline version: `2.3.1` (`backend/pipeline/runner.py`). Bump it whenever an extraction rule changes. The `output_v2` dataset was produced by rules version 2.3.1 (15 Oct 2026): decision G (product pictures, 2.3.0) and decision H (clean pictures, 2.3.1), both approved by the owner. Earlier, 2.2.0 applied decisions A–F. Every changed value is listed in `review/applied/` (one folder per applied rules version).

## Batches

| Batch | Scope | Status |
|---|---|---|
| `batch_1` | `tools_storage.pdf` + `GROZ_LIGHTING_GL-10_1.pdf`, all pages (includes the former pilot p6–10 and p5 / LED/695) | approved |
| `batch_2` | `Estwing_Hammer_E-03_Interactive_1.pdf` + `Precision_Catalogue_CA_03.pdf`, all pages | approved |
| `batch_3_pilot` | `Hand_Tool_Catalogue_low_res_with_cover.pdf` pages 8, 11, 12, 53, 224 → `output_pilot_handtool/` | approved and run 17 Oct 2026 (73 records); its proposed fixes await approval |
| `batch_3_fluid` | `Fluid_Handling_Catalogue_spread.pdf` (CC-07, all 372 pages) + `FUEL.pdf` (CAT 400, 32 pages) | approved 21 Oct 2026 ("extract all, preview"); its preview was approved for the website the same day ("approve the preview and make it live"); 2024 records in `output_v2` |

Supplementary sources (no product records by default; used later for images, features and descriptions; genuinely new products or specifications are flagged for review): `Workshop_mini-compress.pdf`, `Fluid_Handling_mini_min_2.pdf`. `groz-lubrication-equipments.pdf` prints no CAT or ORD numbers at all: it is shown in the flipbook only, never a source of product records.
Not yet scheduled: the rest of the Hand Tool catalogue.

### `batch_3_fluid`: Fluid Handling CC-07 and FUEL CAT 400 (rules 3.0.x)

- **Column reader** (`backend/extractor/grid_tables.py`, used only for these two PDFs; batches 1 and 2 keep their rules and re-extract with 0 changes). Each ordering table is read as printed:
  - one record per printed CAT NR.; best-seller / new marks and footnote stars are not part of a code;
  - the ORD NR. of the same row ("ORDERING #" in CAT 400; beside the code when a header omits the ORD column); in a table with ORD columns, a row without an order number is no product;
  - every value column, verbatim, as a specification named after its printed header, up to four header lines ("MAX. PRESSURE (PSI)"); "-" cells left out; check marks (Wingdings 2) as "✓";
  - BOX QTY., SIZE / DIMENSION (INCH) (MM) and DESCRIPTION into their own fields; labels under each CAT/ORD pair (BSP / NPT THREADS) as the variant, section rows across a table (ALUMINUM DIE CAST HEAD) as its section;
  - accessory tiles outside tables (a code with its ORD NR. printed under it);
  - a table that prints its units above the column names is not guessed: those rows keep code, order number and box quantity, with a review note.
- **Completeness:** CC-07's numerical index (pages 365–369) lists 1942 order numbers. Every one printed on a product page is read. 49 appear only in the index, on no product page; they cannot be extracted. About 30 products printed with an order number are missing from the index.
- **Titles:** CC-07 prints them in Mont-Heavy 16 (rules above / page / spread / facing). A last rule, `contents`, takes the family the catalogue's contents page lists for that printed page; CAT 400 prints no product titles, so its titles all come from its contents page. Where two families start on the same page, no title is given.
- **Pictures** (`grid_picture`): the product's own code beside a picture; else the most specific family tag its code begins with (picture "G1-HD" for G1R/HD/B); else, on a page with one ordering table and no labelled pictures, its largest picture. Otherwise the picture stays unconfirmed and is not shown. A picture labelled for other products is never used.
- **Categories** (site): CC-07 products take the section of the contents their printed page is in: Greasing Equipment, Oiling Equipment, Hose Reels, Waste Oil Handling, Drum Handling (all under Lubrication), Fuel & DEF Handling (Fuel & DEF), Air Handling (Air Tools). Grease guns whose printed title names a battery are Battery Grease Guns (Power Tools, owner's choice). CAT 400 products are Fuel & DEF Handling.
- **Duplicates:** 73 CAT 400 products are also printed in CC-07 (same ORD NR.). The site shows each once, from CC-07.
- **Preview, then live (21 Oct 2026):** the batch was first extracted into `output_preview_fluid/` and shown only locally (`build_site_data.py --preview`, `?data=preview`, with a yellow bar). The owner approved it the same day. The batch then moved into the main dataset: its `output_dir` setting was removed (commit e14eb51) and it was re-extracted into `output_v2`. The re-extraction is identical to the approved preview: the same 2024 records field for field, and byte-identical pictures. `site/data/catalogue.json` holds the same 2892 products as the approved preview. `.vercelignore` now deploys `FUEL.pdf` and `Fluid_Handling_Catalogue_spread.pdf` (82 MB), because products link to their pages. `output_preview_fluid/` (git-ignored) keeps the approved preview as it was.
- **Previews of future batches:** list the batch file and its image folder in `PREVIEW_DATASETS` (`backend/site/catalogue_export.py`), then run `build_site_data.py --preview`. With nothing listed, `--preview` says so and stops.

## Outputs

### `output_v2/`: corrected pipeline (current)

| File | Contents |
|---|---|
| `extracted_products.json` | Cumulative dataset (all batch files) |
| `batches/<batch>.json`, `batches/<batch>.manifest.json` | Per-batch records, pages processed, code commit |
| `images/` | Product pictures, named `<pdf>_p<page>_xref<n>_<x>_<y>.png`: each picture alone as printed, without page text, line art or other pictures, white margins trimmed (rules 2.3.1). Files no longer referenced by any record are kept, never deleted |
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
- From rules version 2.3.1 (decision H, clean pictures):
  - The saved picture is the picture alone, exactly as printed (position, rotation, transparency, clipping), without the page's text, line art or other pictures, and without white margins.
  - A picture that draws only an icon-sized detail on a mostly empty canvas (close-up insets, empty frames) is decoration, not a product picture.
  - A tool storage panel's code tag reaches its picture up to 120 pt below it.
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
    - A shown picture that fails to load (for example, the local server stopped) is retried once, then labelled "Picture didn't load". "Image unavailable" stays reserved for products that have no picture.
    - **Clear pictures** (`tools/build_display_images.py`, 21 Oct 2026): most catalogue pictures are printed small (often 250–450 px wide), and the 200 DPI extraction render had enlarged each real pixel into a block of about 3 × 3, so they looked torn. The site shows WebP copies instead: each picture is taken back to its real pixels and enlarged smoothly (Lanczos, light unsharp mask), with nothing invented. `site/img/full/` (at most 1200 px, product details, quote, flipbook) and `site/img/thumb/` (480 px, cards, lists): 663 pictures, about 18 MB instead of about 200 MB of PNGs. The dataset PNGs stay the extraction's evidence and are not deployed. Run the tool after an extraction adds pictures, then `build_site_data.py` (it uses a copy only where both sizes exist; a test fails if one is missing).
      - **AI upscaling** (owner's choice, 21 Oct 2026): `--ai <path to realesrgan-ncnn-vulkan.exe>` enlarges the pictures smaller than 800 px with Real-ESRGAN (model `realesr-animevideov3`, 2×/3×/4×) instead of Lanczos. They are much crisper, but the AI fills in fine detail, so small print or logos can differ slightly from the catalogue. Every such picture says so in the product details ("Enlarged for the screen with AI upscaling…; the catalogue page is the original"). `site/img/manifest.json` records how each copy was made (`ai`, `smooth` or `resized`).
      - The upscaler is not part of the project: it is the official Windows build from github.com/xinntao/Real-ESRGAN (release v0.2.5.0, `realesrgan-ncnn-vulkan-20220424-windows.zip`, 45,474,481 bytes, sha256 `abc02804…802d`), unpacked on this PC in `Downloads\realesrgan-ncnn-vulkan\app\`. `realesrgan-x4plus` is a little crisper but about 23 times slower on this laptop's Intel Iris Xe (115 s vs 5 s for 6 pictures).
  - **Verification:** cards and table rows show a badge only for products a person has checked ("Verified") or that need review; one note above the catalogue covers the rest. Every product's details show its status, including "Not yet verified". Nothing is marked verified by the site.
  - **Printed title:** the title the catalogue prints for the product's ordering table, in the catalogue's title type (Mont-Heavy 16 pt for GROZ, Futura-Bold 12 pt for Estwing). The rules are the same as for `sub_title` (shared module `backend/extractor/printed_titles.py`).
    - Since rules 2.2.0 the title and `sub_title` agree for all 941 products.
    - Product details name the rule and PDF page the title came from.
    - Any future difference is listed in `review/display_titles.csv`.
- **Font:** Ubuntu Sans on every device.
  - It is one variable font file (`site/assets/fonts/ubuntu-sans-latin-wght-normal.woff2`, 38 KB, from Fontsource `@fontsource-variable/ubuntu-sans` 5.3.0), served with the site and preloaded.
  - Licence: Ubuntu Font Licence 1.0, `site/assets/fonts/LICENSE-ubuntu-font.txt`.
  - Apple's San Francisco cannot be used: its licence does not allow serving it to other devices.
  - Characters outside the font's Latin set fall back to the system fonts.
- **Light and dark mode:**
  - The site follows the device's setting.
  - The sun/moon button in the header (on phones, "Dark mode" in the menu) switches it. That choice is kept in the browser only while it differs from the device setting.
  - A small script in the page head applies the theme before the first paint, so there is no flash.
  - Dark styles live in one block of `site.css` (`:root[data-theme=dark]`); light styles are unchanged.
  - Catalogue pictures keep soft light tiles in dark mode, because they are renders on white.
  - Switching shows a glass reveal (View Transitions API): the new theme grows from the button in a soft-edged circle while the old view frosts over. It is instant where unsupported, on low-end devices, and for visitors who ask for reduced motion.
- **Product details:** the picture is the hero, beside the code, title, status and up to four key facts.
  - Opening a product from a card plays a short 3D unboxing (about 0.8 s; the details are readable after about 0.6 s). The picture tile becomes a GROZ carton that tilts toward the viewer and opens its flaps. The product's own picture (or its category icon) rises out and flies to its place in the details, which grow from the box. The key specifications then fade up into their rows, one after another.
    - Made lighter on 21 Oct 2026 (owner's request): it was about 1.6 s, with two full-size picture copies moving in 3D and up to 8 cloned specification rows (with large shadows) flying in arcs. Now the picture copies show the card's own small picture, which is already decoded (nothing waits), and the specification rows fade up in place. Measured in Edge with the CPU 4× slower: dropped frames while opening 15–21 → 7–9, while closing 10–18 → 3–5. Hovering a card also fetches its large picture, so the details are sharp when they open.
    - It is one continuous sequence: the details are built and measured before the first frame, and every movement is a Web Animation on the same timeline (`unboxThenShow`/`playUnbox` in `app.mjs`; the carton's faces are `.unbox`/`.ub-*` in `site.css`). Only transform and opacity are animated, and never opacity on the carton itself, which would flatten its 3D faces.
    - The flying picture is a copy of the real one, landing exactly on it; the real one appears as its copy lands. The dialog's usual entrance is replaced, not replayed afterwards. Nothing in the data changes.
    - If the page stops drawing (a hidden tab), a timer still ends the sequence so the details show.
    - While any dialog is open, the space of the hidden page scrollbar is kept, so the page behind does not reflow.
    - It is skipped (the details open at once) for visitors who ask for reduced motion, on low-end devices, for cards that are off screen, in Table view, and when stepping between products inside the dialog.
    - The animations are created paused and start together once the picture copies are decoded (they show the card's picture, so this is at once; at most ~150 ms), so the first frames do not stall on image decoding.
  - Closing the details plays the unboxing backwards (`playBoxClose`; about 0.85 s):
    - the picture flies down to the box and sinks inside;
    - the details shrink toward the box and the page comes back;
    - the flaps close and the carton settles onto the product's card and fades into its picture.
    - It applies to product details whose card is on screen in Cards view, with the picture in view. Other dialogs, and every dialog with reduced motion, close with the plain fade.
    - Reopening during the close stops it and leaves the dialog as it was.
    - Opening and closing share one carton builder (`buildCarton`), so the box looks the same both ways.
  - Then Add to quote, Save and Compare, and a link to the catalogue page.
  - Below: all specifications in a two-column grid, and "From the catalogue" (source page, printed-title evidence, the table row as extracted).
  - Previous/Next and the position in the results sit in the dialog header.
- **Results bar:** the product count, Filters, sort and active filter chips stick under the header while scrolling, on every screen size.
- **GROZ categories** (`GROUPS` in `core.mjs`; presentation only, the data keeps its own `category`):
  - The site uses GROZ's own top-level categories, in the order of the main menu on groz-tools.com (India site, checked 17 Oct 2026): Lubrication, Fuel & DEF, Air Tools, Lighting, Hand Tools, Mechanic's Tools, Power Tools, New & Exciting.
  - The catalogue categories sit where GROZ's menu puts them:
    - LED Worklights under Lighting;
    - Striking Tools (hammers) under Hand Tools;
    - Tool Storage (rolling tool cabinets, tool boxes) under Mechanic's Tools.
  - GROZ's menu has no place for precision measuring tools: its site search finds no micrometers, calipers, scribers or verniers. So Precision Tools follows the eight as a category of its own (owner's choice, 17 Oct 2026).
  - They appear as category tiles, in a Categories menu in the header and in the phone menu, and as the Category filter. Chips and the details heading show them too, for example "Mechanic's Tools › Tool Storage". Searching a category name finds its products.
  - Since 21 Oct 2026, Lubrication, Fuel & DEF, Air Tools and Power Tools show the products of the Fluid Handling CC-07 and Fuel CAT 400 catalogues (`batch_3_fluid`). Only New & Exciting says "Coming soon": there is no catalogue for it. Its description lists what GROZ's menu shows under it. No products are made up for it.
    - The full Hand Tools catalogue is in the project but not extracted yet; Hand Tools shows the Estwing hammers.
    - The GROZ Lubrication Equipment catalogue (`groz-lubrication-equipments.pdf`) can be read in the flipbook, but its products are not on the site. A quick table scrape of it (`tools/extract_lubrication_products.py`, Oct 2026) was merged into the site data and then taken off again (21 Oct 2026). About 50 of its 170 records were table labels such as "Accuracy" and "Repeatability". Every picture was a whole page, and some values were made up (box quantity 1, one pressure line copied to every product on a page). Its products will come through `run_extraction.py` with the same checks as the others, previewed for approval first. `tools/merge_catalogue_data.py` refuses to run without `--force`.
  - A data category that no group lists is shown as a category of its own, so no product drops out of the navigation (tested).
- **Motion** (`site/assets/js/motion.mjs`, styles under "decorative motion" in `site.css`):
  - Add to quote: the product picture is tossed in an arc into the Quote button, which pops as its count rolls to the new number. This works from cards, table rows, the details and the saved list. The button's check mark draws itself.
  - Save: the heart squashes and springs back with a ring and sparks; the saved count rolls.
  - Cards and category tiles lean toward the mouse in 3D, with a soft glare and the picture drifting the other way (mouse only).
  - New results rise in one after another. Cards further down wait and rise as they are scrolled into view. While typing a search, results only fade, so they do not dance; rebuilds that only refresh buttons show at once.
  - The product count counts up or down to the new total. Screen readers get the plain sentence through a separate live region, not the counting.
  - Details Previous/Next (buttons or arrow keys): the old picture swings out one side of its tile while the new one swings in from the other. Save, Compare and Add to quote inside the details no longer replay its fade-in.
  - The rows of the saved list and the quote rise in when those dialogs open. Buttons press in slightly when clicked.
  - Hero: an orange spotlight follows the mouse, the hammer leans toward it and the rings drift the other way.
    - Clicking the hammer makes it wind up and strike, pivoting at its grip. Sparks fly from its face with a shockwave, and the hero gives a small knock.
    - It strikes once by itself the first time the page is opened in a visit (remembered in sessionStorage for that visit only).
  - Category icons come alive on hover or keyboard focus, each with its own action:
    - the lamp lights up; the sledge swings and taps; the drawers slide out; the measuring line draws itself;
    - the grease gun pumps and drips; the fuel nozzle squeezes and drips; the air wrench buzzes and puffs; the drill buzzes with its bit spinning; the star turns and twinkles.
    - The moving parts are classed `a-*` in `art.mjs` and animated in CSS.
  - Section headings, and the hero title, rise in word by word when first scrolled to. Each word is clipped by its own inline box, so the layout is the same as the plain heading (measured: no change in width or height).
  - Compare: once the compare bar is showing, a newly picked product's picture flies into it.
  - Prepare request: the request feeds out of a printer slot, then a green "Ready · not sent" stamp lands on it. It says so because nothing is sent.
  - A glowing orange bar along the top of the window shows how far down the page you are (`animations.mjs` adds it). Where the browser supports scroll-driven animations, CSS moves it, off the main thread; elsewhere GSAP scales it.
  - Hero numbers count up from zero. The hero search box types example searches into its placeholder: micrometer, LED/621, rolling tool cabinet, sledge, 55044, pin vice, caliper. Each was checked to find products. It runs only while the box is on screen, empty and not focused.
  - Confetti bursts from the "Ready · not sent" stamp.
  - Buttons show a soft ripple from where they are pressed. Primary buttons lean toward the mouse (magnetic). Ticked checkboxes pop.
  - Product details: hovering the picture shows a round magnifier (mouse only). It appears only when the picture file is at least 1.4× larger than shown, and zooms up to 3×.
  - A round "Back to top" button appears once the page is scrolled well down. Pressed, it lifts off as the page scrolls up. It moves up while the compare bar is showing.
  - Wave 6 (21 Oct 2026):
    - An orange underline glides between the header links, and a soft row glides between the Categories menu's items (`glider()`: transform and opacity only, eased per frame, mouse only). The menu's items rise in one after another as it opens.
    - While a search box is focused, a light beam runs around its edge: a rotating conic gradient behind an inner fill, clipped by the box, so the compositor draws it.
    - Primary buttons get a light sweep on hover. Section titles get an orange underline that draws itself once the title has risen in.
    - Moving between the catalogue page and the flipbook cross-fades: a cross-document view transition (`@view-transition`, type `page`, so the dark-mode reveal is not affected). It is skipped with reduced motion and on low-end devices.
  - Smoothness (any refresh rate, 60 to 144 Hz and above):
    - Everything that follows the mouse (card and tile tilt, the hero lean and spotlight, magnetic buttons) is driven on every display frame by `follower()` in `motion.mjs`. Its easing does not depend on the frame rate, and its CSS transitions are off while it moves. Transitions restarted on every pointer event lag or judder.
    - Tilting cards get their own compositor layer while they move.
    - The hero hammer sits in a `.tool-wrap` that leans and strikes as one compositor layer, pivoting at its grip (`.grip-point`, `hammerPivot`). The drawing, with its blurred shadow, is not redrawn while it swings. Sparks are timed by the strike animation itself.
    - The hero badge uses a plain tint instead of a backdrop blur. It sits over constantly moving embers and rings, so the blur would be recomputed on every frame.
    - The hero numbers start counting after the first render, not during it.
    - Smoothness can only be judged in a real browser window. Preview panels that are hidden or not focused draw few or no frames.
  - Exits:
    - Dialogs fade and settle back before they hide; on phones the bottom sheet slides down. Reopening one during its exit cancels the exit.
    - The phone menu slides in with its items cascading, and slides away when closed.
    - The phone filter sheet slides down when closed.
    - All use `leave()` in `motion.mjs`, which hides the element and drops the exit in the same task, so no frame shows it again.
  - When results change (sort, filters), cards that were on screen glide to their new places (FLIP); newcomers rise in.
  - Saving a product flies a small heart into the saved button; the saved count changes as it lands.
  - Soft embers drift up behind the hero hammer. They are CSS-animated and paused while the hero is off screen.
  - Messages (toasts) spring in with a timer bar that runs down. The theme button's sun or moon spins into place.
  - Rules:
    - Only transform and opacity move: on the element itself, through the separate `translate`/`scale` properties so its own transform is kept, or on short-lived copies in a fixed layer.
    - Each copy is removed when its animation ends, or by a timer if the page stops drawing.
    - Nothing waits for an effect. With reduced motion, on low-end devices, or without Web Animations support, every effect is skipped and the page behaves as before.
- **Intro, sound and GSAP effects** (`site/assets/js/animations.mjs`, with GSAP 3.12.5 and ScrollTrigger vendored in `site/assets/js/vendor/`, GreenSock standard license):
  - **Intro:** the GROZ logo assembles from tool parts, then the page appears. It plays once per visit, and only when motion is allowed and the device is not low-end. A small script in the page head decides this before the first paint (`html.intro`).
    - Skip, <kbd>Esc</kbd> and a 6-second timer end it. A CSS failsafe hides the overlay after 7 seconds even if no script runs, so the page is never left black.
    - The hero count-up, the hammer strike, the heading reveal and the icon drawing wait for it (`introDone`).
  - **Sound** (synthesized, no audio files): off until the visitor turns it on with the speaker button. The choice is remembered in this browser (`groz.sound`) and shared with the flipbook.
  - **Effects:**
    - Hero silhouettes and parallax on scroll.
    - A scroll cue whose arrow bobs (CSS, paused off screen).
    - Sparks when the mouse enters a card or table row.
    - Table rows rise in.
    - The Quote button bounces once per added product.
    - The quote opens as a drawer from the right (from below on phones).
    - A quote readiness bar.
    - The Categories menu and the label legend unfold.
    - The Hand Tools tile knocks and the Lighting tile glows when scrolled to.
    - Icons draw their outlines once.
  - **Rules learned (21 Oct 2026):**
    - GSAP must not animate a property that has a CSS transition on the same element. The transition re-times every GSAP frame, which caused the lag in cards, buttons and the drawer. Cards use the Web Animations cascade (`motion.mjs`); rows and the cart bounce use Web Animations.
    - No GSAP tween may stay on a section. A leftover transform on `#products` turned the fixed phone filter sheet into one positioned inside it.
    - `main` uses `overflow-x: clip`, not `hidden`: `hidden` made it a scroll container, and the results bar stopped sticking on phones.
    - There is no backdrop blur over anything that moves, nor on the sticky header or dialog heads: re-blurring the page scrolling under them every frame made scrolling stutter on laptops (removed 21 Oct 2026).
    - The quote drawer slides with the Web Animations API (compositor), not GSAP: the GSAP tween ran on the main thread and stuttered while the drawer's contents were being built.
    - `html` reserves the scrollbar's space (`scrollbar-gutter: stable`), so locking the page for a dialog does not lay the whole page out again (the old padding-right compensation did).
    - In the light theme, form controls stay light (`color-scheme: light`) even when Windows is in dark mode; the quantity boxes in the quote showed dark before.
    - Dropdowns and accordions animate transform and opacity only, not height.
- **Flipbook** (`site/flipbook.html`, `site/assets/js/flipbook.mjs`, `site/assets/flipbook.css`): seven catalogues as a book with 3D page turns (GSAP), opened from the Catalogues section and from every product ("Open in 3D Flipbook").
  - **Pages:** WebP copies of the PDF page renders, plus 96 px thumbnails for the filmstrip, made by `tools/build_flipbook_webp.py`. That is 21 MB instead of 100 MB of PNGs for the first five. The PNGs stay in the project and are not deployed.
    - Fluid Handling CC-07 (372 pages) and Fuel CAT 400 (32 pages) were added on 21 Oct 2026, when their products went live. Their pages are rendered straight from the PDFs (no PNGs). A product opens at its own page there instead of downloading the whole 82 MB PDF.
    - Pages next to the open spread are fetched and decoded ahead.
    - A turn starts once its pages are decoded (300 ms at most), so the turning page is never blank.
    - The page under the lifting leaf is already the next one. The last page has a spread of its own (25 spreads for 48 pages).
  - **Turns:**
    - A jump, a catalogue switch or a resize during a turn stops it cleanly (`stopTurn`).
    - The leaf has no CSS filter: it flattened the 3D faces and repainted a blurred shadow every frame.
    - With reduced motion, pages change at once.
  - **Phones:** one page at a time, swiped like a card, with the next page waiting underneath at the same size.
  - **Products on a page:** the data records which page a product is printed on, not where on the page. So each page with products shows one "N products on this page" button instead of pins at made-up spots. Hovering it lists them; clicking it opens the specifications drawer.
    - The drawer shows the same values as the catalogue page: status ("Not yet verified"), picture evidence and a link to the PDF page.
    - **Add to quote** adds to the real quote kept in this browser (`groz.quote`), which the catalogue page shows.
  - **Other features:**
    - Zoom is exactly 2×. The pointer's position chooses which part of the enlarged page is in view, edge to edge.
    - **Magnifying glass** (toolbar button or <kbd>M</kbd>): a round lens follows the pointer and enlarges the spot under it, 2.5× to start. Scroll, or press <kbd>+</kbd> and <kbd>−</kbd>, to change it (1.5× to 5×); <kbd>Esc</kbd> or Done turns it off.
      - On a touch screen, hold a finger on the page: the lens floats above it, and the page does not swipe while the lens is on.
      - Inside the lens the page is a sharper render: the PDF page at 200 DPI (`hires/`, 40 MB for all five catalogues, made by `tools/build_flipbook_webp.py`). It is fetched only for a page someone looks at; until it arrives, the lens shows the page already on screen.
      - The lens and the 2× zoom take turns. The lens is moved once per display frame, and its position is a `translate`, so it grows in place when it appears.
    - Keyboard: <kbd>←</kbd> <kbd>→</kbd>, <kbd>Space</kbd>, <kbd>Z</kbd> zoom, <kbd>Esc</kbd>. The page counter is a button that opens "go to page".
    - Page changes are read out to screen readers.
    - The drawer is `inert` while closed, and focus moves into it and back.
    - The stage clips instead of scrolling, so nothing can push the book out of view.
  - Its sounds (page rustle, ambience) are off until turned on; the ambience stops fully when turned off.
- Files:
  - `site/index.html`, `site/assets/site.css`
  - `site/assets/js/core.mjs`: pure logic, tested by Node.
  - `site/assets/js/app.mjs`: page behaviour. `site/assets/js/motion.mjs`: decorative motion only. `site/assets/js/animations.mjs`: intro, sound and the GSAP effects.
  - `site/assets/js/art.mjs`: category icons from the reference design. `site/assets/js/icons.mjs`: interface icons (inline SVG).
- Responsive and touch:
  - Tested at 320, 375, 430, 768, 1024 and 1440 px with no horizontal page scrolling.
  - Touch screens get 44 px targets and 16 px form text (no zoom on focus).
  - On phones, filters and dialogs open as bottom sheets that respect the safe areas, and quote lines stack, with − / + quantity buttons.
- Motion and performance:
  - Only `transform` and `opacity` are animated: with CSS or Web Animations, and with GSAP in `animations.mjs` and the flipbook. Displays at 60 to 144 Hz run them at their own rate.
  - The hero's looping motion pauses off screen. Hover effects apply only where a pointer can hover.
  - `prefers-reduced-motion` turns motion off.
  - A *lite* mode (data saver, ≤ 2 GB memory or ≤ 2 CPU cores, or a measured median frame time over 34 ms) turns off decorative motion and blur, keeping every function.
  - Cards render 36 at a time and "Show more" appends instead of rebuilding. Further cards also load by themselves as the end of the list comes near (an IntersectionObserver on the button), so a long category needs no click after click.
  - Filter panel: a category's specification filters come in order of how many of its products print them; the first 8 are shown and the rest wait behind "Show N more specifications" (Lubrication prints over a hundred). Choosing a category updates the category tiles in place. A click on a filter takes about 35 ms (it was about 300 ms with all of Lubrication's filters).
  - A whole category group chosen (Lubrication's five sections) shows as one chip, and the Filters badge counts chips.
  - Images are lazy-loaded in fixed-size boxes; layout shift on load measured 0.
- Saved products, the quote list and the grid/table choice are kept in the browser (`localStorage`). Contact details typed into the quote form are not stored.
- **Quotations are prepared locally only.** Nothing is emailed or sent anywhere: there is no backend.
  - The quote drawer shows three steps (products, your details, prepare), each product as a card with its picture, quantity buttons and a remove button (the card slides away and the others close the gap), and a footer with the totals and "Prepare request" that stays in view.
  - The prepared request is a formatted document (`core.quoteHtml`): GROZ letterhead, your reference (`QR-yyyymmdd-hhmm`, the time it was prepared) and the local time, requested by / delivery / summary, a product table with pictures, catalogue and printed page, total units, notes, and a "Not sent" footer. It is shown as a white sheet in both themes.
  - **Copy for email** copies it as formatted text (the table survives being pasted into an email; pictures are left out, as an email cannot load them from this site), with plain text for other apps. **Print or save as PDF** prints the document alone on A4 once its pictures have loaded. Excel (.csv) and Text (.txt) downloads are named after the reference.
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

## Deployment (Vercel)

Every push to `main` on GitHub deploys the site as **static files**: `vercel.json` sets `"framework": null` ("Other": no build, no server), redirects `/` to `/site/` and keeps search engines out (`X-Robots-Tag: noindex`). `.vercelignore` leaves out everything the site does not load (extraction code, datasets, PNG renders, `requirements*.txt`). A Vercel project created on 21 Oct 2026 took `requirements.txt` for a Python app and failed with `PYTHON_ENTRYPOINT_NOT_FOUND`; the Python here is offline tooling only. `site/tests/deploy.test.mjs` checks all of this.

## Tools

- `tools/dump_page.py <pdf> <page>`: prints a page's words line by line with x positions (read-only). Use it to check a table layout before changing the parser.
- `tools/build_flipbook_webp.py`: makes the flipbook's WebP pages and thumbnails from the page PNGs, and the magnifier's 200 DPI pages from the PDFs; catalogues in `PDF_ONLY` (Fluid Handling, Fuel) are rendered straight from their PDFs (only new or changed pages; `--force` rebuilds all; needs `.venv` for PyMuPDF).
- `tools/build_display_images.py`: the clear WebP copies of every picture the site shows (`site/img/`; only new or changed pictures; `--force` rebuilds all; needs `.venv`).
- `tools/sync_catalogue_pipeline.py`: renders missing flipbook page PNGs (pdftoppm), builds their WebP copies, writes `site/data/catalogue.csv` from `catalogue.json` and runs the website tests. It never adds products (`--csv` only exports the CSV).
- `tools/extract_lubrication_products.py` and `tools/merge_catalogue_data.py`: the Oct 2026 lubrication scrape, kept for reference only (see Website › GROZ categories).
