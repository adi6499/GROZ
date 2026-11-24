# Applied 24 Nov 2026: extraction rules 3.1.0 (decision I, worklight front views)

- **Approval:** task 2 of Mitul's groz.tools checklist ("fix LED/360, LED/375, LED/396 pictures": they showed the back of the light); the project owner said "yes start task 2" on 24 Nov 2026.
- **Code:** commit `f2171dd` (pipeline version 3.1.0).
- **Regeneration:** `run_extraction.py batch batch_1`, then the cumulative dataset and reports.
  - Record count: still 150 in `batch_1`. No record was lost or added; no value other than these five pictures changed.
  - The result matches the dry run made before the commit, picture for picture.

What changed (`changes.csv`, `before_after.png`):
- **LED/360** (p16), **LED/375** (p17), **LED/396** (p19), **LED/397** (p21): the lighting catalogue prints each of these worklights twice, its front (the lit face, with callouts such as "COB light", "SMD Worklight", "Top torch") and its back (hook, magnets, switch). They now show the front.
- **LED/140** (p26): showed the night-time photo that opens the FLASHLIGHTS chapter; it now shows the light itself (its front view, "3W COB LED").

How it works:
- A callout belongs to the picture its thin leader line is drawn into, not to the picture printed nearest to it (on p16 the LED/360 callouts sit closer to the back picture).
- Lighting catalogue only. When the picture the layout rules chose has no callout naming the light, and exactly one other large picture in the same printed section has one, that front view is used. Pictures labelled with a product code and tripod models are never replaced; pages without leader lines are left as they are (e.g. LED/800 on p10).

A 360° view (Mitul's question): the catalogue prints one picture per side shown, at most two. A real 360° view needs 24–36 photos of the product turned on a turntable, taken for each product; it cannot be made from the catalogue, and the site does not fake one with AI.
