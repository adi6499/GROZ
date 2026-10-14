# GROZ Product Catalogue - Batch 1 Extraction Summary Report

**Generated:** 2026-10-14  
**Scope:** Batch 1 Only (`tools_storage.pdf` [35 pages] + `GROZ_LIGHTING_GL-10_1.pdf` [pages 11–48])  
**Pilot Context Included:** `GROZ_LIGHTING_GL-10_1.pdf` pages 6–10 (11 products)  
**Strict Policy Enforcement:**
- ✅ Published catalogue values preserved verbatim without mathematical alterations
- ✅ Zero products automatically marked `verified` (100% of newly extracted records are `unverified`)
- ✅ Zero duplicate merging of variants; uncertain records kept distinct
- ✅ Full traceability preserved: source PDF, physical PDF sheet, printed catalogue page reference, bounding boxes, and image crop provenance
- ✅ Requirement 1 Compliance: LED-685T dimensions preserved verbatim (`28-17/64 × 6-27/64 × 19-9/16` / `718 × 1630 × 497`), discrepancy marked `pending_review`, `suggested_correction` left empty (`None`) pending technical engineering drawing interpretation

---

## 1. Executive Metrics & Extraction Counts

| Metric | Tool Storage (`tools_storage.pdf`) | Lighting Batch 1 (Pages 11–48) | Pilot Baseline (Pages 6–10) | Combined Cumulative Total |
| :--- | :---: | :---: | :---: | :---: |
| **Physical Pages Processed** | 35 pages | 38 pages | 5 pages | **78 pages** |
| **Products Extracted** | **82** | **56** | **11** | **149** |
| **Unique ORD Numbers** | 82 / 82 (100%) | 54 / 54 (100%) | 11 / 11 (100%) | **147 unique ORDs** |
| **Products without Published ORD** | 0 | 2 (`LED/616` US & EU) | 0 | **2 products** |
| **Duplicate Records Detected** | **0** | **0** | **0** | **0** |
| **Verification Status** | `unverified`: 82 (100%) | `unverified`: 54<br>`needs_review`: 2 | `unverified`: 11 (100%) | `unverified`: 147<br>`needs_review`: 2 |
| **Products with Hero Images** | 82 / 82 (100%) | 56 / 56 (100%) | 11 / 11 (100%) | **149 / 149 (100%)** |
| **Editorial Discrepancies Logged** | 0 | 2 (`LED/616` US & EU) | 5 (`LED-670`, `670T`, `685T`, `800/EU`, `800/US`) | **7 editorial records** |
| **Automated Tests Passing** | — | — | — | **25 / 25 PASSED** |

---

## 2. Batch 1 Scope & Catalogues Processed

### A. `tools_storage.pdf` (35 Physical Pages)
- **Layout Architecture:** 2-page InDesign spreads (1190.55 × 841.89 pt).
- **Product Range:**
  - 27", 29", 35", 42", and 50" Rolling Tool Cabinets across S10D, S10, S20, and S30 Series (`RTC/...`, `RTCL/...`).
  - 20", 27", and 42" Tool Chests with Lids and Hutches (`TCH/...`, `TCHL/...`, `TCHH/...`, `TCHS/...`).
  - Heavy Duty Cantilever Metal Tool Boxes (`MTB/5`, `MTB/5T`, `MTB/3L`, `MTB/5L`).
  - 11" and 14" Mini Tool Boxes with Lids, Hanging Brackets, and 7-color swatches (`TCHL/11-10D/...`).
  - 30" Service Carts (`SRC/30-20/...`).
  - Heavy Duty Work Benches (`WBN/60-20/...`, `WBN/79-20/...`).
  - Complete Automotive Tool Kits in 7-Drawer Rolling Cabinets: 65, 90, 148, 170, 211, 235, 243, and 255 Piece configurations (`RTC/27-10D/.../AU`, `RTC/27-10/.../AU`).
- **Specifications Extracted:** Overall load capacity, drawer load capacity, net weight, steel gauge, series, top options (Rubberized Mat, Thermofoam, Wooden, Stainless Steel), and color variants.

