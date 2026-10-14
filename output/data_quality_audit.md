# GROZ Product Catalogue — Data-Quality Audit Report

**Audit Target**: Prototype extraction across physical pages 6 to 10 of `GROZ_LIGHTING_GL-10_1.pdf`  
**Date of Audit**: October 2026  
**Auditor**: Antigravity AI Data Quality Pipeline  
**Verification Baseline**: Original digital vector PDF catalogue (`GROZ_LIGHTING_GL-10_1.pdf`)

---

## 1. Executive Summary

A comprehensive data-quality audit was performed on the prototype extraction output covering **11 product records** across physical pages 6 to 10. The audit verified:
1. Every inch and metric dimension against printed table cells.
2. Every product hero image crop and spatial bounding box against page artwork.
3. Every CAT NR, ORD NR, Box Quantity, and technical specification against printed callouts.
4. Upstream publication anomalies in the source PDF (e.g. centimeter values printed under a column labeled `(MM)`).

All identified discrepancies were resolved in code, verified against the source PDF, and locked with **12 automated pytest regression tests** (`100% pass rate`).

---

## 2. Itemized Discrepancy Matrix

| # | Item / Product | Physical Page | Initial Extracted Value | Confirmed Source Value | Root Cause | Code Change Made | Regression Test Added | Status |
|---|---|---|---|---|---|---|---|---|
| **D-01** | **LED-670T** Dimensions | Page 7 | `— / —` (Missing) | `46 × (48 to 75-1/2) × 46` (inch)<br>`117 × (122 - 192) × 117` (metric) | Telescopic height range contained parenthesized text `(48 to 75-1/2)` not matched by initial regex | Updated `dim_pattern` in `TableExtractor` to capture parenthesized telescopic ranges | `test_live_page_7_exact_dimensions`<br>`test_table_multi_row_parsing_with_tripod` | **Resolved** |
| **D-02** | **LED-680T** Dimensions | Page 8 | `— / —` (Missing) | `11-3/16 × (27-1/2 to 67) × 5-1/8` (inch)<br>`288 × (699 to 1702) × 131` (metric) | Telescopic height range `(27-1/2 to 67)` failed dimension pattern match | Updated `dim_pattern` in `TableExtractor` to support range syntax | `test_telescopic_range_dimension_parsing`<br>`test_live_page_8_exact_dimensions` | **Resolved** |
| **D-03** | **LED-670** Suspicious Unit Conversion | Page 7 | `9.5 x 10 x 5` (inch)<br>`24 x 26 x 13` (mm) | Printed table verbatim: `9.5 x 10 x 5` under `(INCH)` and `24 x 26 x 13` under `(MM)` | **Upstream Catalogue Typo**: GROZ InDesign publication printed centimeter values (`24 x 26 x 13`) under the `(MM)` column header | Preserved verbatim printed values per anti-hallucination policy (no silent unit conversion) | `test_live_page_7_exact_dimensions` | **Documented & Preserved** |
| **D-04** | **LED-685** Product Image Link | Page 9 | `images/p9_xref3683_908_137.png` (secondary folded sitelamp) | `images/p9_xref3656_305_140.png` (primary 3-head hero unit) | Ordering table was located on right half (`x > mid_x`), restricting search to right half and missing main hero on left half | Updated `ImageExtractor.match_image_to_product` to evaluate unified 2-page spreads across both halves | `test_live_page_9_image_hero_isolation` | **Resolved** |
| **D-05** | **LED-660** Dimensions Preceding Text | Page 10 | `660 55043 8.7 × 8.7 × 12.2` | `8.7 × 8.7 × 12.2` (inch)<br>`223 × 223 × 309` (mm) | `\s` matched newlines preceding dimensions, capturing model code and order number | Restricted dimension whitespace to non-newline horizontal whitespace `[^\S\n]` | `test_live_page_10_diameter_dimensions` | **Resolved** |
| **D-06** | **LED-800** Missing Dimensions | Page 10 | `— / —` | `Dia. 12-1/64"` (inch)<br>`305 mm` (metric) | Ordering table for LED-800 omitted `SIZE` column because product is circular | Added diameter callout regex (`Dia. 12-1/64" (305 mm)`) in `ProductBuilder` | `test_live_page_10_diameter_dimensions` | **Resolved** |
| **D-07** | **Fraction Box Quantity Interference** | Pages 8, 9 | Box Qty became `3`, `6`, or `None` on fractional sizes | Box Qty is `1` for LED-680T, LED-685, and LED-685T | Numbers in fraction dimensions (e.g. `1/8`, `1/2`, `3/16`) were erroneously matched as box quantities | Sanitized row text by stripping identified dimension substrings before parsing box quantities | `test_telescopic_range_dimension_parsing`<br>`test_table_multi_row_parsing_with_tripod` | **Resolved** |
| **D-08** | **Contiguous Narrative Description** | Pages 6, 7 | Jumbled disjoint lines containing matching keywords | Structured introductory lead paragraph at standard layout coordinates `(y ~ 205 pt)` | Initial regex matched disconnected phrases with "designed for" across the page | Bounded description extraction to the lead editorial block at `(y in [190, 270])` | `test_live_page_extraction_ground_truth` | **Resolved** |

