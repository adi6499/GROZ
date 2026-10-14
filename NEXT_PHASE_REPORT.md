# GROZ next phase: decisions, technical gaps, Hand Tool pilot preparation

**Date:** 14 Oct 2026 · **Status:** preparation complete. **The Hand Tool pilot has not been run.** Batch 3 has not been run, the brochures were not processed as product sources, and nothing was built or deployed. `output_v2/` records are unchanged.

## 1. What was inspected

- **Repository state:** git history (`012245d` … `36bc63a`), working tree, README, RECOVERY_REPORT and the change reports.
- **Integrity:** the backup zip, the legacy `output/` folder, and the `output_v2/` counts (941 = 150 + 791; 813 matched, 128 added, 0 missing). All matched what was reported.
- **Decision A:** GL-10 physical page 10, including the rendered LED-800 dimension diagram.
- **Decision B:** Estwing physical page 11, plus a search of all 8 PDFs for 62900/62901/62902.
- **Decision C:** the Precision index (pages 82–83) against physical pages 14 and 77, including the rendered page 77.
- **Gaps:**
  - capacity blocks and panel headings on tools_storage pages 4, 6, 7, 11 and 20–26;
  - the spec-icon strip on every GL-10 page with a beam-angle value.
- **Pilot readiness:** the pilot configuration, runner, cumulative builder and CLI; the Hand Tool index pages (254–257); the printed page numbers of the 5 pilot pages (read-only, no extraction).

## 2. What changed and why

| Commit | Change | Why |
|---|---|---|
| `d9df38d` | Capacities read per product: each label paired with the value printed above it, assigned to the panel headed by the product's CAT NR, else to its own table area; decimals read whole | p25–26 values were empty; p4, 6, 7, 11 and 20 had the first variant's values copied to every variant; "4.5 KG" was stored as "5 KG" |
| `d9df38d`, `0e48ff4`, `1847d4a` | Beam angle only from the spec-icon strip (a top-area line of tile values), verbatim; two strip angles → empty | "270° Swivelling" (LED/621) and similar callouts were stored as beam angles. The two refinements came from spot-checking the preview (p11: lumens-only strips; p5/p21: "BLUETOOTH" captions) |
| `b76ff7c` | Editorial decision log and index discrepancy list | Decisions A–D documented with evidence; index issues kept separate from extraction defects |
| `279ad31` | Pilot hardening (details below) | The pilot would have written into `output_v2` and been merged there; the CLI had an approval bypass; nothing stopped other Batch 3 pages |
| `66c1366` | Fixed a variable clash in the index check | My bug, introduced in `279ad31`. It made `compare` fail loudly before writing anything. Test extended |
| `46a7e6e` | Regenerated `output_v2/reports/change_report.md` (+ `index_discrepancies.csv`) | Adds §15 (decisions) and §16 (index discrepancies). Report files only |
| `d7db3ce` | `review/preview_batch_1.*`, `review/preview_batch_2.*` | Shows the effect of the capacity and beam-angle rules before they are applied |

Pilot hardening in `279ad31`:
- `batch_3_pilot` writes only to `output_pilot_handtool/`. No batch may write into another batch's folder, and the cumulative build refuses to merge the pilot into `output_v2`.
- The `--allow-unapproved` CLI flag is removed. Approval is the `approved` flag in `backend/pipeline/batches.py`, changed in its own commit.
- `status` command: runs every gate without extracting.
- Batch 3 catalogues allow only listed pages: the 5 Hand Tool pilot pages, and no Fluid Handling pages. Brochures are still refused.
- Extraction refuses uncommitted extraction code. Manifests record pipeline version 2.1.0, commit, source PDF SHA-256, pages and approval state.
- A replaced batch file is archived in `batches/history/`.
- The index check is scoped to the printed pages processed. ORDs indexed to a pilot page but printed on a neighbouring page are reported as outside scope, not as missing.
- Pilot report: records, missing values, ambiguous matches, unresolved images, gate results, counterparts in `output_v2`/legacy by ORD (compared, never merged), and changes since the previous run.

Preview of the new rules (not applied; `output_v2` unchanged):

| Batch | Records | Field changes | Notes |
|---|---|---|---|
| batch_1 | 150 matched, 0 added, 0 missing | 109 | All 91 new values printed on their page |
| batch_2 | 791 matched, 0 added, 0 missing | 0 | |

The 109 batch_1 changes:
- **47 capacity changes:** 35 values added, 12 corrected.
- **62 beam-angle changes:**
  - 25 glyph-only (e.g. `120°` → `120˚` as printed);
  - 19 corrected values (e.g. LED/621 `270°` → `60˚`, LED/670 `180°` → `110°`);
  - 18 emptied, where the product's page has no strip angle or two of them (e.g. LED/685, LED/800, LED/230).