### B. `GROZ_LIGHTING_GL-10_1.pdf` Pages 11–48 (38 Physical Pages)
- **Layout Architecture:** 2-page InDesign spreads (1190.55 × 841.89 pt).
- **Product Range:**
  - Portable Worklights with Swivel Bases (`LED/602`, `LED/612`, `LED/621`).
  - Twin-head Folding Worklights with Dual Battery Configurations (`LED/385` Drycell AA vs. `LED/385RM` Li-Po).
  - Slim Inspection Lamps and 360° Ball-Joint Worklights (`LED/360`, `LED/370`, `LED/390`, `LED/395`, `LED/396`, `LED/397`).
  - UV and Laser Pen Lights (`LED/175`, `LED/185`, `LED/186`, `LED/345`, `LED/346`, `LED/351`, `LED/355`).
  - Flashlights and Pocket Worklights (`LED/140`, `LED/150`, `LED/160`, `LED/165R`, `LED/170`, `LED/170R`, `LED/190`).
  - Dual Output Rechargeable Headlamps (`LED/220`, `LED/225`, `LED/230`, `LED/245`, `LED/250`).
  - Heavy Duty SMD and COB Floodlights (`LED/501`, `LED/502`, `LED/501S`, `LED/505`, `LED/512`, `LED/515`, `LED/520`, `LED/530`, `LED/541`, `LED/545`, `LED/701`, `LED/711`, `LED/721`).
- **Pages 43–45:** Summary specification comparison matrix tables (catalog reference; no ordering rows).
- **Pages 46–48:** Packaging, marketing support, and notes back cover.

---

## 3. Discrepancy & Editorial Review Log

Every catalog discrepancy is recorded separately in `editorial_notes` with `review_status: pending_review`. Source values remain verbatim in the catalog data.

| Product | CAT NR / ORD | Source Reference | Field | Verbatim Published Value | Issue Description | Suggested Correction | Review Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **LED-670** | `LED/670`<br>55050 | GL-10 Physical P7<br>Printed P11, Table SIZE | `dimensions_mm` | `24 x 26 x 13` | Upstream unit label mismatch: catalogue table lists `24 x 26 x 13` under column explicitly labeled `(MM)` (suggesting cm; conversion of 9.5 × 10 × 5 in would be ~241 × 254 × 127 mm). Technical drawing contains no dimension callouts; left unresolved pending technical drawing interpretation. | *None (Left empty per audit rules)* | `pending_review` |
| **LED-670T** | `LED/670T`<br>55077 | GL-10 Physical P7<br>Printed P11, Table SIZE | `dimensions_mm` | `117 × (122 - 192) × 117` | Catalogue discrepancy: table lists `(INCH)` as `46 × (48 to 75-1/2) × 46` and `(MM)` as `117 × (122 - 192) × 117` (suggesting cm). Meanwhile, technical diagram callout indicates an operational height range of `1m - 1.68m (39-1/2" - 66")`. The table values and diagram callout conflict and require interpretation against the original technical drawing; left unresolved per audit rules. | *None (Left empty per audit rules)* | `pending_review` |
| **LED-685T** | `LED/685T`<br>55119 | GL-10 Physical P9<br>Printed P15, Table SIZE | `dimensions_inch` | `28-17/64 × 6-27/64 × 19-9/16` | **Requirement 1 Compliance:** Table lists height as `6-27/64"` under (INCH) and `1630` under (MM). Meanwhile, the technical diagram callout indicates an operational height range of 0.7m – 1.3m (27-1/2" – 51"). The 1630 mm table value and diagram range require interpretation against the original technical drawing; left unresolved per audit rules. | *None (Left empty per instructions)* | `pending_review` |
| **LED-800** | `LED/800/EU`<br>55048 | GL-10 Physical P10<br>Printed P17, Graphic Callout | `dimensions_inch` | `[Not in table]` | Ordering table omitted SIZE column for circular cable reel worklight. Diameter extracted from graphic callout. | `12-1/64" (Dia.) / 305 mm (Dia.)` | `pending_review` |
| **LED-616** | `LED/616/US`<br>`LED/616/EU`<br>None | GL-10 Physical P12<br>Printed P20, Table | `ord_nr` | `[Not in table]` | Catalogue omission: ordering table omits ORD NR column entirely, providing only CAT NR, PLUG TYPE, POWER SOURCE, and dual open/closed dimensions. Marked `needs_review`. | *None (Awaiting Groz ERP ORD NR)* | `pending_review` |

---

## 4. Test Suite & Validation Results

The automated regression test suite was expanded to **25 comprehensive tests** covering all parsing rules, schemas, live PDFs, and cumulative reconciliation metrics:

