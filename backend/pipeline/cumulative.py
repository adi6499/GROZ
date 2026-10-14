"""Build the cumulative dataset from per-batch files.

The cumulative file is a pure function of the batch files present in `<out>/batches/`. It is never
the input of a batch run, so running one batch cannot delete another. The build refuses to:
- drop a batch that the previous cumulative file contained, or shrink its record count;
- include the same catalogue page from two different batches (double extraction).
Both refusals can be overridden with allow_shrink=True when the change is intended.
"""

import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List

from .batches import BATCHES, BATCH_ORDER
from .runner import UnsafeOutputError, _same_path, guard_output_dir, write_json_atomic

CUMULATIVE_NAME = "extracted_products.json"


def load_batches(out_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    folder = os.path.join(out_dir, "batches")
    names = [f[:-5] for f in os.listdir(folder) if f.endswith(".json") and not f.endswith(".manifest.json")] \
        if os.path.isdir(folder) else []
    ordered = [n for n in BATCH_ORDER if n in names] + sorted(n for n in names if n not in BATCH_ORDER)
    out = {}
    for n in ordered:
        with open(os.path.join(folder, f"{n}.json"), encoding="utf-8") as f:
            out[n] = json.load(f)
    return out


def build_cumulative(out_dir: str, allow_shrink: bool = False, log=print) -> List[Dict[str, Any]]:
    guard_output_dir(out_dir)
    batches = load_batches(out_dir)
    if not batches:
        raise FileNotFoundError(f"No batch files in {os.path.join(out_dir, 'batches')}")
    reserved = {b.name: b.output_dir for b in BATCHES.values() if b.output_dir}
    foreign = [n for n in batches if n in BATCHES and (
        (BATCHES[n].output_dir and not _same_path(BATCHES[n].output_dir, out_dir))   # e.g. the pilot outside its folder
        or (not BATCHES[n].output_dir and any(_same_path(d, out_dir) for d in reserved.values())))]
    if foreign:
        raise UnsafeOutputError(
            f"Batch file(s) {', '.join(foreign)} belong to another output folder and cannot be merged into {out_dir}."
        )

    page_owner: Dict[tuple, str] = {}
    clashes = defaultdict(set)
    for name, recs in batches.items():
        for r in recs:
            key = (r["source_pdf"], r["physical_page_number"])
            if page_owner.setdefault(key, name) != name:
                clashes[key].update({page_owner[key], name})
    if clashes and not allow_shrink:
        sample = ", ".join(f"{k[0]} p{k[1]} ({'/'.join(sorted(v))})" for k, v in list(clashes.items())[:5])
        raise UnsafeOutputError(f"Same page extracted by more than one batch: {sample}")

    counts = {n: len(r) for n, r in batches.items()}
    path = os.path.join(out_dir, CUMULATIVE_NAME)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            previous = Counter(r.get("extraction_batch") for r in json.load(f))
        problems = [f"{b}: {n} -> {counts.get(b, 0)}" for b, n in previous.items() if counts.get(b, 0) < n]
        if problems and not allow_shrink:
            raise UnsafeOutputError(
                "Cumulative build would remove records (" + "; ".join(problems) + "). Existing file kept."
            )

    records = [r for recs in batches.values() for r in recs]
    write_json_atomic(path, records)
    write_json_atomic(os.path.join(out_dir, "extracted_products.manifest.json"), {
        "batches": counts,
        "record_count": len(records),
    })
    log("Cumulative: " + ", ".join(f"{n}={c}" for n, c in counts.items()) + f" -> {len(records)} records in {path}")
    return records
