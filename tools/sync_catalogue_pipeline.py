#!/usr/bin/env python3
"""Automated GROZ Catalogue Synchronization Pipeline.

Automatically detects product PDFs in the repository, extracts product records,
renders flipbook page spreads, normalizes CSV/JSON datasets, and updates the website.

Usage:
    python3 tools/sync_catalogue_pipeline.py         # Run full synchronization
    python3 tools/sync_catalogue_pipeline.py --watch # Watch for new/modified PDFs and sync automatically
"""

import os
import sys
import time
import glob
import json
import hashlib
import subprocess
from datetime import datetime

CATALOGUE_JSON = "site/data/catalogue.json"
CATALOGUE_CSV = "site/data/catalogue.csv"
FLIPBOOK_ASSETS = "site/assets/flipbook"

def get_pdf_manifest():
    manifest = {}
    for pdf in glob.glob("*.pdf"):
        size = os.path.getsize(pdf)
        mtime = os.path.getmtime(pdf)
        manifest[pdf] = {"size": size, "mtime": mtime}
    return manifest

def render_flipbook_spreads(pdf_path, out_dir, dpi=100):
    os.makedirs(out_dir, exist_ok=True)
    existing_pngs = glob.glob(f"{out_dir}/page-*.png")
    if existing_pngs:
        return len(existing_pngs)
    print(f"Rendering flipbook spreads for {pdf_path} at {dpi} DPI...")
    cmd = ["pdftoppm", "-png", "-r", str(dpi), pdf_path, f"{out_dir}/page"]
    subprocess.run(cmd, check=True)
    return len(glob.glob(f"{out_dir}/page-*.png"))

def sync():
    print("=" * 60)
    print("GROZ AUTOMATED CATALOGUE SYNC PIPELINE")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. Ensure all catalogues have flipbook page spreads
    catalogue_folders = {
        "GROZ_LIGHTING_GL-10_1.pdf": "site/assets/flipbook/lighting",
        "tools_storage.pdf": "site/assets/flipbook/storage",
        "Estwing_Hammer_E-03_Interactive_1.pdf": "site/assets/flipbook/estwing",
        "Precision_Catalogue_CA_03.pdf": "site/assets/flipbook/precision",
        "groz-lubrication-equipments.pdf": "site/assets/flipbook/lubrication",
    }

    for pdf, folder in catalogue_folders.items():
        if os.path.exists(pdf):
            pages = render_flipbook_spreads(pdf, folder)
            print(f"✓ {pdf}: {pages} pages available in {folder}")

    # 2. Extract product details from lubrication & fluid handling catalogues
    if os.path.exists("groz-lubrication-equipments.pdf"):
        print("\nExtracting product tables and specifications from groz-lubrication-equipments.pdf...")
        subprocess.run([sys.executable, "tools/extract_lubrication_products.py"], check=True)

    # 3. Merge and normalize datasets into site/data/catalogue.json and site/data/catalogue.csv
    print("\nNormalizing dataset and updating catalogue.json & catalogue.csv...")
    subprocess.run([sys.executable, "tools/merge_catalogue_data.py"], check=True)

    # 4. Run test suite to verify integrity
    print("\nRunning test suite...")
    res = subprocess.run(["node", "--test", "site/tests/core.test.mjs", "site/tests/flipbook.test.mjs"], capture_output=True, text=True)
    print(res.stdout)
    if res.returncode == 0:
        print("✓ All synchronization checks passed successfully.")
    else:
        print("✗ Test failures detected:\n", res.stderr)

    return res.returncode == 0

def watch():
    print("Watching repository for new or modified PDF catalogues (Ctrl+C to stop)...")
    last_manifest = get_pdf_manifest()
    while True:
        time.sleep(3)
        current_manifest = get_pdf_manifest()
        if current_manifest != last_manifest:
            print("\nDetected PDF catalogue changes! Starting synchronization...")
            sync()
            last_manifest = current_manifest

if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        success = sync()
        sys.exit(0 if success else 1)
