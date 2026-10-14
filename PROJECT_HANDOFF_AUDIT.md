# GROZ Product Catalogue — Project Handoff Audit (Phase 1)

**Date:** 14 Oct 2026 · **Auditor:** Claude Code · **Scope:** read-only audit of the Antigravity project delivered as `Downloads\GROZ.zip`

**Project location:** `C:\Users\Analyst Profile\Downloads\GROZ`. Extracted from `GROZ.zip`, which is left untouched in Downloads.

**Nothing in the project was modified.** All 1,231 project files (excluding `venv/`) were fingerprinted (SHA-256) before the audit and re-checked afterwards: 0 added, 0 removed, 0 changed. This file is the only addition. Tests and re-extraction runs were done on a **separate scratch copy**, because the tests and batch scripts write into `output/`.

> A separate, earlier pipeline (`Desktop\GROZ\platform`, built by Claude on 13 Oct) also exists. It was **not** used or touched here.

---

## 1. What already works

| Area | Result (verified on disk) |
|---|---|
| Schema (pydantic) | Enforces lineage fields. Blocks `verified` status at construction. Bounding boxes are validated. |
| Verification status | 810 `unverified`, 3 `needs_review`, **0 `verified`**. Matches the handoff claim. |
| ORD integrity | **Every extracted ORD is printed on its recorded page.** No invented order numbers in 813 records. |
| CAT NR integrity | 793 / 813 CAT NRs match a printed word exactly. The 20 failures are covered in §4.2. |
| Image provenance | All 192 referenced crops exist on disk. **Each re-renders pixel-identically from its recorded PDF, page and bounding box.** No cross-page or cross-PDF links. |
| Image rendering | Byte-identical on Windows / Python 3.13 vs the original Linux run, so crops are reproducible. |
| Dataset reconciliation | `extracted_products.json` is exactly pilot (11) + `batch_1_products.json` (138) + `batch_2_products.json` (664), in that order. Every record is verbatim identical. |
| Review dashboards | `batch_1_review.html`: 149 cards match the JSON card-by-card (CAT, ORD, image, box qty), and the flagged (7) and needs-review (2) counts match. `batch_2_review.html`: 813 cards match the JSON in order. All image paths resolve. |
| Editorial claims | 7 claims re-checked against the PDF text, all accurate: 62900 is printed twice (CH-38W = 62901); LED/616 and EPAX-336F tables have no ORD column; LED/670, LED/670T and LED/685T values are as printed; the LED/800 table has no size column. |
| Batch 2 reproducibility | Re-running `run_batch_2.py` regenerates all 664 records identically (apart from path separators on Windows, see §5). |

## 2. Actual test results

```
35 passed in 26.07s   (pytest 9.1.1, Python 3.13.14, Windows 11; run on a scratch copy)
```
Same package versions as the original Linux venv: pymupdf 1.28.2, pydantic 2.14.1, pillow 12.3.0, pdfplumber 0.11.10. The test count matches the inherited `.pytest_cache` (35 node IDs, 0 last-failed).

**What the tests do not prove.** Six tests assert counts read back from the saved JSON (813, 664, 50 …). They confirm the files agree with themselves, not with the PDFs. The editorial-note tests check text that is hard-coded per product in `product_builder.py` (lines 114–204). No test covers two-column tables, single-letter CAT prefixes, box-qty alignment, bare-fraction dimensions or index cross-checks. That is why the defects in §4 pass.

## 3. Dataset counts verified from disk

| Catalogue | Records | Pages processed / with records | Notes |
|---|---:|---|---|
| `tools_storage.pdf` | 82 | 35 / – | |
| `GROZ_LIGHTING_GL-10_1.pdf` | 67 | p6–48 | 11 pilot (p6–10) + 56 (p11–48). **p1–5 never processed** |
| `Estwing_Hammer_E-03_Interactive_1.pdf` | 131 | 20 / 13 | |
| `Precision_Catalogue_CA_03.pdf` | 533 | 88 / 68 | |
| **Total** | **813** | | All `extraction_method = native_pdf`. OCR was never used. |

- **ORDs:** 810 records carry one, 809 unique. The only duplicate is **62900** (Estwing p11, EMLTT/CH-25W and CH-45W). Missing: **LED/616/US, LED/616/EU, EPAX-336F**. No ORD is shared between catalogues.
- **Images:** 763 / 813 have exactly one image; 50 have none (Precision p23:2, p44:2, p45:12, p49:7, p61:27). Association types: **182 `direct_hero`, 581 `product_family`.**
- **Editorial notes:** 9, all `pending_review`: 7 from Batch 1 + 2 from Batch 2. Seven have `suggested_correction = None`. The two LED/800 notes carry a suggestion taken from the page's diameter callout, and their dimension fields are filled from that callout.
- **Inherited claims:** 813 / 149 / 664, 35 tests, 62900, the three missing ORDs and the 50 image-less records are all **confirmed**. The claim "every product is associated with a verified candidate image" (Batch 2 summary) is **not accurate**: 50 have none, and "verified" overstates page-level matches.

