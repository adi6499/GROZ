"""Verification tool for the GROZ catalogue (this computer only).

  .venv/Scripts/python.exe verify_server.py           -> http://127.0.0.1:8963/verify/
  .venv/Scripts/python.exe verify_server.py --port 9000

A person compares each product's extracted values with its printed catalogue page (rendered from the
PDF, with the product's row highlighted) and marks it Verified or flags a problem. Decisions are saved
to review/verifications.json, and every action is appended to review/verifications_log.jsonl. Each
decision carries a fingerprint of the values that were checked: if a later extraction changes any of
them, the product goes back to "to check". output_v2 is never modified.

"Update catalogue site" (or `python build_site_data.py`) shows the decisions on the website: a
product reads "Verified" only while its values still match what the reviewer verified.
"""

import argparse
import collections
import functools
import http.server
import json
import os
import re
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8963
MAX_BODY = 64 * 1024


class ReviewStore:
    """The dataset, the decision ledger and page rendering, shared by all request threads."""

    def __init__(self, dataset: str, ledger_path: str, log_path: str, pdf_root: str = ".", can_publish: bool = True):
        import pymupdf  # noqa: F401  (fail early with a clear message if the venv is not used)
        from backend.review import verification
        from backend.site import catalogue_export as cx
        self.v, self.cx = verification, cx
        self.dataset, self.ledger_path, self.log_path, self.pdf_root = dataset, ledger_path, log_path, pdf_root
        # Only the project's own ledger may be published to the catalogue site (a test ledger never is).
        self.can_publish = can_publish
        self.lock = threading.RLock()          # ledger and dataset state
        self.render_lock = threading.Lock()    # PyMuPDF documents are not thread-safe
        self.docs: Dict[str, Any] = {}
        self.png_cache: "collections.OrderedDict[Tuple[str, str], bytes]" = collections.OrderedDict()
        self.ledger = verification.load_ledger(ledger_path)
        self._mtime = None
        self.records: Dict[str, Dict[str, Any]] = {}
        self.order: List[str] = []
        self.titles: Dict[str, Optional[Dict[str, Any]]] = {}
        self.reload_if_changed()

    # ------------------------------------------------------------------ data
    def reload_if_changed(self) -> None:
        mtime = os.path.getmtime(self.dataset)
        if mtime == self._mtime:
            return
        with open(self.dataset, encoding="utf-8") as f:
            records = json.load(f)
        reader = self.cx.TitleReader(self.pdf_root)
        try:
            titles = {self.cx.record_id(r): reader.title_for(r) for r in records}
        finally:
            reader.close()
        by_id = {self.cx.record_id(r): r for r in records}
        if len(by_id) != len(records):
            raise ValueError("record ids are not unique")
        with self.lock:
            self.records, self.order, self.titles = by_id, [self.cx.record_id(r) for r in records], titles
            self._mtime = mtime
            self.png_cache.clear()

    def view(self, rid: str) -> Dict[str, Any]:
        r = self.records[rid]
        cx = self.cx
        cat = cx.CATALOGUES.get(r["source_pdf"], {"category": "Other", "title": r["source_pdf"]})
        values = [
            {"key": "cat_nr", "label": "CAT NR", "value": r.get("cat_nr")},
            {"key": "ord_nr", "label": "ORD NR", "value": r.get("ord_nr")},
            {"key": "sub_title", "label": "Printed title", "value": r.get("sub_title")},
            {"key": "dimensions_inch", "label": "Size (inch)", "value": r.get("dimensions_inch")},
            {"key": "dimensions_mm", "label": "Size (mm)", "value": r.get("dimensions_mm")},
            {"key": "box_qty", "label": "Box quantity", "value": None if r.get("box_qty") is None else str(r["box_qty"])},
        ]
        specs = r.get("specifications") or {}
        for key in sorted(specs, key=lambda k: (cx.SPEC_ORDER.index(k) if k in cx.SPEC_ORDER else len(cx.SPEC_ORDER), k)):
            if specs[key] not in (None, ""):
                values.append({"key": f"specifications.{key}", "label": cx.spec_label(key), "value": str(specs[key])})
        image = cx._image(r)
        title = self.titles.get(rid)
        state, entry = self.v.state_for(self.ledger, rid, r)
        return {
            "id": rid, "cat_nr": r.get("cat_nr"), "ord_nr": r.get("ord_nr"), "title": r.get("sub_title"),
            "title_evidence": title["evidence"] if title else None,
            "category": cat.get("category"), "catalogue": cat.get("title"), "pdf": r["source_pdf"],
            "page": r["physical_page_number"], "printed_page": r.get("catalog_page_label"),
            "pdf_href": f"/{r['source_pdf']}#page={r['physical_page_number']}",
            "values": values,
            "image": {"src": "/" + image["src"].replace("../", "", 1), "label": image["evidence_label"],
                      "evidence": image["evidence_detail"]} if image else None,
            "image_unconfirmed": image is None and any(im.get("association_type") == "unresolved" for im in r.get("images") or []),
            "notes": [{"field": n.get("field_name"), "published_value": n.get("published_value"), "issue": n.get("suspected_issue")}
                      for n in r.get("editorial_notes") or []],
            "source_row_text": r.get("source_row_text"),
            "extraction_status": r.get("verification_status"),
            "fingerprint": self.v.fingerprint(r),
            "decision": None if not entry else {"state": state, **{k: entry.get(k) for k in ("status", "reviewer", "at", "comment", "fields")}},
        }

    def payload(self) -> Dict[str, Any]:
        self.reload_if_changed()
        with self.lock:
            views = [self.view(rid) for rid in self.order]
            counts = self.v.summary(self.ledger, [(rid, self.records[rid]) for rid in self.order])
            site_meta = self.site_meta()
        return {"records": views, "counts": counts, "total": len(views), "site": site_meta, "can_publish": self.can_publish}

    def site_meta(self) -> Dict[str, Any]:
        """How far the published site data is behind the ledger (decisions not yet on the website)."""
        try:
            with open(self.cx.SITE_DATA, encoding="utf-8") as f:
                products = json.load(f)["products"]
        except (OSError, ValueError, KeyError):
            return {"verified": None, "behind": None}
        site_verified = {p["id"] for p in products if p.get("status") == "verified"}
        ledger_verified = {rid for rid in self.order if self.v.state_for(self.ledger, rid, self.records[rid])[0] == "verified"}
        site_flagged = {p["id"] for p in products if (p.get("verification") or {}).get("state") == "flagged"}
        ledger_flagged = {rid for rid in self.order if self.v.state_for(self.ledger, rid, self.records[rid])[0] == "flagged"}
        return {"verified": len(site_verified), "behind": len(site_verified ^ ledger_verified) + len(site_flagged ^ ledger_flagged)}

    # ------------------------------------------------------------------ decisions
    def decide(self, body: Dict[str, Any]) -> Dict[str, Any]:
        rid = str(body.get("id", ""))
        with self.lock:
            r = self.records.get(rid)
            if r is None:
                raise self.v.DecisionError("Unknown product.")
            entry = self.v.record_decision(self.ledger, rid, r, str(body.get("status", "")), body.get("reviewer", ""),
                                           str(body.get("fingerprint", "")), body.get("comment", ""),
                                           body.get("fields") or [])
            self.v.save_ledger(self.ledger, self.ledger_path)
            self.v.append_log({"action": entry["status"], "id": rid, **entry}, self.log_path)
            return self.view(rid)

    def undo(self, body: Dict[str, Any]) -> Dict[str, Any]:
        rid = str(body.get("id", ""))
        reviewer = " ".join(str(body.get("reviewer", "")).split())
        with self.lock:
            if rid not in self.records:
                raise self.v.DecisionError("Unknown product.")
            if not reviewer:
                raise self.v.DecisionError("Enter your name: every action records who made it.")
            removed = self.v.undo_decision(self.ledger, rid)
            if removed is None:
                raise self.v.DecisionError("This product has no decision to undo.")
            self.v.save_ledger(self.ledger, self.ledger_path)
            self.v.append_log({"action": "undo", "id": rid, "reviewer": reviewer, "at": self.v.now_iso(),
                               "undid": {k: removed.get(k) for k in ("status", "reviewer", "at", "fingerprint")}}, self.log_path)
            return self.view(rid)

    def publish(self) -> Dict[str, Any]:
        if not self.can_publish:
            raise self.v.DecisionError("This server uses a separate (test) ledger, so it cannot update the catalogue site.")
        with self.lock:
            data = self.cx.build(ledger_path=self.ledger_path)
            self.cx.write(data)
            self.cx.write_title_review(data)
            m = data["meta"]
            return {"verified": m["verified"], "flagged": m["flagged_by_reviewer"], "stale": m["verification_stale"],
                    "records": m["records"]}

    # ------------------------------------------------------------------ page images
    def _doc(self, pdf: str):
        import pymupdf
        if pdf not in self.docs:
            self.docs[pdf] = pymupdf.open(os.path.join(self.pdf_root, pdf))
        return self.docs[pdf]

    VIEWS = ("row", "head", "table", "page")

    def geometry(self, rid: str, view: str) -> Dict[str, Any]:
        """The area to render and the boxes to highlight, in PDF points.

        row:   this product's printed row, across the table's printed width (the closest check).
        head:  the table's column headings, same width (shown above the row so columns line up).
        table: the whole ordering table with its caption. page: the whole page, table outlined.
        """
        import pymupdf
        r = self.records[rid]
        bb = r.get("bounding_box") or {}
        with self.render_lock:
            page = self._doc(r["source_pdf"])[r["physical_page_number"] - 1]
            pr = page.rect
            table = pymupdf.Rect(bb["x0"], bb["y0"], bb["x1"], bb["y1"]) if bb else pr
            words = page.get_text("words", clip=table + (-3, -3, 3, 3))
        norm = lambda t: re.sub(r"^[^0-9A-Za-z]+", "", t).rstrip(".,;:")
        cat, ord_ = r.get("cat_nr"), r.get("ord_nr")
        cat_hits = [w for w in words if cat and norm(w[4]) == cat]
        ord_hits = [w for w in words if ord_ and norm(w[4]) == ord_]
        # The printed extent of the table: where its words are (the stored box can span a half page).
        xs0 = min((w[0] for w in words), default=table.x0)
        xs1 = max((w[2] for w in words), default=table.x1)
        boxes, row = [], None
        if cat_hits:
            c = cat_hits[0]
            o = min(ord_hits, key=lambda w: abs((w[1] + w[3]) / 2 - (c[1] + c[3]) / 2)) if ord_hits else None
            if o is not None and abs((o[1] + o[3]) / 2 - (c[1] + c[3]) / 2) > 12:
                o = None  # not on the same printed row
            row = (min(c[1], o[1]) if o else c[1], max(c[3], o[3]) if o else c[3])
            boxes.append({"kind": "row", "rect": [xs0 - 3, row[0] - 2, xs1 + 3, row[1] + 2]})
            boxes.append({"kind": "cat", "rect": list(c[:4])})
            if o:
                boxes.append({"kind": "ord", "rect": list(o[:4])})
        elif ord_hits:
            boxes.append({"kind": "ord", "rect": list(ord_hits[0][:4])})
        # Column headings end where the first data row starts (its first five-digit order number).
        data_tops = [w[1] for w in words if re.fullmatch(r"\d{5}", norm(w[4]))]
        head_bottom = min(data_tops) - 1 if data_tops else None
        if view == "row" and row:
            clip = pymupdf.Rect(xs0 - 8, row[0] - 7, xs1 + 8, row[1] + 7)
        elif view == "head" and head_bottom and head_bottom - table.y0 > 4:
            clip = pymupdf.Rect(xs0 - 8, table.y0 - 2, xs1 + 8, head_bottom)
        elif view in ("row", "head"):
            return {"clip": None, "boxes": [], "row_found": bool(cat_hits)}  # nothing reliable to show
        elif view == "page":
            clip = pr
            boxes.insert(0, {"kind": "table", "rect": [table.x0, table.y0, table.x1, table.y1]})
        else:
            clip = pymupdf.Rect(xs0, table.y0, xs1, table.y1) + (-14, -30, 14, 12)
        clip = clip & pr
        if view == "head":
            boxes = []
        return {"clip": [clip.x0, clip.y0, clip.x1, clip.y1], "page_size": [pr.width, pr.height], "boxes": boxes,
                "row_found": bool(cat_hits)}

    def png(self, rid: str, view: str) -> bytes:
        import pymupdf
        key = (rid, view)
        with self.lock:
            cached = self.png_cache.get(key)
        if cached:
            return cached
        g = self.geometry(rid, view)
        if not g["clip"]:
            raise LookupError("This view is not available for this product.")
        r = self.records[rid]
        clip = pymupdf.Rect(*g["clip"])
        zoom = min(1.6, 1500 / clip.width) if view == "page" else min(4.0, 1600 / clip.width)
        with self.render_lock:
            page = self._doc(r["source_pdf"])[r["physical_page_number"] - 1]
            data = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False).tobytes("png")
        with self.lock:
            self.png_cache[key] = data
            while len(self.png_cache) > 160:
                self.png_cache.popitem(last=False)
        return data


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".mjs": "text/javascript", ".js": "text/javascript", ".json": "application/json",
                      ".css": "text/css", ".svg": "image/svg+xml"}
    store: ReviewStore = None  # set by make_server
    port: int = DEFAULT_PORT

    def end_headers(self):
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):  # keep the console readable: API calls and errors only
        msg = fmt % args if args else fmt
        if "/api/" in msg or msg.startswith("code ") or re.search(r'" [45]\d\d ', msg):
            super().log_message(fmt, *args)

    def _json(self, code: int, obj: Any) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/review/"):
            return super().do_GET()
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/review/records":
                return self._json(200, self.store.payload())
            rid, view = q.get("id", ""), q.get("view", "table")
            if rid not in self.store.records or view not in ReviewStore.VIEWS:
                return self._json(400, {"error": "Unknown product or view."})
            if u.path == "/api/review/geometry":
                return self._json(200, self.store.geometry(rid, view))
            if u.path == "/api/review/page.png":
                data = self.store.png(rid, view)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return None
            return self._json(404, {"error": "Not found."})
        except Exception as e:  # report, never crash the server
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/review/"):
            return self._json(404, {"error": "Not found."})
        # Only this page may change decisions: a custom header and a JSON body cannot be sent by another
        # website without a CORS preflight, which this server never approves.
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
        if self.headers.get("X-GROZ-Review") != "1" or (origin and origin not in allowed) \
                or not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._json(403, {"error": "Requests must come from the verification page."})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._json(413, {"error": "Request too large."})
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("expected a JSON object")
        except ValueError:
            return self._json(400, {"error": "Invalid JSON."})
        try:
            if u.path == "/api/review/decision":
                return self._json(200, {"record": self.store.decide(body), "site": self.store.site_meta()})
            if u.path == "/api/review/undo":
                return self._json(200, {"record": self.store.undo(body), "site": self.store.site_meta()})
            if u.path == "/api/review/publish":
                return self._json(200, {"site": self.store.publish()})
            return self._json(404, {"error": "Not found."})
        except self.store.v.DecisionError as e:
            return self._json(409 if "changed since" in str(e) else 400, {"error": str(e)})
        except Exception as e:
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def do_OPTIONS(self):  # no CORS: other origins are never allowed to call the API
        self.send_response(405)
        self.end_headers()