LED/160's `20˚` stays empty: it stands alone on its line and can't be distinguished from a callout.

## 3. Tests run and actual results

`.venv/Scripts/python.exe -m pytest -q`: **95 passed** (final run, 58 s).

| Group | Count |
|---|---:|
| Tests at session start (all passing at start) | 71 |
| New capacity / beam-angle regression tests | 5 |
| New pilot-safety and report tests | 19 |
| **Total** | **95** |

Gate tests disable page extraction, so a failing gate can never produce pilot records.

## 4. Backup and legacy-output integrity (checked at start and end of the session)

| Check | Result |
|---|---|
| `Downloads\GROZ_BACKUP_2026-10-14_pre-recovery.zip` | 576,698,152 bytes, 7,112 files, **CRC test OK**, last modified 2026-10-14 10:52:50 (not modified this session) |
| Legacy `output/` vs backup | 1,210 / 1,210 files byte-identical |
| Legacy `output/` vs baseline commit `012245d` | identical; no untracked files added |
| `output_v2/extracted_products.json` and batch files | byte-identical (SHA-256) to the start of this session |
| `output_pilot_handtool/` | does not exist (pilot never run) |

I ran `run_extraction.py batch batch_3_pilot` once, deliberately, to test the gate. It stopped with "not approved" before reading any page and created nothing.

An untracked `index.html` ("GROZ Product Catalogue — Local Portal", created 12:18 today) appeared in the project root during the session. It was not created by me. I left it untouched and uncommitted.

## 5. Decisions needing your approval

Details and evidence: `review/editorial_decisions.json`; summary in change report §15.

| ID | Item | Proposal |
|---|---|---|
| A | LED/800 EU/US size | Empty the size fields: the table prints no size. Record the callout verbatim as `specifications.diameter = '12-1/64" (305 mm)'`, with a note quoting `Dia. 12-1/64" (305 mm)` |
| B | 62900 note | Replace the "likely 62902" guess with the factual wording in the log, and attach the note to both EMLTT/CH-25W and CH-45W. Both ORDs stay `62900` as printed |
| C | Precision index discrepancies | Keep the data and the list (`output_v2/reports/index_discrepancies.csv`): 3 index-only numbers and 29 non-indexed printed products, with the 01217 ↔ 01227 pair flagged. Optionally ask GROZ |
| D | TCHL/14-10D/2 `4 KG (21 LBS)` (new) | Keep verbatim; add a kg/lb inconsistency note |
| E | Apply rules 2.1.0 to `output_v2` | Re-extract batch_1/2 and regenerate reports. This applies exactly the 109 previewed changes, with the previous files archived in `batches/history/` |
| F | **Run the Hand Tool pilot** | See §6 |

## 6. Is the Hand Tool pilot ready for approval?

**Yes.** On approval I would:
1. Set `approved=True` for `batch_3_pilot` in its own commit.
2. Run `python run_extraction.py batch batch_3_pilot`.
3. Stop and report.

Hand Tool pages 8, 11, 12, 53 and 224 (printed 9, 10, 51, 222; page 8 is a divider) would be written only to `output_pilot_handtool/`.

The pilot report would show:
- every record;
- the gates against the printed pages;
- the Hand Tool index check for printed pages 9/10/51/222;
- missing values, ambiguous matches and unresolved images;
- side-by-side comparisons where the same ORD already exists. The p224 calipers (Precision ID/OD/DD) would be compared, not merged.

The pilot would use rules 2.1.0 whether or not E is approved, because E only concerns `output_v2`.

## 7. Files and commits

- **Reports:** `NEXT_PHASE_REPORT.md` (this file), `RECOVERY_REPORT.md` (pointer added), `README.md` (commands, safety rules, outputs).
- **Decision log:** `review/editorial_decisions.json`.
- **Previews:** `review/preview_batch_1.md` / `.csv`, `review/preview_batch_2.md` / `.csv`.
- **Change report:** `output_v2/reports/change_report.md` (§15–16), `output_v2/reports/index_discrepancies.csv`.
- **Code:**
  - `backend/pipeline/{batches,runner,cumulative}.py`
  - `backend/extractor/product_builder.py`
  - `backend/validator/coverage.py`
  - `backend/reports/{editorial,pilot_report,change_report}.py`
  - `run_extraction.py`
- **Tests:** `tests/test_recovery_regressions.py`, `tests/test_pipeline_safety.py`.
- **Commits this phase:** `d9df38d`, `b76ff7c`, `279ad31`, `0e48ff4`, `1847d4a`, `66c1366`, `46a7e6e`, `d7db3ce`, plus the documentation commit containing this file.