## 4. Known data-quality issues

### 4.1 Missing products (coverage gaps): ~128 printed items not in the dataset
- **Precision, two-column tables:** pages 8, 17, 56, 57 and 62 print paired `CAT | ORD | CAT | ORD` tables (Grade A/B, A/Workshop grade). Only the left-hand variant was extracted, so **127 printed ORDs are missing**: p8: 9, p17: 6, p56: 48, p57: 50, p62: 14.
  - Corroboration: the catalogue's own **numerical index (p82–83)** lists 634 ORDs. 109 of them are not in the dataset; 106 of those are printed on the pages above.
  - 3 index ORDs (01217, 35044, 35045) appear nowhere in the body.
  - 8 extracted ORDs (01227, 12201–12207) are absent from the index. That is a catalogue editorial question, not an extraction error.
- **Lighting LED/695 (ORD 55117)** on physical p5 has a full ordering table but was skipped: the pilot started at p6 and Batch 1 at p11.

### 4.2 Wrong published values (must be fixed in the pipeline, not by hand)
| Issue | Evidence | Cause |
|---|---|---|
| **20 truncated CAT NRs** | Precision p61: printed `G/10/M1` … `G/24/M5` (ORD 07700–07719) stored as `10/M1` … `24/M5` | `CAT_PATTERN` needs ≥2 characters before the first `/` |
| **Box quantities misassigned** | Precision p10: ID/8 printed **90** → stored 200; ID/10 **60** → 200; ID/12 **60** → 100; OD/4 **200** → 100. p33: EF/* printed **400** → stored 1–10. p57: `TB/*` box qty = the LENGTH column (that table has no box column). | Box qty is accepted only from a fixed whitelist (1, 2, 4 … 200), so 60/90/400 are dropped and the column shifts. The fallback grabs unrelated numbers. An automated row check could confirm only 404 of 813 values. **Treat `box_qty` as unreliable until reviewed.** |
| **Bare fractions truncated in dimensions** | COB/0-1 printed `1/16 × 5/16 × 3-1/2` → `16 × 5/16 × 3-1/2`; COB/0-2 `3/32 × 1/ 2 × 4` → `32 × 1/` (mm field `2 × 4`) | The dimension regex can't start on a bare fraction. 20 records start with a bare 4/8/16/32/64 and need review. |
| **Specs attached to the wrong products** | `beam_angle` on 117 non-lighting records (e.g. "90°" on tool cabinets and squares); `overall_length` on 43 Precision records ("2"", "0.20""); `head_weight` "150 \n G" on RNG/4; `top_options` "Stainless Steel" on LED/360 and two Precision items | Spec regexes run over the whole page or half-page, not the product's own table row |

### 4.3 Image associations need visual review before customer use
- 581 of 763 links are `product_family`. On single-page catalogues, any large image on the page is attached to **every** product on that page; one crop is shared by 48 records (Precision p56 and p68). These are page-level matches, not product-level.
- `image_id` is not unique across PDFs: `img_508_16` and `img_512_16` are used by both Estwing and tools_storage. Crop filenames have no PDF prefix. No overwrite has happened yet, but Batch 3 could collide.

### 4.4 Customer-facing text is not ready
`product_name` is the model code for 810 / 813 records. `sub_title` is often a cut-off sentence (e.g. "Drill Chuck Arbors Drill Chuck Arbors are used to mount a drill"). `description` comes from a fixed page rectangle.

### 4.5 Reports are partly hard-coded
The metric tables in `batch_1_summary.md` and `batch_2_summary.md`, and the Batch 2 HTML banner ("663 … 1"), are **literal text in the scripts, not computed**. They match today's data, but they would not change if the data did. The dashboards do not HTML-escape values.

## 5. Reproducibility, environment and missing pieces
- **Batch 1 cannot be reproduced.** Re-running `run_batch_1.py` with today's code changes **140 of 149** Batch 1 records: description 117, sub_title 89, box_qty 16, confidence 14, specs 5, features 2, image confidence 2.
  - The extractor files were edited (01:27–02:05) after Batch 1 was generated (00:50), and there is no version control, so the code that produced Batch 1 is lost.
  - Today's code would **add 16 printed box quantities** that the saved data lacks (checked: LED/370 = 15, LED/390 = 50, LED/131 = 100, LED/505 = 20).
  - It would also **add 5 wrong specs** (e.g. `head_weight "1 G"` on RTC/42-20/2B/GRZ, `overall_length 27"` on cabinets).
- **Overwrite hazards:**
  - `run_batch_1.py` rewrites `extracted_products.json` with 149 records, **dropping all 664 Batch 2 records**.
  - `run_prototype.py` rewrites it with 11.
  - The tests write crops into the real `output/images/`.
  - Scripts depend on the current directory being the project root (relative paths only).
- **Platform bug:** image `file_path` is built with `os.path.relpath`, so a Windows run writes `images\…` (backslashes) into the JSON and HTML.
- **venv is unusable here:** it is a Linux venv (Python 3.12.3, `/home/adesh/Documents/GROZ/venv`) and must be recreated. `requirements.txt` uses `>=` ranges with no lockfile.
- **Declared but unused:** `pdfplumber`; `rapidocr` (OCR runs only in `run_prototype.py`, and the batch runners hard-code `native_pdf`).
- **Missing:** README / docs, git history, a pinned lockfile.
- **Clutter in `output/`:** 462 unreferenced crops in `images/`, plus scratch folders `test_crops` (2), `test_images` (27), `test_b2_crops` (305) and `test_b2_images` (21). `review_report.*` and `data_quality_audit.md` are pilot-era (11 records) and superseded.
- **Editorial notes don't generalise:** they are hard-coded per product, so new catalogues will get none unless detection is built.
- **Unsupported guess:** the 62900 note suggests "likely intended as 62902". 62902 appears nowhere in the Estwing catalogue, so that guess has no evidence and should be removed or marked as conjecture.

## 6. Remaining catalogues: layout profile (read-only)

| PDF | Pages | Ordering-table pages | 5-digit ORDs (unique) | Two-column pages | Image-only pages | Index | Notes |
|---|---:|---:|---:|---:|---:|---|---|
| `Hand_Tool_Catalogue_low_res_with_cover.pdf` | 260 | 192 | ~1,880 | 23 | 14 (section dividers) | p254 (likely to p257) | Same CAT / ORD / BOX table family as Precision and Estwing. 49 ORDs already in the dataset (calipers, p224) |
| `Fluid_Handling_Catalogue_spread.pdf` | 372 | 287 | ~1,978 | 68 | 1 (cover) | p365 | Despite the name, pages are single portrait. Up to 298 images per page, so high image-association risk |
| `Workshop_mini-compress.pdf` | 68 | 0 | 1 | 0 | 1 | – | Brochure layout, no ORDs. 159 / 243 codes also in Hand Tool |
| `Fluid_Handling_mini_min_2.pdf` | 64 | 0 | 3 | 0 | 1 | – | Brochure layout, no ORDs. 236 / 335 codes also in Fluid "spread" |

## 7. Recommended next steps (each needs your approval)
1. **Put the project under git** and commit this exact state as the baseline, ignoring `venv/`. Everything after that becomes reversible. Recreate a Windows venv with pinned versions.
2. **Fix the pipeline defects in §4–5 with a regression test for each**, in small steps:
   - single-letter CAT prefix;
   - two-column table parsing;
   - box qty taken from the header-aligned column with no whitelist, left empty when there is no BOX QTY column;
   - bare-fraction dimensions;
   - specs scoped to the product's own table / catalogue family;
   - PDF-prefixed crop names and image IDs, forward-slash paths;
   - computed (not typed) report metrics;
   - make the runners write versioned outputs instead of overwriting the cumulative file.
3. **Add automatic coverage gates** (the checks used in this audit):
   - every printed ORD on a product page is extracted or explicitly excluded with a reason;
   - every CAT NR equals a printed word;
   - every extracted ORD is printed on its page;
   - an index cross-check wherever the catalogue has a numerical index.
4. **Re-extract Batches 1–2 into new versioned files** (not overwriting the current ones). Produce a field-by-field diff of every changed published value for your review, plus LED/695 and the ~127 missing Precision variants. Nothing is auto-verified.
5. **Then Batch 3 pilot (proposed):** Hand Tool catalogue, 5 pages:
   - **p12:** standard table; head weight in separate lb/kg columns.
   - **p11 and p53:** two-column tables.
   - **p224:** calipers already extracted from Precision, to test keeping cross-catalogue duplicates as separate records.
   - **p8:** image-only divider; must produce 0 records without error.
   - The index (p254+) serves as the completeness checklist for those pages.
   - Fluid Handling "spread" follows, after an image-association review approach is agreed.
6. **Decision needed from you:** whether the two "mini" brochures should become product records (they have no ORDs and mostly duplicate the full catalogues) or serve only as a secondary source of images and features.

*Stopped at Phase 1. No extraction code was changed and Batch 3 has not been started.*
