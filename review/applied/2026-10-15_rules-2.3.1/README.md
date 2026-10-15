# Applied 15 Oct 2026: extraction rules 2.3.1 (decision H, clean product pictures)

- **Approval:** the project owner asked for the pictures to be fixed on 15 Oct 2026 ("yes fix the pictures"), after seeing that many product pictures included catalogue text, icons or neighbouring products.
- **Code:** commit `1dd3e42` (pipeline version 2.3.1).
- **Regeneration:** `output_v2` was regenerated with `run_extraction.py recovery`.
  - Record count: still 941 (150 + 791). No record was lost or added.
  - Verification statuses and confidence scores are unchanged.
  - The result matches a full dry run picture for picture.

What changed:
- **Picture files:** 679 of the 683 files in `output_v2/images/` were re-rendered. Each is now the picture alone, exactly as printed (position, rotation, transparency, clipping), without the page's text, line art or other pictures, and with white margins trimmed.
  - All 262 pictures the website shows were checked on contact sheets.
  - The 4 files left unchanged are no longer extracted (see below) and are kept, unreferenced.
- **How it works:**
  - On a private copy of the page, text is made invisible, shapes are traced but not painted (so clipping paths still cut photos to shape), and the other pictures are hidden.
  - PDF redaction is not used: it broke the masks of some photos (the Estwing G-bar and construction bars became blue rectangles).
- **Decoration:** what a picture actually draws decides whether it is a product picture. Four pictures draw only an icon-sized close-up (or nothing) on a mostly empty canvas, and are no longer candidates:
  - Estwing p15: two blade close-ups;
  - Estwing p7: an empty frame;
  - Lighting p22: a torch-tip close-up whose canvas covers most of the spread.
- **Picture assignments** (6 records, each checked on its page):

| Product | Before | Now |
|---|---|---|
| LED/185 | the torch-tip close-up (as "largest picture") | the folding worklight above its table |
| EPAX-336F | the lifestyle photo (man carrying a mattock) | the Pulaski axe printed above its table |
| RTC/42-20/4/GRZ, /4B | the "perforated side wall" detail photo | the cabinet printed under its code tag (tag reach 60 → 120 pt: the panel's size line and capacity icons come first) |
| RTC/42-20/3/GRZ, /3B | the same cabinet, as the section's largest picture | the same cabinet, now as "code printed beside the image" (variant: base model) |

Pictures shown: 879 (unchanged). Direct product pictures: 88 → 90.

Files:
- `all_changes.csv`: every changed record field (6 rows), produced by `make_all_changes.py`.
- `pictures.csv`: every picture file with its pixel size before and after, and how many products show it, produced by `make_picture_list.py`.
- `before_after_examples.png`: eight pictures before and after.
- Regression tests: `tests/test_image_evidence.py`. They check that the crop has no page text, that clipped photos keep their shape, that crops are trimmed, and the decoration and tag-reach cases.
