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

1. **Home.** 2892 products from 6 GROZ catalogues. The note above the products says plainly that none is verified yet; open "How to read the labels" to explain the badges.
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
   - LED/621 shows the beam angle printed in its spec strip (60˚), not the "270° Swivelling" callout.
   - G/10/M1 shows the printed table caption "TAPER SHANK ARBORS - DIN 238".
5. **Compare.** Tick *Compare* on 2–4 products and open the dock's Compare: "Not specified" cells are explicit; remove one.
6. **Save.** Tap the heart; reload the page; the saved list (heart icon in the header) is still there.
7. **Quote.**
   - Add products, use − / + to set quantities, and try *Prepare request* empty to show the validation.
   - Then fill in a name and email.
8. **Export.**
   - Copy, download .txt/.csv, or print.
   - The request says it was **not sent**. There is no sending backend, by design.

9. **Dark mode.** Click the moon in the header. The new theme spreads from the button with a frosted-glass reveal, and the whole site switches, including the dialogs, while the catalogue pictures stay on soft light tiles. Reload: the choice is kept. Click the sun to return. By default the site follows the device's light or dark setting.

10. **Unboxing.** In Cards view, click a product's picture or code. The picture turns into a GROZ carton, the flaps open, the product rises out, and the details panel grows from the box and the specifications fade up into their rows (about 0.8 s). Use Previous/Next inside the dialog (or the arrow keys): the old picture swings out as the new one swings in. Close the details: the picture sinks back into the box, the flaps close and the box settles back onto the card.

11. **GROZ categories.**
    - Open *Categories* in the header (on a phone, the menu): GROZ's own eight categories in GROZ's order, plus Precision Tools.
    - Lubrication, Fuel & DEF, Air Tools, Lighting, Hand Tools, Mechanic's Tools, Power Tools and Precision Tools show their products.
    - New & Exciting says "Coming soon": there is no catalogue for it yet.

12. **Motion.**
    - Move the mouse over a card: it leans toward the pointer with a soft glare.
    - Click *Add to quote*: the picture is tossed into the Quote button, and its count rolls up.
    - Click a heart: it bursts.
    - Pick a category: the count counts down and the new cards rise in one after another.
    - Scroll down: further cards rise as they come into view, and the orange line under the header fills up.
    - Move the mouse over the hero: a spotlight follows it. Click the hammer: it strikes, with sparks.
    - Hover the category tiles: each icon acts out its tool (lamp lights, hammer swings, drawers slide, drill spins…).
    - Tick *Compare* on a second product: its picture flies into the compare bar.
    - *Prepare request* in the quote: the request prints out of a slot and is stamped "Ready · not sent", with confetti.
    - Watch the hero search box: it types example searches. The hero numbers count up when the page opens.
    - In a product's details, hover the picture: a magnifier shows it closer.
    - Scroll far down: a round arrow appears at the bottom right; press it and it lifts off back to the top.
    - Search "micrometer", then change the sort: the cards shuffle into their new places.
    - Close any dialog: it fades away instead of vanishing. On a phone, the menu and the filter sheet slide in and out.
    - Save a product: a heart flies to the saved button. Watch the embers rising behind the hero hammer.
    - Open the site in a new tab: the GROZ logo assembles from tool parts first (once per visit; *Skip* or <kbd>Esc</kbd> ends it).
    - Sounds are off at first. Turn them on with the speaker button in the header; the site remembers the choice.
    - Move the mouse along the header links and down the Categories menu: a highlight glides with it. Click into a search box: a light runs around its edge.

13. **Flipbook.**
    - In *Catalogues*, open the 3D flipbook (or a catalogue's *Interactive Flipbook*). Turn pages with the arrows, the page corners, ← → or a swipe; pick a page in the filmstrip or click the page counter to type one.
    - Pages with products show "N products on this page": hover it for the list, click it for the specifications drawer. The drawer shows each product's status ("Not yet verified"), where its picture comes from and a link to the PDF page.
    - *Add to quote* in the drawer adds to the same quote as the catalogue page (go back: the Quote count includes it).
    - *Zoom 2x* (or double-click, or <kbd>Z</kbd>): move the pointer to look around the page.
    - *Magnifier* (or <kbd>M</kbd>): a round lens follows the pointer and shows the page sharply enlarged; scroll to change the size. On a phone, hold a finger on the page.
    - The Lubrication catalogue can be read in the flipbook, but its products are not in the product list yet (see below).

On a phone-sized window, show:
- the header search;
- the Filters bottom sheet, and the Filters/sort bar that stays under the header while you scroll;
- product details and the quote as bottom sheets;
- the stacked quote lines;
- the *Dark mode* switch in the menu.

## What to say about the data

- Products not yet checked by a person carry no badge on their card; their details say **Not yet verified**, and a short note above the catalogue tells visitors to check the catalogue page before ordering. A product turns **Verified** (green badge) only when a person checks it in the verification tool, which compares its values with its printed row (see below), and then shows who checked it and when. Nothing is marked verified automatically.
- **Approved corrections are in** (decisions A–F, rules 2.2.0, 14 Oct 2026).
  - Capacities and beam angles are read from each product's own panel or strip.
  - Every heading is the title printed for the product's own table.
  - Printed table captions and row descriptions are kept.
  - The catalogue's own inconsistencies carry review notes rather than guesses.
  - Every changed value, before and after, is in `review/applied/2026-10-14_rules-2.2.0/`.
- **Pictures are linked by page evidence** (decision G, rules 2.3.0, applied 15 Oct 2026; `review/applied/2026-10-15_rules-2.3.0/`).
  - Before the Fluid Handling catalogues went live, 879 of 941 products showed a picture: 90 printed beside (or on the tag above) their own code, 789 family pictures (their section's picture, or one labelled for their base model or caption). Each says why on the product page, and each picture is shown alone, without the catalogue text around it (rules 2.3.1).
  - **62 products** have no confirmed image: 59 have a nearby picture that the page does not tie to them ("Image not confirmed"), 3 have none ("Image unavailable"). Mostly variants whose page pictures other variants but not them.
- The Fluid Handling CC-07 and Fuel CAT 400 catalogues went live on 21 Oct 2026 (1951 products, after the owner approved their preview). The full Hand Tool catalogue is not included yet: its five-page pilot was approved and run on 17 Oct 2026, but the rest has not been extracted.
- **Lubrication:** a quick table scrape of the Lubrication catalogue was on the site briefly (Oct 2026) and was taken off, because about a third of its "products" were table labels, its pictures were whole pages and some values were made up. The catalogue stays readable in the flipbook. Its products will be extracted with the same checks as the others and shown for approval before they go live.

## Still open

- **Verification:** checking the products in the verification tool (none is verified yet).
  - Start it with `.venv/Scripts/python.exe verify_server.py`, then open http://127.0.0.1:8963/verify/.
  - Enter your name. For each product, compare its values with the printed row, then press <kbd>V</kbd> (verified) or <kbd>F</kbd> (flag a problem).
  - Press "Update catalogue site" to show the results on the catalogue.
- **C:** catalogue index discrepancies (documented only; questions for GROZ).
- **Hand Tool pilot fixes** (awaiting approval), then the rest of the Hand Tool catalogue.
