"""GROZ extraction command line. Run from the project root.

  python run_extraction.py list                 batches, approval status and output folders
  python run_extraction.py status               run every safety check for every batch, without extracting
  python run_extraction.py batch batch_1        extract a batch into its own folder, then rebuild its reports
  python run_extraction.py preview batch_1      re-extract an approved batch into a temporary folder and
                                                report differences vs the current dataset (writes review/ only)
  python run_extraction.py cumulative           rebuild output_v2/extracted_products.json from batch files
  python run_extraction.py report               coverage gates + summary.md + review.html (output_v2)
  python run_extraction.py compare              change report vs the legacy dataset (+ decisions, index list)
  python run_extraction.py pilot-report NAME    rebuild a dedicated-folder batch's report from its files
  python run_extraction.py recovery             batch_1 + batch_2 + cumulative + compare + report

There is no option that bypasses the approval gate: a batch is approved by setting approved=True for
it in backend/pipeline/batches.py, in its own commit. Extraction commands refuse to run while the
extraction code has uncommitted changes, so every manifest records an exact commit.
Options: --out DIR (main dataset folder, default output_v2), --legacy FILE, --allow-shrink.
"""

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile

from backend.pipeline.batches import BATCHES, BATCH_ORDER
from backend.pipeline.cumulative import CUMULATIVE_NAME, build_cumulative
from backend.pipeline.runner import (DEFAULT_OUTPUT_DIR, PIPELINE_VERSION, batch_output_dir, batch_path, code_version,
                                     guard_output_dir, preflight, run_batch)
from backend.reports.change_report import compare, write_change_report
from backend.reports.editorial import index_discrepancies, load_decisions
from backend.reports.pilot_report import write_pilot_report
from backend.reports.summary import load_manifests, pages_by_pdf, write_review_html, write_summary_md
from backend.validator.coverage import coverage_problems, coverage_report

LEGACY_DATASET = os.path.join("output", "extracted_products.json")
REVIEW_DIR = "review"


def _coverage(out: str):
    with open(os.path.join(out, CUMULATIVE_NAME), encoding="utf-8") as f:
        records = json.load(f)
    manifests = load_manifests(out)
    cov = coverage_report(records, pages_by_pdf(manifests))
    return records, manifests, cov, coverage_problems(cov)


def cmd_report(out: str) -> None:
    records, manifests, cov, problems = _coverage(out)
    write_summary_md(os.path.join(out, "reports", "summary.md"), records, cov, manifests, problems)
    changes = {}
    cj = os.path.join(out, "reports", "change_report.json")
    if os.path.exists(cj):
        with open(cj, encoding="utf-8") as f:
            changes = json.load(f)["changed_keys"]
    write_review_html(os.path.join(out, "review.html"), records, changes)
    print(f"Reports: {out}/reports/summary.md, {out}/review.html ({len(problems)} coverage findings)")


def cmd_compare(out: str, legacy: str) -> None:
    records, _, _, problems = _coverage(out)
    discrepancies = [row for pdf in sorted({r["source_pdf"] for r in records})
                     if pdf == "Precision_Catalogue_CA_03.pdf" for row in index_discrepancies(records, pdf)]
    res = write_change_report(out, legacy, os.path.join(out, CUMULATIVE_NAME), coverage_problems=problems,
                              decisions=load_decisions(), discrepancies=discrepancies)
    print(f"Change report: {out}/reports/change_report.md (+ .csv): {res['pairs']} matched, "
          f"{len(res['added'])} added, {len(res['missing'])} missing, {len(res['rows'])} change rows")


