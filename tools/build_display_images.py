#!/usr/bin/env python3
"""Clear product pictures for the website: smooth WebP copies of every catalogue picture the site shows.

Most pictures are printed small in the catalogue PDFs (often 250-450 px wide; LED/695's is 259 x 182).
The extraction renders them at 200 DPI, and the renderer enlarges each real pixel into a block of about
3 x 3 (nearest neighbour), so on screen the pictures looked torn. This tool takes each picture back to
its real pixels (a box filter averages each block back into the pixel it came from), then enlarges it
smoothly (Lanczos) with a light unsharp mask. Nothing is invented: no detail is added that the catalogue
picture does not hold. It writes
    site/img/full/<name>.webp    at most 1200 px on the longest side (product details, quote, flipbook)
    site/img/thumb/<name>.webp   at most 480 px (product cards, table rows, lists)
The dataset pictures (output_v2/images/*.png) are only read: they stay the evidence of the extraction.
build_site_data.py points the website at these copies (a test checks that every one exists).

Usage (from the project root):
    python tools/build_display_images.py           # pictures not built yet, or whose PNG is newer
    python tools/build_display_images.py --force   # rebuild every picture
"""

import glob
import json
import math
import os
import re
import sys

import pymupdf
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.extractor.image_extractor import pdf_slug  # noqa: E402
from backend.site.catalogue_export import DATASET, EVIDENCE_LABELS, PREVIEW_DATASETS  # noqa: E402

OUT = os.path.join("site", "img")
RENDER_DPI = 200  # ImageExtractor's dpi: rendered pixels per point = 200 / 72
FULL_MAX, FULL_MIN, THUMB_MAX = 1200, 720, 480
FULL_QUALITY, THUMB_QUALITY = 84, 80
NAME = re.compile(r"(?P<slug>.+)_p(?P<page>\d+)_xref(?P<xref>\d+)_(?P<x>-?\d+)_(?P<y>-?\d+)$")


def display_paths(png_path: str):
    """(full, thumb) WebP paths of a dataset picture (relative to the project root)."""
    stem = os.path.splitext(os.path.basename(png_path))[0]
    return os.path.join(OUT, "full", stem + ".webp"), os.path.join(OUT, "thumb", stem + ".webp")


def shown_pictures():
    """Dataset PNG paths of the pictures the website shows (confirmed product or family pictures)."""
    found = set()
    for path, base in ((DATASET, "output_v2"), *PREVIEW_DATASETS):
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                for im in r.get("images") or []:
                    if im.get("association_type") in EVIDENCE_LABELS:
                        found.add(os.path.join(base, im["file_path"]))
                        break  # the site shows the first confirmed picture only
    return sorted(found)


class Natives:
    """How many rendered pixels each real pixel of a picture became (from the catalogue PDF)."""

    def __init__(self):
        self.pdfs = {pdf_slug(p): p for p in glob.glob("*.pdf")}
        self.docs = {}

    def factor(self, png_path: str) -> float:
        m = NAME.match(os.path.splitext(os.path.basename(png_path))[0])
        pdf = m and self.pdfs.get(m["slug"])
        if not pdf:
            return 1.0
        doc = self.docs.get(pdf) or self.docs.setdefault(pdf, pymupdf.open(pdf))
        try:
            native = doc.extract_image(int(m["xref"]))
            rects = doc[int(m["page"]) - 1].get_image_rects(int(m["xref"]))
        except Exception:
            return 1.0
        if not native or not rects:
            return 1.0
        x, y = int(m["x"]), int(m["y"])
        rect = min(rects, key=lambda r: abs(r.x0 - x) + abs(r.y0 - y))
        if rect.width <= 0 or rect.height <= 0:
            return 1.0
        per_point = math.sqrt(native["width"] * native["height"] / (rect.width * rect.height))
        return (RENDER_DPI / 72) / per_point

    def close(self):
        for d in self.docs.values():
            d.close()


def clear_picture(png_path: str, factor: float) -> Image.Image:
    img = Image.open(png_path)
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA") or "transparency" in img.info else "RGB")
    w, h = img.size
    if factor > 1.15:  # blocks of factor x factor: back to the real pixels, then enlarge smoothly
        real = img.resize((max(1, round(w / factor)), max(1, round(h / factor))), Image.BOX)
        longest = max(real.size)
        target = min(FULL_MAX, max(FULL_MIN, round(longest * 3.5)))
        scale = target / longest
        img = real.resize((max(1, round(real.width * scale)), max(1, round(real.height * scale))), Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=max(1.0, scale * 0.45), percent=60, threshold=2))
    elif max(w, h) > FULL_MAX:
        scale = FULL_MAX / max(w, h)
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    return img


def thumb_of(img: Image.Image) -> Image.Image:
    if max(img.size) <= THUMB_MAX:
        return img
    scale = THUMB_MAX / max(img.size)
    t = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    return t.filter(ImageFilter.UnsharpMask(radius=0.8, percent=35, threshold=2))


def build(force: bool = False, log=print) -> int:
    pictures = shown_pictures()
    natives = Natives()
    made = 0
    try:
        for png in pictures:
            full, thumb = display_paths(png)
            if not force and all(os.path.exists(p) and os.path.getmtime(p) >= os.path.getmtime(png) for p in (full, thumb)):
                continue
            img = clear_picture(png, natives.factor(png))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            os.makedirs(os.path.dirname(thumb), exist_ok=True)
            img.save(full, "WEBP", quality=FULL_QUALITY, method=6)
            thumb_of(img).save(thumb, "WEBP", quality=THUMB_QUALITY, method=6)
            made += 1
    finally:
        natives.close()
    log(f"{len(pictures)} pictures shown on the site; {made} built into {OUT}/full and {OUT}/thumb")
    return made


if __name__ == "__main__":
    build(force="--force" in sys.argv)
