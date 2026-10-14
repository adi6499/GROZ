"""Batch 2 runner: Estwing_Hammer_E-03_Interactive_1.pdf + Precision_Catalogue_CA_03.pdf (all pages).

Safe to run on its own: writes only output_v2/batches/batch_2.json, then rebuilds the cumulative
dataset from all batch files (other batches are kept) and regenerates the computed reports.
Never writes to the legacy output/ folder. Equivalent to: python run_extraction.py batch batch_2

The original runner (hard-coded summary numbers, rebuilt the cumulative file from itself) is in git
history at commit 012245d.
"""

import sys

from run_extraction import main

if __name__ == "__main__":
    sys.exit(main(["batch", "batch_2", *sys.argv[1:]]))
