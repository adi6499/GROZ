#!/usr/bin/env python3
"""GROZ catalogue sync: flipbook page images and the website's product list export.

Renders flipbook page images for each catalogue PDF (when they are missing) and writes
site/data/catalogue.csv from site/data/catalogue.json.

It does NOT add products to the website. Products reach site/data/catalogue.json only through the
reviewed pipeline: run_extraction.py writes output_v2 (with its checks and change reports), and
build_site_data.py builds the site data from output_v2. A quick table scrape merged straight into
catalogue.json (tools/extract_lubrication_products.py + tools/merge_catalogue_data.py, Oct 2026)
published table labels as products, whole pages as product pictures and invented values, so that
path is no longer run from here. Those two scripts are kept for reference only.

Usage:
    python tools/sync_catalogue_pipeline.py          # render missing flipbook pages, export the CSV
    python tools/sync_catalogue_pipeline.py --csv    # only export the CSV
    python tools/sync_catalogue_pipeline.py --watch  # re-run when a catalogue PDF changes
"""

import csv
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime

CATALOGUE_JSON = "site/data/catalogue.json"
CATALOGUE_CSV = "site/data/catalogue.csv"

CATALOGUE_FOLDERS = {
    "GROZ_LIGHTING_GL-10_1.pdf": "site/assets/flipbook/lighting",
    "tools_storage.pdf": "site/assets/flipbook/storage",
    "Estwing_Hammer_E-03_Interactive_1.pdf": "site/assets/flipbook/estwing",
    "Precision_Catalogue_CA_03.pdf": "site/assets/flipbook/precision",
    "groz-lubrication-equipments.pdf": "site/assets/flipbook/lubrication",
}


def get_pdf_manifest():
    return {pdf: {"size": os.path.getsize(pdf), "mtime": os.path.getmtime(pdf)} for pdf in glob.glob("*.pdf")}


def render_flipbook_pages(pdf_path, out_dir, dpi=100):
    """Renders page-NN.png for a PDF with pdftoppm, unless the folder already has pages."""
    os.makedirs(out_dir, exist_ok=True)
    existing = glob.glob(f"{out_dir}/page-*.png")
    if existing:
        return len(existing)
    print(f"Rendering flipbook pages for {pdf_path} at {dpi} DPI...")
    subprocess.run(["pdftoppm", "-png", "-r", str(dpi), pdf_path, f"{out_dir}/page"], check=True)
    return len(glob.glob(f"{out_dir}/page-*.png"))


def export_site_csv():
    """site/data/catalogue.csv: one row per product on the website (read from catalogue.json)."""
    with open(CATALOGUE_JSON, encoding="utf-8") as f:
        products = json.load(f)["products"]
    with open(CATALOGUE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "cat_nr", "ord_nr", "title", "category", "brand", "catalogue_pdf", "page", "specs"])
        for p in products:
            specs = " | ".join(f"{s.get('label')}: {s.get('value')}" for s in p.get("specs", []))
            writer.writerow([p.get("id"), p.get("cat_nr"), p.get("ord_nr") or "", p.get("title") or p.get("heading") or "",
                             p.get("category"), p.get("brand"), p.get("catalogue", {}).get("pdf"), p.get("page"), specs])
    print(f"Wrote {CATALOGUE_CSV}: {len(products)} products")


def sync():
    print("=" * 60)
    print("GROZ CATALOGUE SYNC")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    for pdf, folder in CATALOGUE_FOLDERS.items():
        if os.path.exists(pdf):
            print(f"  {pdf}: {render_flipbook_pages(pdf, folder)} pages in {folder}")
    export_site_csv()
    print("\nRunning the website tests...")
    res = subprocess.run(["node", "--test", "site/tests/core.test.mjs", "site/tests/flipbook.test.mjs", "site/tests/deploy.test.mjs"],
                         capture_output=True, text=True)
    print(res.stdout)
    print("All checks passed." if res.returncode == 0 else f"Test failures:\n{res.stderr}")
    return res.returncode == 0


def watch():
    print("Watching for new or changed PDF catalogues (Ctrl+C to stop)...")
    last = get_pdf_manifest()
    while True:
        time.sleep(3)
        current = get_pdf_manifest()
        if current != last:
            print("\nCatalogue PDFs changed: syncing...")
            sync()
            last = current


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    elif "--csv" in sys.argv:
        export_site_csv()
    else:
        sys.exit(0 if sync() else 1)
