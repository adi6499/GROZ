# GROZ catalogue website — internal demo guide (14 Oct 2026)

Local only: do not deploy, publish or share the address outside this computer. The catalogue content belongs to GROZ.

## Launch

From `C:\Users\Analyst Profile\Downloads\GROZ`:

```bash
.venv/Scripts/python.exe build_site_data.py
.venv/Scripts/python.exe serve_site.py
```

Open http://127.0.0.1:8962/site/. Stop the server with Ctrl+C.

- Rebuilding is only needed after `output_v2` or the review previews change, but it is safe to repeat.
- For a clean start, clear this site's data in the browser (it only holds the saved list, quote list and view choice).

## Walkthrough (about 5 minutes)

1. **Home.** 941 products from 4 GROZ catalogues. The note above the products says plainly that none is verified yet; open "How to read the labels" to explain the badges.
2. **Find.**
   - Type `led 621`, then `55044` (an order number), then `club hammers` or `micrometer`.
   - Codes match in any spelling (`LED/621`, `led-621`).
   - Titles come from the printed catalogue page.
3. **Filter and sort.**
   - Click the *LED Worklights* category, then *IP rating: IP65*.
   - Remove a chip, and sort by *Printed title A–Z*.
   - Switch Cards/Table: the search stays.
4. **Product.**
   - Open a product. Show its source line, the PDF page link ("Catalogue page"), the printed-title evidence and the table row as extracted.
   - Use Previous/Next or the ← → keys to step through results.
   - LED/621 shows a beam angle "Under review".
5. **Compare.** Tick *Compare* on 2–4 products and open the dock's Compare: "Not specified" and "Under review" cells are explicit; remove one.
6. **Save.** Tap the heart; reload the page; the saved list (heart icon in the header) is still there.
7. **Quote.**
   - Add products, use − / + to set quantities, and try *Prepare request* empty to show the validation.
   - Then fill in a name and email.
8. **Export.**
   - Copy, download .txt/.csv, or print.
   - The request says it was **not sent**. There is no sending backend, by design.

On a phone-sized window, show:
- the header search;
- the Filters bottom sheet;
- product details and the quote as bottom sheets;
- the stacked quote lines.

## What to say about the data

- Every product shows **Not yet verified** (3 show **Needs review**). Verification needs a person; nothing is marked verified automatically.
- **49 values** show *Under review*: a corrected reading is ready but not yet approved (decision E), so the old values are withheld.
- **261 products** have no confirmed image:
  - 211 have a nearby picture that is not linked to the product ("Image not confirmed");
  - 50 have none ("Image unavailable").
- **Titles:** read from each product's own heading in the PDF (`review/display_titles.csv` lists every case). 111 products have an extracted heading from another product or section; the extraction fix is decision F, awaiting approval.
- Hand Tool and Fluid Handling catalogues are not included yet. The Hand Tool pilot is prepared but has not been run.

## Approvals still needed

Recorded in `review/editorial_decisions.json` and `NEXT_PHASE_REPORT.md`; nothing in `output_v2` changes until approved:

- **A:** LED/800 dimensions.
- **B:** ORD 62900 note wording.
- **C:** index discrepancies (documented only).
- **D:** TCHL net weight note.
- **E:** apply extraction rules 2.1.0 (releases the 49 withheld values).
- **F:** heading rule.
- **The five-page Hand Tool pilot.**