def make_server(port: int, store: ReviewStore) -> http.server.ThreadingHTTPServer:
    """Bind on 127.0.0.1 only (port 0 picks a free port)."""
    handler_cls = type("BoundHandler", (Handler,), {"store": store, "port": port})
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(handler_cls, directory=ROOT))
    handler_cls.port = httpd.server_address[1]
    return httpd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--ledger", help="decision file (default review/verifications.json); another file is a test ledger that cannot be published")
    ap.add_argument("--log", help="action log (default review/verifications_log.jsonl)")
    args = ap.parse_args()
    ledger_arg = os.path.abspath(args.ledger) if args.ledger else None
    log_arg = os.path.abspath(args.log) if args.log else None
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    try:
        from backend.review import verification
        from backend.site import catalogue_export
        ledger = ledger_arg or verification.LEDGER
        own = os.path.abspath(ledger) == os.path.abspath(verification.LEDGER)
        store = ReviewStore(catalogue_export.DATASET, ledger, log_arg or verification.LOG, can_publish=own)
    except ImportError as e:
        print(f"{e}. Run this with the project's Python: .venv/Scripts/python.exe verify_server.py", file=sys.stderr)
        return 1
    with make_server(args.port, store) as httpd:
        print(f"GROZ verification tool (local only): http://127.0.0.1:{args.port}/verify/  — press Ctrl+C to stop")
        if not own:
            print(f"Test ledger: {ledger} (the catalogue site cannot be updated from this server)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
