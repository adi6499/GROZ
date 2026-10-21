#!/usr/bin/env python3
"""Lighter flipbook pages: WebP copies of the rendered page PNGs, small filmstrip thumbnails, and sharp
pages for the magnifying glass.

For every site/assets/flipbook/<catalogue>/page-NN.png this writes
    site/assets/flipbook/<catalogue>/page-NN.webp          (same size, for the book)
    site/assets/flipbook/<catalogue>/thumbs/page-NN.webp   (96 px wide, for the filmstrip)
    site/assets/flipbook/<catalogue>/hires/page-NN.webp    (page NN of the catalogue PDF rendered at
                                                            200 DPI, for the magnifying glass)
The PNGs stay where they are (they are the renders from the PDFs); the website loads the WebP files,
and the PNGs are left out of the Vercel deployment (.vercelignore). The sharp pages are loaded only for
a page someone looks at through the magnifier.
Catalogues in PDF_ONLY have no PNG renders: their pages, thumbnails and sharp pages are rendered
straight from the PDF with PyMuPDF (pages at PAGE_DPI, as the PNG renders were).

Existing WebP files are kept unless their source is newer, or --force is given.

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
HIRES_DPI = 200
PAGE_DPI = 100  # the PNG renders' resolution (pdftoppm -r 100, tools/sync_catalogue_pipeline.py)
HIRES_QUALITY = 66

# Each flipbook folder and the catalogue PDF its pages come from (as in site/assets/js/flipbook.mjs).
FOLDER_PDFS = {
    "lighting": "GROZ_LIGHTING_GL-10_1.pdf",
    "storage": "tools_storage.pdf",
    "estwing": "Estwing_Hammer_E-03_Interactive_1.pdf",
    "precision": "Precision_Catalogue_CA_03.pdf",
    "lubrication": "groz-lubrication-equipments.pdf",
    "fluid": "Fluid_Handling_Catalogue_spread.pdf",
    "fuel": "FUEL.pdf",
}
PDF_ONLY = ("fluid", "fuel")  # added 21 Oct 2026, when their products went live


def stale(src, dst, force):
    return force or not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src)


def build_hires(folder, pngs, force):
    """Page NN of the folder's PDF at HIRES_DPI, for the magnifier. Returns (written, bytes)."""
    pdf = FOLDER_PDFS.get(os.path.basename(os.path.normpath(folder)))
    if not pdf or not os.path.exists(pdf):
        print(f"  {folder}: no catalogue PDF found, no magnifier pages")
        return 0, 0
    try:
        import pymupdf
    except ImportError:
        sys.exit("The magnifier pages need PyMuPDF: run this with .venv/Scripts/python.exe")
    out = os.path.join(folder, "hires")
    os.makedirs(out, exist_ok=True)
    doc = pymupdf.open(pdf)
    if doc.page_count != len(pngs):
        sys.exit(f"{pdf} has {doc.page_count} pages but {folder} has {len(pngs)}: re-render the flipbook pages first")
    written = size = 0
    for i in range(doc.page_count):
        dst = os.path.join(out, f"page-{i + 1:02d}.webp")
        if stale(pdf, dst, force):
            pix = doc[i].get_pixmap(dpi=HIRES_DPI)
            Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(dst, "WEBP", quality=HIRES_QUALITY, method=6)
            written += 1
        size += os.path.getsize(dst)
    return written, size


def build_from_pdf(folder, force):
    """Pages, thumbnails and magnifier pages straight from the folder's PDF. Returns (pages, written, bytes)."""
    import pymupdf
    pdf = FOLDER_PDFS[os.path.basename(os.path.normpath(folder))]
    if not os.path.exists(pdf):
        return 0, 0, 0
    for sub in ("thumbs", "hires"):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
    doc = pymupdf.open(pdf)
    written = size = 0
    for i in range(doc.page_count):
        name = f"page-{i + 1:02d}.webp"
        page, thumb, hires = (os.path.join(folder, sub, name) for sub in ("", "thumbs", "hires"))
        if any(stale(pdf, p, force) for p in (page, thumb, hires)):
            pix = doc[i].get_pixmap(dpi=PAGE_DPI)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            im.save(page, "WEBP", quality=PAGE_QUALITY, method=6)
            im.resize((THUMB_WIDTH, round(im.height * THUMB_WIDTH / im.width)), Image.LANCZOS).save(
                thumb, "WEBP", quality=THUMB_QUALITY, method=6)
            pix = doc[i].get_pixmap(dpi=HIRES_DPI)
            Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(hires, "WEBP", quality=HIRES_QUALITY, method=6)
            written += 1
        size += sum(os.path.getsize(p) for p in (page, thumb, hires))
    return doc.page_count, written, size


def build(force=False):
    total_png = total_webp = total_hires = written = hires_written = 0
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
        n, size = build_hires(folder, pngs, force)
        hires_written += n
        total_hires += size
        print(f"  {folder}: {len(pngs)} pages")
    for name in PDF_ONLY:
        pages, n, size = build_from_pdf(os.path.join(FLIPBOOK, name), force)
        written += n
        hires_written += n
        print(f"  {FLIPBOOK}/{name}: {pages} pages from {FOLDER_PDFS[name]} ({size / 1e6:.1f} MB)")
    print(f"Wrote {written} pages and {hires_written} magnifier pages. PNG {total_png / 1e6:.1f} MB -> "
          f"WebP pages + thumbnails {total_webp / 1e6:.1f} MB, magnifier pages {total_hires / 1e6:.1f} MB")


if __name__ == "__main__":
    build(force="--force" in sys.argv)
