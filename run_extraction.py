"""GROZ extraction command line. Run from the project root.

  python run_extraction.py list                       show batches and their status
  python run_extraction.py batch batch_1              extract one batch, rebuild cumulative, regenerate reports
  python run_extraction.py cumulative                 rebuild <out>/extracted_products.json from batch files
  python run_extraction.py report                     coverage gates + summary.md + review.html
  python run_extraction.py compare                    change report vs the legacy 813-record dataset
  python run_extraction.py recovery                   batch_1 + batch_2 + cumulative + compare + report

Options: --out DIR (default output_v2; the legacy output/ folder is refused), --allow-shrink,
--allow-unapproved (needed for batches not yet approved, e.g. batch_3_pilot).
"""

import argparse
import json
import os
import sys

from backend.pipeline.batches import BATCHES, BATCH_ORDER
from backend.pipeline.cumulative import CUMULATIVE_NAME, build_cumulative
from backend.pipeline.runner import DEFAULT_OUTPUT_DIR, guard_output_dir, run_batch
from backend.reports.change_report import write_change_report
from backend.reports.summary import load_manifests, pages_by_pdf, write_review_html, write_summary_md
from backend.validator.coverage import coverage_problems, coverage_report

LEGACY_DATASET = os.path.join("output", "extracted_products.json")


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
    _, _, _, problems = _coverage(out)
    res = write_change_report(out, legacy, os.path.join(out, CUMULATIVE_NAME), coverage_problems=problems)
    print(f"Change report: {out}/reports/change_report.md (+ .csv): {res['pairs']} matched, "
          f"{len(res['added'])} added, {len(res['missing'])} missing, {len(res['rows'])} change rows")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["list", "batch", "cumulative", "report", "compare", "recovery"])
    ap.add_argument("batches", nargs="*")
    ap.add_argument("--out", default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--legacy", default=LEGACY_DATASET)
    ap.add_argument("--allow-shrink", action="store_true")
    ap.add_argument("--allow-unapproved", action="store_true")
    a = ap.parse_args(argv)
    guard_output_dir(a.out)

    if a.command == "list":
        for n in BATCH_ORDER:
            b = BATCHES[n]
            print(f"{n:15} {'approved' if b.approved else 'NOT APPROVED'}  {b.description}")
        return 0
    if a.command == "batch":
        if not a.batches:
            ap.error("name at least one batch, e.g. batch_1")
        for n in a.batches:
            run_batch(n, a.out, allow_unapproved=a.allow_unapproved, allow_shrink=a.allow_shrink)
        build_cumulative(a.out, allow_shrink=a.allow_shrink)
        cmd_report(a.out)
    elif a.command == "cumulative":
        build_cumulative(a.out, allow_shrink=a.allow_shrink)
    elif a.command == "report":
        cmd_report(a.out)
    elif a.command == "compare":
        cmd_compare(a.out, a.legacy)
    elif a.command == "recovery":
        for n in ("batch_1", "batch_2"):
            run_batch(n, a.out, allow_shrink=a.allow_shrink)
        build_cumulative(a.out, allow_shrink=a.allow_shrink)
        cmd_compare(a.out, a.legacy)
        cmd_report(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
