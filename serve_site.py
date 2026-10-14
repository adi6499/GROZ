"""Serve the catalogue website locally (this computer only).

  python serve_site.py            -> http://127.0.0.1:8962/site/
  python serve_site.py --port 8000

Serves the project folder read-only on 127.0.0.1, so the site can load site/data/catalogue.json, the
image crops in output_v2/images/ and the source catalogue PDFs. It never binds to a network address.
Build the data first with `python build_site_data.py` (re-run after output_v2 changes).
"""

import argparse
import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".mjs": "text/javascript", ".js": "text/javascript", ".json": "application/json",
                      ".css": "text/css", ".svg": "image/svg+xml"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8962)
    args = ap.parse_args()
    if not os.path.exists(os.path.join(ROOT, "site", "data", "catalogue.json")):
        print("site/data/catalogue.json is missing: run `python build_site_data.py` first.", file=sys.stderr)
        return 1
    handler = functools.partial(Handler, directory=ROOT)
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"GROZ catalogue (local only): http://127.0.0.1:{args.port}/site/  — press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
