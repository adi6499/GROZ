#!/usr/bin/env python3
"""Lighter flipbook pages: WebP copies of the rendered page PNGs, plus small filmstrip thumbnails.

For every site/assets/flipbook/<catalogue>/page-NN.png this writes
    site/assets/flipbook/<catalogue>/page-NN.webp          (same size, for the book)
    site/assets/flipbook/<catalogue>/thumbs/page-NN.webp   (96 px wide, for the filmstrip)
The PNGs stay where they are (they are the renders from the PDFs); the website loads the WebP files,
and the PNGs are left out of the Vercel deployment (.vercelignore).

Existing WebP files are kept unless the PNG is newer, or --force is given.

Usage:
    python tools/build_flipbook_webp.py            # all catalogues
    python tools/build_flipbook_webp.py --force    # rebuild every WebP
"""

import glob
import os
import sys

from PIL import Image

FLIPBOOK = "site/assets/flipbook"
PAGE_QUALITY = 80
THUMB_WIDTH = 96
THUMB_QUALITY = 70


def stale(src, dst, force):
    return force or not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src)


def build(force=False):
    total_png = total_webp = written = 0
    for folder in sorted(glob.glob(f"{FLIPBOOK}/*/")):
        pngs = sorted(glob.glob(os.path.join(folder, "page-*.png")))
        if not pngs:
            continue
        thumbs = os.path.join(folder, "thumbs")
        os.makedirs(thumbs, exist_ok=True)
        for png in pngs:
            name = os.path.splitext(os.path.basename(png))[0]
            page = os.path.join(folder, f"{name}.webp")
            thumb = os.path.join(thumbs, f"{name}.webp")
            if stale(png, page, force) or stale(png, thumb, force):
                with Image.open(png) as im:
                    im = im.convert("RGB")
                    im.save(page, "WEBP", quality=PAGE_QUALITY, method=6)
                    h = round(im.height * THUMB_WIDTH / im.width)
                    im.resize((THUMB_WIDTH, h), Image.LANCZOS).save(thumb, "WEBP", quality=THUMB_QUALITY, method=6)
                written += 1
            total_png += os.path.getsize(png)
            total_webp += os.path.getsize(page) + os.path.getsize(thumb)
        print(f"  {folder}: {len(pngs)} pages")
    print(f"Wrote {written} pages. PNG {total_png / 1e6:.1f} MB -> WebP pages + thumbnails {total_webp / 1e6:.1f} MB")


if __name__ == "__main__":
    build(force="--force" in sys.argv)
