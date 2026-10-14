# GROZ recovery: fixes, re-extraction and change report

**Date:** 14 Oct 2026 · **Scope approved:** protect the project, fix the audited defects, re-extract Batches 1–2 into new files, compare, and prepare (not run) the Hand Tool pilot.

**Stopped here.** Batch 3 has not been run, and no website has been built or deployed.

## Outcome in one paragraph

The corrected pipeline re-extracted Batches 1–2 into `output_v2/`: **941 records, up from 813**.
- **All 813 legacy records are matched**; none are missing.
- **128 records were added:** 127 right-hand variants from two-column Precision tables, plus LED/695.
- **The legacy `output/` folder is byte-identical** to the received baseline.
- **Coverage checks against the PDFs:** every printed ORD on every processed product page is now extracted. Every extracted ORD and every CAT NR is printed on its recorded page.
- **Remaining findings:** only 3 order numbers that appear in the Precision index but nowhere in its body.
- **Tests:** 71 pass.

## Phase 1: protection

| Item | Result |
|---|---|
| Backup | `Downloads\GROZ_BACKUP_2026-10-14_pre-recovery.zip` (550 MB, 7,112 files, including the Linux venv). Every file was verified byte-for-byte against the project. The original `Downloads\GROZ.zip` is also kept. |
| Git | `012245d` is the untouched baseline (every received file except `venv/` and caches), committed with no line-ending conversion. Later commits each hold one step. |
| README | Setup, dependencies, commands, outputs and safe execution order |
| Legacy data | `output/` (all 1,210 files) is unchanged since `012245d`. Tests no longer write into it. |

## Phase 2: defects fixed (each with regression tests)

| # | Defect (audit) | Cause | Fix | Evidence |
|---|---|---|---|---|
| 1 | Right-hand items of two-column tables lost (Precision p8, 17, 56, 57, 62) | Two CAT headers on one line were treated as separate tables | Header lines are split into CAT/ORD column groups, each pair becomes a record, and the printed group header is kept as `variant_label` (GRADE B, WORKSHOP GRADE, KNIFE EDGES) | Printed ORDs = extracted ORDs on all 5 pages (18, 12, 96, 100, 28) |
| 2 | `G/10/M1` … stored as `10/M1` (20 records) | CAT pattern needed ≥2 characters before `/` | Single-letter prefix accepted | All 941 CAT NRs are printed words on their page |
| 3 | Box quantities shifted or invented | Value whitelist (1, 2, 4 … 200) plus "last number in the row" fallback | Read under the table's own BOX QTY header in the product's row; empty when the table has no BOX QTY column | p10 ID/8 = 90, ID/10 = 60; p33 EF = 400; p45 VB/C/5 = 6; p57 TB = none (no column) |
| 4 | Dimensions starting with a fraction cut short | Dimension pattern couldn't start on `1/16` | Fraction-aware pattern; a dimension is only read where the table has a SIZE/INCH/MM column | COB/0-1 `1/16 × 5/16 × 3-1/2` / `1.52 × 7.93 × 88.9`; LED/131 battery `4×1.5LR44` no longer a size |
| 5 | Specs leaking between products | Page-wide regexes; row text included feature text beside the table | Row values only from the product's own row and columns; lighting specs only for lighting products; page specs only where a region has one table and one consistent value; power source verbatim, never derived from plug type | See §3.4 |
| 6 | LED/695 missing | Lighting p1–5 never processed | Batches now process every page | LED/695, ORD 55117, box 10, dims as printed (p5) |
| 7 | Image links over-claimed | Largest image on the page called "hero" | `direct_product` / `product_family` / `unresolved`, each with an `evidence` sentence; codes match only as whole codes; PDF-prefixed crop names and IDs; forward slashes | Unresolved candidates are excluded from confidence |

### Defects found during recovery (each also fixed and tested)

- **Precision p39:** captions EST/2/ST and EST/1/ST became records with no ORD. A caption merged into the header line hid the ORD column. Header lines are now never rows.
- **No-ORD gate:** a new coverage check flags any record without an ORD unless an editorial note explains it.
- **Tool storage drawer counts (17 records):** these came from the separate drawer-details tables (rows A/B/C). Drawers are now read only from a NO. OF DRAWERS column.
- **Estwing columns relabelled:** values under WEIGHT, LENGTH and HANDLE LENGTH had been stored as `head_weight`/`overall_length`. They are now keyed by the printed header (`weight`, `length`, `handle_length`). The mallets' `overall_length` had been taken from the FACE DIA. column.
- **Set descriptions:** a description running across columns (Precision p5) is no longer read as a length.
- **Batch 2 rerun:** it then produced 2 fewer records (the p39 captions). The runner **refused** to overwrite until rerun with `--allow-shrink`, which is the safety rule working as designed.

