"""Safe batch runner.

- Writes only to its own output folder (default `output_v2/`); refuses the legacy `output/` folder.
- Each batch writes only `<out>/batches/<batch>.json` (+ a manifest); other batches are untouched.
- A re-run that would produce fewer records than the existing batch file is refused unless
  `allow_shrink=True`, so a regression can never silently delete records.
- Unapproved batches refuse to run unless `allow_unapproved=True`.
- Supplementary (brochure) sources can never produce product records.
"""

import json
import os
import platform
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

import pymupdf

from ..extractor.image_extractor import ImageExtractor
from ..extractor.product_builder import ProductBuilder
from ..validator.schema import ProductRecord
from .batches import BATCHES, SUPPLEMENTARY_SOURCES

LEGACY_OUTPUT_DIR = "output"
DEFAULT_OUTPUT_DIR = "output_v2"


class UnsafeOutputError(RuntimeError):
    """Raised when a run would overwrite protected data."""


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def guard_output_dir(out_dir: str) -> None:
    if _same_path(out_dir, LEGACY_OUTPUT_DIR):
        raise UnsafeOutputError(
            f"Refusing to write into the legacy '{LEGACY_OUTPUT_DIR}/' folder; use e.g. '{DEFAULT_OUTPUT_DIR}/'."
        )


def write_json_atomic(path: str, data: Any) -> None:
    """Write JSON to a temp file and rename it into place, so a crash never leaves a half file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def code_version() -> str:
    """Git commit of the extraction code, with '+dirty' if there are uncommitted changes."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "backend", "run_extraction.py"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def batch_path(out_dir: str, name: str) -> str:
    return os.path.join(out_dir, "batches", f"{name}.json")


def run_batch(name: str, out_dir: str = DEFAULT_OUTPUT_DIR, allow_unapproved: bool = False,
              allow_shrink: bool = False, log=print) -> List[ProductRecord]:
    if name not in BATCHES:
        raise KeyError(f"Unknown batch '{name}'. Known: {', '.join(BATCHES)}")
    batch = BATCHES[name]
    guard_output_dir(out_dir)
    if not batch.approved and not allow_unapproved:
        raise PermissionError(f"Batch '{name}' is not approved to run yet ({batch.description}).")
    for src in batch.sources:
        if src.pdf in SUPPLEMENTARY_SOURCES:
            raise UnsafeOutputError(f"'{src.pdf}' is a supplementary source and cannot create product records.")
        if not os.path.isfile(src.pdf):
            raise FileNotFoundError(src.pdf)

    builder = ProductBuilder(ImageExtractor(os.path.join(out_dir, "images")))
    records: List[ProductRecord] = []
    pages_processed: Dict[str, List[int]] = {}
    log(f"[{name}] {batch.description}")
    for src in batch.sources:
        with pymupdf.open(src.pdf) as doc:
            pages = list(src.pages) if src.pages else list(range(1, len(doc) + 1))
            pages_processed[src.pdf] = pages
            before = len(records)
            for pno in pages:
                for p in builder.process_page(doc[pno - 1], src.pdf, pno):
                    p.extraction_batch = name
                    records.append(p)
            log(f"  {src.pdf}: {len(pages)} pages -> {len(records) - before} records")

    path = batch_path(out_dir, name)
    if os.path.exists(path) and not allow_shrink:
        with open(path, encoding="utf-8") as f:
            previous = len(json.load(f))
        if len(records) < previous:
            raise UnsafeOutputError(
                f"Batch '{name}' produced {len(records)} records but {path} holds {previous}. "
                "Kept the existing file. Re-run with allow_shrink only if the reduction is intended."
            )
    write_json_atomic(path, [p.model_dump() for p in records])
    write_json_atomic(path.replace(".json", ".manifest.json"), {
        "batch": name,
        "description": batch.description,
        "record_count": len(records),
        "records_per_pdf": dict(Counter(p.source_pdf for p in records)),
        "pages_processed": pages_processed,
        "code_version": code_version(),
        "python": platform.python_version(),
        "pymupdf": pymupdf.VersionBind,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    log(f"[{name}] {len(records)} records -> {path}")
    return records