---

## 3. Detailed Audit by Physical Page

### Physical Page 6 (Printed Pages 8–9)
- **Products**: `LED-550` (ORD: 55046), `LED-560` (ORD: 55047)
- **Table Type**: Split page (Left half: LED-550, Right half: LED-560)
- **Dimensions**:
  - `LED-550`: `6-11/16 × 5` inch, `170 × 125` mm. Matches original PDF table cell verbatim.
  - `LED-560`: `7-9/32 × 5-1/2` inch, `185 × 140` mm. Matches original PDF table cell verbatim.
  - Box Quantities: `10` (LED-550), `8` (LED-560). Verified against printed column.
- **Images**:
  - `LED-550`: `images/p6_xref3384_297_198.png` (Direct hero, bbox: x0=297.6, y0=198.0, x1=531.2, y1=388.8).
  - `LED-560`: `images/p6_xref3394_607_197.png` (Direct hero, bbox: x0=607.4, y0=197.3, x1=866.1, y1=408.5).
  - Secondary callouts (`xref 3402`, `xref 3412`, `xref 3431`, `xref 3435`) correctly excluded from hero slots.

---

### Physical Page 7 (Printed Pages 10–11)
- **Products**: `LED-670` (ORD: 55050), `LED-670T` (ORD: 55077)
- **Table Type**: Unified 2-page spread
- **Dimensions & Upstream Publication Discrepancy**:
  - `LED-670`:
    - `(INCH)`: `9.5 x 10 x 5`
    - `(MM)`: `24 x 26 x 13`
    - *Audit Finding*: 9.5 inches = 241.3 mm. The printed table literally displays `24 x 26 x 13` under the header `(MM)`. This is an authentic graphic design error in the GROZ InDesign publication where centimeter dimensions were placed under an `(MM)` header.
    - *Action Taken*: Preserved verbatim per requirement ("Do not silently replace values based on mathematical assumptions"). Marked for human review.
  - `LED-670T`:
    - `(INCH)`: `46 × (48 to 75-1/2) × 46`
    - `(MM)`: `117 × (122 - 192) × 117`
    - *Audit Finding*: Telescopic height range `(48 to 75-1/2)` inches and `(122 - 192)` mm (also published in cm). Extracted verbatim.
- **Images**:
  - `LED-670`: `images/p7_xref3457_284_191.png` (Hero standalone unit).
  - `LED-670T`: `images/p7_xref3503_613_196.png` (Hero telescopic tripod mounting unit).

---

### Physical Page 8 (Printed Pages 12–13)
- **Products**: `LED-680` (ORD: 55089), `LED-680T` (ORD: 55090)
- **Table Type**: Unified 2-page spread
- **Dimensions**:
  - `LED-680`: `11-3/16 × 7 × 5-1/8` inch, `288 × 176 × 131` mm. Verified verbatim.
  - `LED-680T`: `11-3/16 × (27-1/2 to 67) × 5-1/8` inch, `288 × (699 to 1702) × 131` mm. Verified verbatim.
  - Box Quantities: `1` (LED-680), `1` (LED-680T). Verified against column alignment.
