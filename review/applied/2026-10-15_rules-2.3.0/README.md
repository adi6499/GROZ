# Applied 15 Oct 2026: extraction rules 2.3.0 (decision G, product pictures)

- **Approval:** the project owner approved decision G on 14 Oct 2026, after reviewing its preview (374 picture changes).
- **Code:** pipeline version 2.3.0, in three commits:
  - `2033b7e`: the rules, as previewed;
  - `57d279a`: caption and section pictures carry the layout rule's strength;
  - `135592b`: code tags. This was found while checking the applied data: a tool storage panel's code tag labelled the series photo printed above it, and page-header tabs could label a usage photo.
- **Regeneration:** `output_v2` was regenerated with `run_extraction.py recovery`.
  - Record count: still 941 (150 + 791). No record was lost or added.
  - Verification statuses are unchanged: 938 not yet verified, 3 need review.
  - The result matches the full dry runs picture for picture.
- **Difference from the approved preview:** 383 picture changes instead of 374. The tag fix changed 17 records relative to the previewed result:
  - 13 tool storage products now show the cabinet, cart or tool box printed under their own code tag, instead of the series photo above it.
  - The two work benches (WBN/60-20/1, WBN/79-20/2) keep their picture, now as direct pictures.
  - LED/345 and LED/150 keep the same picture, but as family pictures: their only "label" was the page tab.
  - Every one was checked on its page.

| Change | Records |
|---|---|
| Picture added (was "Image not confirmed" or "Image unavailable") | 225 |
| Picture replaced by a better-evidenced one | 113 |
| Same picture, now `direct_product` (its own code is printed under it, or on the tag above it) | 10 |
| Same picture, now `product_family` (the "code beside the image" was an ordering-table cell or a page tab) | 9 |
| Picture withdrawn: it was labelled for another product and linked by layout only | 26 |
| Same picture and type, evidence sentence restated | 334 |
| `sub_title`: EKIT-2F `AXE KIT: AXE WITH SHARPENER` → `POWER DUO - 2PC KIT` (the title printed over its own column) | 1 |
| `confidence` (derived): image evidence bonus +0.05 gained (228) or lost (27) | 255 |

Pictures shown: 680 → 879. Direct product pictures: 49 → 88. Family pictures: 631 → 791. Unresolved: 211 → 59. No picture: 50 → 3.

Every page whose picture changed was checked against the rendered page with the old and new pictures marked. Examples:
- **Tweezers** (Precision physical pages 58–59) and **scribers** (page 40): each now has its own picture. These photos are 21–43 pt wide and were dropped as icons before.
- **Pin vices** (page 60) and **edge finders** (page 33) are diagonal cut-outs with overlapping boxes. Each code is matched to the tool actually drawn above it.
- **Tool bits** (page 57) take the only picture of their section on the facing page 56.
- **Arbors** (page 61) take the pictures captioned like their tables (JACOBS TAPER ARBORS, TAPER SHANK ARBORS - DIN 238).
- **Tool storage panels** (e.g. RTC/27-10/4/GRZ, RTC/42-20/2/GRZ, MTB/3L, MTB/5L) take the picture under their own code tag.
- **Withdrawn pictures:**
  - Ten steel body scribers no longer show the aluminium scriber MS/380A.
  - MMED/1 and /2 no longer show the IP65 micrometer MMED/1/65.
  - Further cases: EDC/8 and /12, DTI/40M, EF/3, /5, /6, /9 and the EF sets, PV/2A–4A and the PV set, TWZ/ST-6.

Notes:
- **WG/RD/3** (Precision p16): the code is printed centred under both faces of the round gauge. The picture moved from the metric face to the gauge face, and both show WG/RD/3. Its confidence went 0.85 → 0.80 because the older region heuristic scores the right-hand face lower; its status is unchanged.
- **Batch history** (`output_v2/batches/history/`; every archive is kept):
  - `*.20261014T12*`: the 2.2.0 batch files, byte-identical to commit `15748b9`.
  - `*.20261015T0510*`/`T0511*`: the first 2.3.0 run (section pictures at strength 0.6), superseded by `57d279a`.
  - `*.20261015T0525*`: the second 2.3.0 run (before the tag rule), superseded by `135592b`.

Files:
- `all_changes.csv`: every changed field, with its before and after values and the kind of change (973 rows in 717 records), produced by `make_all_changes.py` from the 2.2.0 dataset at `15748b9`.
- `preview_batch_1.*`, `preview_batch_2.*`: the previews the approval was based on (picture changes only; they omit evidence-only changes, `sub_title` and `confidence`).
- Regression tests: `tests/test_image_evidence.py`.
