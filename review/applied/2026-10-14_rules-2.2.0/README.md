# Applied 14 Oct 2026: extraction rules 2.2.0 (decisions A, B, D, E, F)

- **Approval:** the project owner approved decisions A–F on 14 Oct 2026. C is documentation only and changes no data.
- **Code:** commit `3df9ad3` (pipeline version 2.2.0).
- **Regeneration:** `output_v2` was regenerated with `run_extraction.py recovery`.
  - The previous batch files are archived in `output_v2/batches/history/`; they are also in git at `36bc63a`.
  - Record count: still 941 (150 + 791), with no record lost or added.
  - Verification statuses are unchanged: 938 not yet verified, 3 need review.

| Decision | What changed | Records |
|---|---|---|
| A | LED/800/EU and /US: size fields left empty (the table has no SIZE column); the diagram's diameter callout is kept verbatim as `specifications.diameter = 12-1/64" (305 mm)`, with a note | 2 |
| B | Duplicate ORD 62900: the same note on EMLTT/CH-25W and EMLTT/CH-45W, without guessing 62902 | 2 |
| D | TCHL/14-10D/2/BL and /OR: note that `4 KG (21 LBS)` has inconsistent kg/lb figures (value kept as printed) | 2 |
| E | Capacities read from each product's own panel (drawer/overall load, net weight) and beam angles from the lighting spec strip only (rules 2.1.0) | 91 (109 fields) |
| F | `sub_title` is the title printed for the product's own table (850 headings changed) | 850 |
| F (kept printed text) | Table captions (159), knurl matrix labels as `variant_label` (48), the row's printed description (5, e.g. LED/685T "Sitelamp complete with tripod") | 212 |
| derived | `confidence` recomputed from the new specifications (105, all increased; statuses unchanged) | 105 |

Files:
- `all_changes.csv`: every changed field, with its before and after value and the decision (1,288 rows). It was produced by `make_all_changes.py`.
- `preview_batch_1.*`, `preview_batch_2.*`: the previews generated before the change (they omit `sub_title` and `confidence`).
- `headings_before.csv`: the old extracted heading next to the printed title, with the rule and PDF page, for every product whose heading changed.