### Tests: 71 passing

`.venv/Scripts/python.exe -m pytest -q` passes all 71 tests in ~40 s.

| Group | Count |
|---|---:|
| Original tests (test_schema.py, test_extraction.py) | 35 |
| Regression tests for confirmed defects (test_recovery_regressions.py) | 27 |
| Pipeline safety tests (test_pipeline_safety.py) | 9 |

Four original expectations changed, each commented in the test:
1. Image IDs now come from crop filenames; `direct_hero` became `direct_product`.
2. Tool storage p4: RTC/27-10D/1/GRZ now gets the image labelled with its own code, instead of the larger family photo.
3. LED/336 is now `product_family`: no code is printed beside its image.
4. LED/621 is now `product_family` for the same reason.

The images chosen for 3 and 4 are unchanged.

## Phase 3: comparison with the legacy dataset

Full detail: `output_v2/reports/change_report.md`. The CSV has one row per changed field (1,160 rows) and opens in Excel. The dashboard is `output_v2/review.html`, filterable by "Changed vs legacy".

### 3.1 Records

| Catalogue | Legacy | New | Change |
|---|---:|---:|---|
| tools_storage.pdf | 82 | 82 | 0 |
| GROZ_LIGHTING_GL-10_1.pdf | 67 | 68 | +1 LED/695 |
| Estwing_Hammer_E-03_Interactive_1.pdf | 131 | 131 | 0 |
| Precision_Catalogue_CA_03.pdf | 533 | 660 | +127 two-column variants (p8 +9, p17 +6, p56 +48, p57 +50, p62 +14) |
| **Total** | **813** | **941** | **+128 added, 0 missing** |

### 3.2 Identifiers and status

- **CAT NR:** 20 changed, all `G/` arbors on Precision p61.
- **ORD NR:** 0 changed. 3 records still have none (LED/616 US/EU, EPAX-336F), each explained by an editorial note. ORD 62900 is still printed twice.
- **Verification status:** 0 changed. 938 unverified, 3 needs_review, **0 verified**.
- **Editorial notes:** 0 changed (9 notes).
- **Printed page labels:** 0 changed.

### 3.3 Box quantity (266 changes)

| Change | Records | Why |
|---|---:|---|
| Empty → printed value | 35 | 20 lighting (e.g. LED/370 = 15) + 15 Precision values outside the old whitelist |
| Value → corrected value | 105 | Whitelist shift (e.g. p40 MS/4 4 → 500; p67 KT/6-2 50 → 30; lighting LED/250 3 → 40) |
| Value → empty | 126 | **Precision (101):** 98 on p56/p57, whose tables have no BOX QTY column (old values were lengths); 3 single cells printed "–" or blank. **Estwing (25):** its tables have no BOX QTY column (old values invented). |

All 562 box quantities now present appear in the product's own table row.

### 3.4 Specifications

