"""Verification decisions made by a person, kept apart from the extraction output.

A reviewer compares a product's extracted values with its printed catalogue page and either marks it
verified or flags a problem. A decision is stored in `review/verifications.json` (the current
decision per product) and appended to `review/verifications_log.jsonl` (every action, never
rewritten). `output_v2` is never modified: extraction stays machine output and verification stays a
human record.

Every decision carries a fingerprint of the values the reviewer saw. If a later extraction changes any
of them, the decision no longer applies ("stale") and the product is back to "to check". A product is
shown as verified only while its current values match the verified fingerprint.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

LEDGER = os.path.join("review", "verifications.json")
LOG = os.path.join("review", "verifications_log.jsonl")
STATUSES = ("verified", "flagged")
SHOWN_IMAGE_TYPES = ("direct_product", "product_family")
MAX_REVIEWER, MAX_COMMENT, MAX_FIELDS = 80, 2000, 30


class DecisionError(ValueError):
    """A decision that cannot be recorded (bad input or values changed since they were shown)."""


def reviewed_values(r: Dict[str, Any]) -> Dict[str, Any]:
    """The values a reviewer checks against the page (and that the website shows)."""
    image = next(({"file": im.get("file_path"), "association": im.get("association_type")}
                  for im in r.get("images") or [] if im.get("association_type") in SHOWN_IMAGE_TYPES), None)
    return {
        "cat_nr": r.get("cat_nr"),
        "ord_nr": r.get("ord_nr"),
        "sub_title": r.get("sub_title"),
        "dimensions_inch": r.get("dimensions_inch"),
        "dimensions_mm": r.get("dimensions_mm"),
        "box_qty": r.get("box_qty"),
        "specifications": {k: v for k, v in sorted((r.get("specifications") or {}).items()) if v not in (None, "")},
        "image": image,
    }


def fingerprint(r: Dict[str, Any]) -> str:
    blob = json.dumps(reviewed_values(r), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def empty_ledger() -> Dict[str, Any]:
    return {"version": 1, "decisions": {}}


def load_ledger(path: str = LEDGER) -> Dict[str, Any]:
    if not os.path.exists(path):
        return empty_ledger()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("decisions"), dict):
        raise ValueError(f"{path} is not a verification ledger")
    return data


def save_ledger(ledger: Dict[str, Any], path: str = LEDGER) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ordered = {"version": ledger.get("version", 1), "decisions": dict(sorted(ledger["decisions"].items()))}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def append_log(entry: Dict[str, Any], path: str = LOG) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def record_decision(ledger: Dict[str, Any], key: str, r: Dict[str, Any], status: str, reviewer: str,
                    shown_fingerprint: str, comment: str = "", fields: Iterable[str] = (),
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """Validate and store a decision for the product `key`; returns the stored entry."""
    if status not in STATUSES:
        raise DecisionError(f"status must be one of {', '.join(STATUSES)}")
    reviewer = " ".join(str(reviewer or "").split())
    if not reviewer:
        raise DecisionError("Enter your name: every decision records who made it.")
    if len(reviewer) > MAX_REVIEWER:
        raise DecisionError("The reviewer name is too long.")
    comment = str(comment or "").strip()
    if len(comment) > MAX_COMMENT:
        raise DecisionError("The comment is too long.")
    fields = [" ".join(str(f).split()) for f in fields if str(f).strip()]
    if len(fields) > MAX_FIELDS:
        raise DecisionError("Too many fields selected.")
    if status == "flagged" and not comment:
        raise DecisionError("Describe the problem: a flag needs a comment.")
    current = fingerprint(r)
    if shown_fingerprint != current:
        raise DecisionError("The product's values changed since this page was loaded. Reload and check again.")
    entry = {
        "status": status, "reviewer": reviewer, "at": now_iso(now), "fingerprint": current,
        "comment": comment, "fields": fields if status == "flagged" else [],
        "cat_nr": r.get("cat_nr"), "ord_nr": r.get("ord_nr"),
        "source_pdf": r.get("source_pdf"), "page": r.get("physical_page_number"),
    }
    ledger["decisions"][key] = entry
    return entry


def undo_decision(ledger: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    return ledger["decisions"].pop(key, None)


def state_for(ledger: Dict[str, Any], key: str, r: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """(state, entry): state is 'verified', 'flagged', 'stale' (values changed since) or None."""
    entry = ledger["decisions"].get(key)
    if not entry:
        return None, None
    if entry.get("fingerprint") != fingerprint(r):
        return "stale", entry
    return entry.get("status"), entry


def summary(ledger: Dict[str, Any], records: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, int]:
    counts = {"verified": 0, "flagged": 0, "stale": 0, "to_check": 0}
    for key, r in records:
        state, _ = state_for(ledger, key, r)
        counts[state if state in counts else "to_check"] += 1
    return counts