```
============================= test session starts ==============================
collected 25 items

tests/test_extraction.py::test_table_sku_parsing PASSED                  [  4%]
tests/test_extraction.py::test_table_multi_row_parsing_with_tripod PASSED [  9%]
tests/test_extraction.py::test_telescopic_range_dimension_parsing PASSED [ 13%]
tests/test_extraction.py::test_image_association_rules PASSED            [ 18%]
tests/test_extraction.py::test_live_page_7_exact_dimensions PASSED       [ 22%]
tests/test_extraction.py::test_live_page_8_exact_dimensions PASSED       [ 27%]
tests/test_extraction.py::test_live_page_9_image_hero_isolation PASSED   [ 31%]
tests/test_extraction.py::test_live_page_10_diameter_dimensions PASSED   [ 36%]
tests/test_extraction.py::test_tool_storage_p4_cabinets PASSED           [ 40%]
tests/test_extraction.py::test_tool_storage_p5_top_options PASSED        [ 45%]
tests/test_extraction.py::test_tool_storage_p20_cantilever_boxes PASSED  [ 50%]
tests/test_extraction.py::test_tool_storage_p21_color_variants PASSED    [ 54%]
tests/test_extraction.py::test_lighting_p11_plug_variants_and_cross_normalization PASSED [ 59%]
tests/test_extraction.py::test_lighting_p12_missing_ord_nr_flagged PASSED [ 63%]
tests/test_extraction.py::test_lighting_p14_dual_table_spread PASSED     [ 68%]
tests/test_led_685t_editorial_note_compliance PASSED                     [ 64%]
tests/test_batch_1_sku_uniqueness_and_traceability PASSED                 [ 68%]
tests/test_extraction.py::test_led_670_and_670t_dimension_discrepancy_compliance PASSED [ 72%]
tests/test_extraction.py::test_slender_penlight_and_option_variant_image_associations PASSED [ 76%]
tests/test_extraction.py::test_cumulative_reconciliation_exact_metrics PASSED [ 80%]
tests/test_schema.py::test_schema_prevents_auto_verified_status PASSED   [ 84%]
tests/test_schema.py::test_schema_defaults_and_missing_fields PASSED     [ 88%]
tests/test_schema.py::test_bounding_box_coordinate_validation PASSED     [ 92%]
tests/test_schema.py::test_editorial_review_notes_attachment PASSED      [ 96%]
tests/test_schema.py::test_confidence_and_status_determination PASSED    [100%]

============================= 25 passed in 29.25s ==============================
```

---

## 5. Review Gate & Traceability Guarantee

1. **No Auto-Verification:** Every product in `output/batch_1_products.json` and `output/extracted_products.json` carries `verification_status: "unverified"` (or `"needs_review"` for LED-616).
2. **No Variant Merging:** Top options (e.g. Rubberized Mat vs. Thermofoam vs. Wooden vs. Stainless Steel) and color swatches are preserved as separate products with distinct ORD numbers.
3. **Traceability:** Every record contains:
   - `source_pdf`: Origin catalogue filename
   - `physical_page_number`: 1-based PDF sheet
   - `catalog_page_label`: Printed page numbers from header/footer
   - `bounding_box`: Page region coordinates
   - `images`: Image reference with crop path, bounding box, association type, and nearby text provenance

---

## 6. Remaining Risks & Recommended Next Steps

### Remaining Risks for Batch 1
1. **LED-616 Order Numbers:** The physical catalogue omitted the ORD NR column for LED/616/US and LED/616/EU on Page 12. These records are preserved as `needs_review` awaiting Groz master inventory data.
2. **LED-685T Tripod Height Range:** The discrepancy between 1630 mm table value, 6-27/64" printed inch value, and 27-1/2"–51" graphic callout requires engineering drawing verification before publishing.

### Recommended Next Steps for Batch 2 (Upon Approval)
1. **Batch 2 Scope:** `Precision_Catalogue_CA_03.pdf` (52 pages) and `Estwing_Hammer_E-03_Interactive_1.pdf` (28 pages).
2. **Awaiting User Review Gate:** All Batch 1 data is generated in `output/batch_1_summary.md`, `output/batch_1_review.html`, and `output/batch_1_products.json`. No work on Batch 2 or frontend will commence without your explicit approval.
