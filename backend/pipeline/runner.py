"""Safe batch runner.

Checks, all made before any page is read:
- the legacy `output/` folder is refused;
- a batch writes only to its own output folder: `output_v2/` for the main corrected dataset, or the
  batch's dedicated folder (the Hand Tool pilot writes only to `output_pilot_handtool/`);
- unapproved batches refuse to run (approval = setting `approved=True` in batches.py, in a commit);
- supplementary brochures can never produce product records;
- restricted catalogues (Batch 3: Hand Tool, Fluid Handling) only allow their listed pages;
- with require_committed_code, extraction code must be committed so the manifest's commit is exact.

On writing: a re-run that would produce fewer records than the existing batch file is refused
unless allow_shrink=True; the previous batch file is archived in `batches/history/`, never discarded.
"""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

from ..extractor.image_extractor import ImageExtractor
from ..extractor.product_builder import ProductBuilder
from ..validator.schema import ProductRecord
from .batches import BATCHES, RESTRICTED_SOURCES, SUPPLEMENTARY_SOURCES, Batch

PIPELINE_VERSION = "2.2.0"  # bump whenever extraction rules change (2.0.0 = recovery 4cf3417; 2.2.0 = decisions A, B, D, F)
LEGACY_OUTPUT_DIR = "output"
DEFAULT_OUTPUT_DIR = "output_v2"


class UnsafeOutputError(RuntimeError):
    """Raised when a run would overwrite protected data or break a safety rule."""


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def guard_output_dir(out_dir: str) -> None:
    if _same_path(out_dir, LEGACY_OUTPUT_DIR):
        raise UnsafeOutputError(
            f"Refusing to write into the legacy '{LEGACY_OUTPUT_DIR}/' folder; use e.g. '{DEFAULT_OUTPUT_DIR}/'."
        )


def batch_output_dir(batch: Batch) -> str:
    return batch.output_dir or DEFAULT_OUTPUT_DIR


def check_batch_output_dir(batch: Batch, out_dir: str) -> None:
    """A batch may only write to its own folder; no batch may write into another batch's dedicated folder."""
    guard_output_dir(out_dir)
    own = batch_output_dir(batch)
    if batch.output_dir and not _same_path(out_dir, own):
        raise UnsafeOutputError(f"Batch '{batch.name}' writes only to '{own}/', not '{out_dir}'.")
    for other in BATCHES.values():
        if other.output_dir and other.name != batch.name and _same_path(out_dir, other.output_dir):
            raise UnsafeOutputError(f"'{out_dir}' is reserved for batch '{other.name}'.")


def check_sources(batch: Batch) -> None:
    for src in batch.sources:
        if src.pdf in SUPPLEMENTARY_SOURCES:
            raise UnsafeOutputError(f"'{src.pdf}' is a supplementary source and cannot create product records.")
        if src.pdf in RESTRICTED_SOURCES:
            allowed = set(RESTRICTED_SOURCES[src.pdf])
            if src.pages is None or not set(src.pages) <= allowed:
                raise UnsafeOutputError(
                    f"'{src.pdf}' belongs to the unapproved Batch 3; only pages {sorted(allowed) or 'none'} may be processed."
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


def code_state() -> Tuple[str, bool]:
    """(git commit, extraction code has uncommitted changes)."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "backend", "run_extraction.py"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return head, bool(dirty)
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def code_version() -> str:
    head, dirty = code_state()
    return head + ("+dirty" if dirty else "")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def batch_path(out_dir: str, name: str) -> str:
    return os.path.join(out_dir, "batches", f"{name}.json")


def preflight(name: str, out_dir: Optional[str] = None, allow_unapproved: bool = False,
              require_committed_code: bool = False) -> Tuple[Batch, str]:
    """Every safety check of run_batch, without reading any page. Returns (batch, output dir)."""
    if name not in BATCHES:
        raise KeyError(f"Unknown batch '{name}'. Known: {', '.join(BATCHES)}")
    batch = BATCHES[name]
    out_dir = out_dir or batch_output_dir(batch)
    check_batch_output_dir(batch, out_dir)
    if not batch.approved and not allow_unapproved:
        raise PermissionError(f"Batch '{name}' is not approved to run yet ({batch.description}).")
    check_sources(batch)
    for src in batch.sources:
        if not os.path.isfile(src.pdf):
            raise FileNotFoundError(src.pdf)
    if require_committed_code and code_state()[1]:
        raise UnsafeOutputError("Commit the extraction code first, so the run is traceable to an exact commit.")
    return batch, out_dir


def run_batch(name: str, out_dir: Optional[str] = None, allow_unapproved: bool = False, allow_shrink: bool = False,
              require_committed_code: bool = False, log=print) -> List[ProductRecord]:
    batch, out_dir = preflight(name, out_dir, allow_unapproved, require_committed_code)

    builder = ProductBuilder(ImageExtractor(os.path.join(out_dir, "images")))
    records: List[ProductRecord] = []
    sources: Dict[str, Dict[str, Any]] = {}
    log(f"[{name}] {batch.description}")
    for src in batch.sources:
        with pymupdf.open(src.pdf) as doc:
            pages = list(src.pages) if src.pages else list(range(1, len(doc) + 1))
            sources[src.pdf] = {"sha256": sha256_file(src.pdf), "page_count": len(doc), "pages": pages}
            before = len(records)
            for pno in pages:
                for p in builder.process_page(doc[pno - 1], src.pdf, pno):
                    p.extraction_batch = name
                    records.append(p)
            log(f"  {src.pdf}: {len(pages)} pages -> {len(records) - before} records")

    path = batch_path(out_dir, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            previous = len(json.load(f))
        if len(records) < previous and not allow_shrink:
            raise UnsafeOutputError(
                f"Batch '{name}' produced {len(records)} records but {path} holds {previous}. "
                "Kept the existing file. Re-run with allow_shrink only if the reduction is intended."
            )
        # Keep the previous version: nothing is discarded, and the next report can diff against it.
        history = os.path.join(out_dir, "batches", "history")
        os.makedirs(history, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for suffix in (".json", ".manifest.json"):
            old = path.replace(".json", suffix)
            if os.path.exists(old):
                shutil.copy2(old, os.path.join(history, f"{name}.{stamp}{suffix}"))
    commit, dirty = code_state()
    write_json_atomic(path, [p.model_dump() for p in records])
    write_json_atomic(path.replace(".json", ".manifest.json"), {
        "batch": name,
        "description": batch.description,
        "approved": batch.approved,
        "output_dir": out_dir.replace("\\", "/"),
        "record_count": len(records),
        "records_per_pdf": dict(Counter(p.source_pdf for p in records)),
        "pages_processed": {pdf: s["pages"] for pdf, s in sources.items()},
        "source_pdfs": sources,
        "pipeline_version": PIPELINE_VERSION,
        "code_version": commit + ("+dirty" if dirty else ""),
        "python": platform.python_version(),
        "pymupdf": pymupdf.VersionBind,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    log(f"[{name}] {len(records)} records -> {path}")
    return records