def cmd_preview(name: str, out: str) -> None:
    """Re-extract an approved main-dataset batch into a temporary folder and diff it with <out>/batches/<name>.json."""
    batch, own = preflight(name, require_committed_code=True)
    if batch.output_dir:
        raise SystemExit(f"preview is for main-dataset batches; '{name}' has its own folder ({own}).")
    current_path = batch_path(out, name)
    with open(current_path, encoding="utf-8") as f:
        current = json.load(f)
    tmp = tempfile.mkdtemp(prefix=f"groz_preview_{name}_")
    try:
        new = [p.model_dump() for p in run_batch(name, out_dir=tmp, require_committed_code=True, log=lambda *_: None)]
        res = compare(current, new)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(REVIEW_DIR, exist_ok=True)
    base = os.path.join(REVIEW_DIR, f"preview_{name}")
    with open(base + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res["rows"][0].keys()) if res["rows"] else ["change"])
        w.writeheader()
        w.writerows(res["rows"])
    L = [f"# Preview: {name} re-extracted with the current code (not applied)", "",
         f"- Current: `{current_path}` ({len(current)} records). Preview: pipeline {PIPELINE_VERSION} at `{code_version()}` "
         f"({len(new)} records), extracted into a temporary folder and deleted; `{out}/` was not changed.",
         f"- Matched {res['pairs']}, added {len(res['added'])}, missing {len(res['missing'])}, field changes {len(res['rows'])}.",
         "- `preview_" + name + ".csv` lists every change; `pdf_check` shows whether the new value is printed on its page.", "",
         "| Change | Catalogue | Page | CAT NR | Field | Current | Preview | New value in PDF |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in res["rows"]:
        L.append("| " + " | ".join(str(x).replace("|", "\\|") for x in (
            r["change"], r["source_pdf"], r["page"], r["cat_nr"], r["field"], r["legacy_value"] or "—",
            r["new_value"] or "—", r["pdf_check"])) + " |")
    with open(base + ".md", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(f"Preview {name}: {res['pairs']} matched, {len(res['added'])} added, {len(res['missing'])} missing, "
          f"{len(res['rows'])} field changes -> {base}.md")


def cmd_status() -> int:
    """Run every pre-extraction safety check for every batch; nothing is read or written."""
    for n in BATCH_ORDER:
        try:
            _, out = preflight(n)
            print(f"{n:15} READY      -> {out}/")
        except (PermissionError, RuntimeError, FileNotFoundError) as e:
            print(f"{n:15} BLOCKED    {e}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["list", "status", "batch", "preview", "cumulative", "report", "compare",
                                        "pilot-report", "recovery"])
    ap.add_argument("batches", nargs="*")
    ap.add_argument("--out", default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--legacy", default=LEGACY_DATASET)
    ap.add_argument("--allow-shrink", action="store_true")
    a = ap.parse_args(argv)
    guard_output_dir(a.out)

    if a.command == "list":
        for n in BATCH_ORDER:
            b = BATCHES[n]
            print(f"{n:15} {'approved' if b.approved else 'NOT APPROVED':13} -> {batch_output_dir(b)}/  {b.description}")
        return 0
    if a.command == "status":
        return cmd_status()
    if a.command in ("batch", "preview", "pilot-report") and not a.batches:
        ap.error("name at least one batch, e.g. batch_1")

    if a.command == "batch":
        for n in a.batches:
            batch, out = preflight(n, require_committed_code=True)
            run_batch(n, out, allow_shrink=a.allow_shrink, require_committed_code=True)
            if batch.output_dir:
                res = write_pilot_report(out, n)
                print(f"Pilot report: {out}/reports/{n}_report.md ({res['records']} records, {len(res['problems'])} gate findings)")
            else:
                build_cumulative(out, allow_shrink=a.allow_shrink)
                cmd_report(out)
    elif a.command == "preview":
        for n in a.batches:
            cmd_preview(n, a.out)
    elif a.command == "pilot-report":
        for n in a.batches:
            res = write_pilot_report(batch_output_dir(BATCHES[n]), n)
            print(f"Pilot report rebuilt: {res['records']} records, {len(res['problems'])} gate findings")
    elif a.command == "cumulative":
        build_cumulative(a.out, allow_shrink=a.allow_shrink)
    elif a.command == "report":
        cmd_report(a.out)
    elif a.command == "compare":
        cmd_compare(a.out, a.legacy)
    elif a.command == "recovery":
        for n in ("batch_1", "batch_2"):
            run_batch(n, a.out, allow_shrink=a.allow_shrink, require_committed_code=True)
        build_cumulative(a.out, allow_shrink=a.allow_shrink)
        cmd_compare(a.out, a.legacy)
        cmd_report(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
