"""Batch 1 runner: tools_storage.pdf + GROZ_LIGHTING_GL-10_1.pdf (all pages).

Safe to run on its own: writes only output_v2/batches/batch_1.json, then rebuilds the cumulative
dataset from all batch files (other batches are kept) and regenerates the computed reports.
Never writes to the legacy output/ folder. Equivalent to: python run_extraction.py batch batch_1

The original runner (which overwrote output/extracted_products.json and deleted Batch 2) is in git
history at commit 012245d.
"""

import sys

from run_extraction import main

if __name__ == "__main__":
    sys.exit(main(["batch", "batch_1", *sys.argv[1:]]))