| Key | Change | Records | Reason |
|---|---|---:|---|
| beam_angle | removed | 117 | Non-lighting products ("90°" on squares and cabinets) |
| overall_length | removed | 59 | 43 Precision mislabels; 16 Estwing relabelled (below) |
| length / handle_length | added | 14 / 2 | Estwing LENGTH / HANDLE LENGTH columns (ETM's old "8"" was the base size) |
| head_weight → weight | 4 removed / 4 added | 4 | WEIGHT column, not HEAD WEIGHT |
| head_weight | removed | 1 | RNG/4 had junk `150 \n G` |
| overall_length | changed | 3 | Mallets: taken from OVERALL LENGTH, not FACE DIA. |
| head_weight | changed | 1 | EPAX-336F: full printed `3.5 lb./1.58 kg` |
| no_of_drawers | removed | 17 | Came from drawer-details tables, not the product's table |
| net_weight / overall_load_capacity / drawer_load_capacity | removed | 4 / 4 / 2 | Tool storage p25–26: two one-product tables per half page, each with its own capacity graphic. The legacy copied the first product's values to both (see open items). |
| ip_rating | removed | 3 | MMED micrometers: page prints IP54 and IP65 for different variants |
| power_source | removed / changed | 4 / 2 | LED/602 and LED/612 have no POWER SOURCE column (value was derived); LED/616 now verbatim `110V AC, 60 Hz` |
| top_options | removed | 3 | Taken from feature text (e.g. LED/360 "stainless steel hooks") |
| variant_label | added | 121 (+121 on new records) | Printed column-group header |

### 3.5 Dimensions (24 inch, 9 mm)

- **Fixed:** 15 values regained their leading fraction (COB ×7, KT ×6, VB/QD ×2), plus LED/336 (`29/32 × …`).
- **mm filled in or corrected:** 9 values, for the COB and KT rows.
- **Removed:** 8 non-dimensions: EYL magnifier "2x 600" (magnification + box qty) ×7, and the LED/131 battery.

Every new dimension value is printed verbatim on its page, except LED/800 EU/US (see open items).

### 3.6 Images (first image of each matched record)

| Legacy | New | Records |
|---|---|---:|
| product_family | product_family, same crop | 415 |
| product_family | **unresolved**, same crop | 150 |
| direct_hero | product_family, same crop | 143 |
| direct_hero | direct_product, same crop | 24 |
| direct_hero / product_family | direct_product, **different, code-labelled crop** | 25 |
| direct_hero / product_family | unresolved (3 same crop, 2 different) | 5 |
| product_family | product_family, different crop | 1 |
| none | none | 50 |

New totals: 49 direct product images, 631 product-family images, 211 unresolved candidates, 50 records with no candidate.
Every referenced crop exists. Its filename now identifies its PDF and page.

## Open review items (need a person)

1. **Precision index vs body:**
   - 3 indexed ORDs (01217, 35044, 35045) are printed nowhere in the body.
   - 29 printed products are absent from the index: 01227, the COB/0-x and COB/H/0-x tool bits (12201–12207, 12221–12227) and the DSW workshop-grade items (08520–08533).
   - These are catalogue editorial questions, not extraction errors.
2. **LED/800 EU/US dimensions.** They are filled from the page's diameter callout, with "(Dia.)" added, and an editorial note. Should they stay in the dimension fields, or live only in the note?
3. **62900 note.** It says "likely intended as 62902", but 62902 appears nowhere in the Estwing catalogue. Should that wording be removed?
4. **Tool storage p25–26 capacities.** Each product's capacity graphic sits beside its own one-row table. Reading specs per table (rather than per page region) would restore these; this is not done yet.
5. **`beam_angle`.** It takes the first "°" value on a lighting page. LED/621's 270° is printed as "270° Rotation", so the value is unchanged from legacy but questionable.
6. **211 unresolved image candidates and 631 family images** need visual review before any customer use.
7. **Not yet captured:**
   - single-value size columns, e.g. Precision "SIZE (L) 3 / 75"; only "×" dimensions are read;
   - `product_name` (still the model code);
   - clean customer-facing descriptions.

## Phase 4: next pilot (prepared, not run)

- **Batch `batch_3_pilot`:** `Hand_Tool_Catalogue_low_res_with_cover.pdf` pages 8, 11, 12, 53, 224.
  - **p8:** image-only divider; should produce 0 records.
  - **p11 and p53:** two-column tables.
  - **p12:** standard table, with weight and length in lb/kg and inch/mm columns.
  - **p224:** calipers already extracted from Precision. They will be kept as separate Hand Tool records, and the shared ORDs will show as "printed more than once".
- **Refused until approved.** To run after approval: set `approved=True` for `batch_3_pilot` in `backend/pipeline/batches.py`, commit, then run `python run_extraction.py batch batch_3_pilot`. The Hand Tool index (p254 onwards) should be added to `INDEX_PAGES` for the pilot's completeness check.
- **Mini catalogues** (Workshop, Fluid Handling mini) are registered as supplementary sources. The runner refuses to create product records from them. Using them for images, features and descriptions, and flagging new products, is a later step.

## Commits

| Commit | Step |
|---|---|
| `012245d` | Baseline (untouched handoff) |
| `9abfc34` | Phase 1 audit |
| `0a9b098` | README + pinned requirements |
| `2b6c120` | Defect fixes + regression tests |
| `d5a9c8a` | Safe pipeline, computed reports, change report |
| `4cf3417` | Parsing refinements found during review (this dataset was produced by this commit) |