- **Images**:
  - `LED-680`: `images/p8_xref3535_331_204.png` (Hero dual-head floodlight).
  - `LED-680T`: `images/p8_xref3515_363_471.png` (Hero tripod mounted unit).

---

### Physical Page 9 (Printed Pages 14–15)
- **Products**: `LED-685` (ORD: 55118), `LED-685T` (ORD: 55119)
- **Table Type**: Unified 2-page spread
- **Dimensions**:
  - `LED-685`: `25-63/64 × 2-31/32 × 3-3/16` inch, `660 × 75.5 × 81` mm. Verified verbatim.
  - `LED-685T`: `28-17/64 × 6-27/64 × 19-9/16` inch, `718 × 1630 × 497` mm. Verified verbatim.
  - Box Quantities: `1` (LED-685), `1` (LED-685T). Verified.
- **Image Association Correction**:
  - `LED-685`: Corrected to `images/p9_xref3656_305_140.png` (Primary hero 3-head sitelamp unit, area: 80,030 pt²). Previously misattributed to secondary application illustration `xref 3683`.
  - `LED-685T`: `images/p9_xref3675_370_496.png` (Telescopic tripod unit, aspect ratio: 2.49, area: 35,973 pt²).

---

### Physical Page 10 (Printed Pages 16–17)
- **Products**: `LED-660` (ORD: 55043), `LED-800-EU` (ORD: 55048), `LED-800-US` (ORD: 55051)
- **Table Type**: Split page (Left: LED-660, Right: LED-800)
- **Dimensions**:
  - `LED-660`: `8.7 × 8.7 × 12.2` inch, `223 × 223 × 309` mm. Box Qty: `8`. Verified verbatim.
  - `LED-800-EU` & `LED-800-US`:
    - Table has NO size column (specifies plug types `EU`/`US` and AC voltages).
    - Extracted technical callout dimension: `12-1/64" (Dia.)` (inch), `305 mm (Dia.)` (metric).
    - Box Qty: `1`. Verified.
- **Images**:
  - `LED-660`: `images/p10_xref3721_343_243.png` (Hero swivel sitelamp).
  - `LED-800-EU` / `LED-800-US`: `images/p10_xref3748_789_209.png` (Hero cable reel worklight).

---

## 4. Unresolved Items Requiring Human Review

The following items are authentically present in the source PDF and are flagged for human editorial decision:

1. **Page 7 (`LED-670` & `LED-670T`) Metric Dimensions**:
   - The printed table states `24 x 26 x 13` under `(MM)` for `LED-670` (actual mm equivalent of 9.5" is ~241 mm).
   - The printed table states `117 × (122 - 192) × 117` under `(MM)` for `LED-670T` (actual mm equivalent of 46" is ~1168 mm).
   - *Decision required*: Should the customer-facing frontend display the verbatim printed numbers (`24 x 26 x 13`), or should an editorial override flag be introduced in the schema? (Currently preserved verbatim as `unverified`).

2. **Page 9 (`LED-685T`) Telescopic Height in Inches**:
   - The printed table states `28-17/64 × 6-27/64 × 19-9/16` inch, while the mm equivalent is `718 × 1630 × 497 mm`.
   - `1630 mm` corresponds to ~`64 inches`, suggesting `6-27/64` was a typographical error for `64-27/64` or `(27-1/2 to 64)` in the original print publication.
   - *Decision required*: Editorial override vs verbatim preserve. (Currently preserved verbatim as `unverified`).

---

## 5. Automated Verification Status

- **Automated Tests**: 12/12 passing (`tests/test_schema.py`, `tests/test_extraction.py`).
- **Extraction Prototype**: 11/11 records extracted cleanly with full provenance, exact bboxes, and zero invented fields.
- **Verification Status**: All 11 records remain strictly marked as `unverified` pending human sign-off.
