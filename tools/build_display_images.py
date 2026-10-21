#!/usr/bin/env python3
"""Clear product pictures for the website: smooth WebP copies of every catalogue picture the site shows.

Most pictures are printed small in the catalogue PDFs (often 250-450 px wide; LED/695's is 259 x 182).
The extraction renders them at 200 DPI, and the renderer enlarges each real pixel into a block of about
3 x 3 (nearest neighbour), so on screen the pictures looked torn. This tool takes each picture back to
its real pixels (a box filter averages each block back into the pixel it came from), then enlarges it
smoothly. It writes
    site/img/full/<name>.webp    at most 1200 px on the longest side (product details, quote, flipbook)
    site/img/thumb/<name>.webp   at most 480 px (product cards, table rows, lists)
    site/img/manifest.json       how each picture was enlarged ("ai", "smooth" or "resized")
Two ways to enlarge:
  - smooth (default): Lanczos with a light unsharp mask. Nothing is invented.
  - ai (--ai EXE, approved by the owner on 21 Oct 2026): Real-ESRGAN (realesrgan-ncnn-vulkan, model
    realesr-animevideov3 at 2x/3x/4x, official build from github.com/xinntao/Real-ESRGAN, not part of
    this project). Much crisper, but it fills in fine detail: small printed text or logos can differ
    slightly from the catalogue. The site says so beside the picture (catalogue_export reads the
    manifest). realesrgan-x4plus is a little crisper but ~23x slower on this laptop's Intel Iris Xe
    (115 s vs 5 s for 6 pictures), so the video model is used.
The AI is used for pictures under AI_MAX_SIDE (800 px), most of them, at the smallest scale that
reaches about AI_TARGET; larger ones are enlarged smoothly. Pictures already large enough are only
resized. The dataset pictures (output_v2/images/*.png) are only
read: they stay the evidence of the extraction. build_site_data.py points the website at these copies
(a test checks that every one exists).

Usage (from the project root):
    python tools/build_display_images.py                   # new pictures, or whose PNG is newer
    python tools/build_display_images.py --ai <path to realesrgan-ncnn-vulkan.exe>   # AI for enlarged ones
    python tools/build_display_images.py --force           # rebuild every picture
"""

import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pymupdf
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.extractor.image_extractor import pdf_slug  # noqa: E402
from backend.site.catalogue_export import DATASET, EVIDENCE_LABELS, PREVIEW_DATASETS  # noqa: E402

OUT = os.path.join("site", "img")
RENDER_DPI = 200  # ImageExtractor's dpi: rendered pixels per point = 200 / 72
FULL_MAX, FULL_MIN, THUMB_MAX = 1200, 720, 480
FULL_QUALITY, THUMB_QUALITY = 84, 80
MANIFEST = os.path.join(OUT, "manifest.json")
AI_MODEL = "realesr-animevideov3"  # has 2x, 3x and 4x versions
AI_MAX_SIDE = 800  # AI only for pictures smaller than this; larger ones are enlarged smoothly
AI_TARGET = 1100  # the scale chosen is the smallest that reaches this, at most 4x


def ai_scale(real: Image.Image) -> int:
    return next((s for s in (2, 3) if max(real.size) * s >= AI_TARGET), 4)
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


def real_pixels(png_path: str, factor: float) -> Image.Image:
    """The picture at the resolution printed in the PDF: blocks of factor x factor averaged back into
    the pixel each came from (a PNG not enlarged by the render is returned as it is)."""
    img = Image.open(png_path)
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA") or "transparency" in img.info else "RGB")
    if factor > 1.15:
        img = img.resize((max(1, round(img.width / factor)), max(1, round(img.height / factor))), Image.BOX)
    return img


def resized(img: Image.Image, longest: int, sharpen: bool = False) -> Image.Image:
    scale = longest / max(img.size)
    if abs(scale - 1) < 0.01:
        return img
    out = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    return out.filter(ImageFilter.UnsharpMask(radius=max(1.0, scale * 0.45), percent=60, threshold=2)) if sharpen and scale > 1 else out


def smooth(real: Image.Image) -> Image.Image:
    """Enlarged 3.5x (between FULL_MIN and FULL_MAX on the longest side), Lanczos + unsharp mask."""
    return resized(real, min(FULL_MAX, max(FULL_MIN, round(max(real.size) * 3.5))), sharpen=True)


def on_white(img: Image.Image) -> Image.Image:
    """Transparent parts over white, as the site shows them (its picture tiles multiply onto light grey)."""
    if img.mode != "RGBA":
        return img
    bg = Image.new("RGB", img.size, "white")
    bg.paste(img, mask=img.getchannel("A"))
    return bg


def ai_enlarge(reals, exe: str, log=print):
    """{stem: enlarged picture} from Real-ESRGAN, run once per scale over a folder of real-pixel pictures."""
    out = {}
    by_scale = {}
    for stem, real in reals.items():
        by_scale.setdefault(ai_scale(real), {})[stem] = real
    for scale, group in sorted(by_scale.items()):
        work = tempfile.mkdtemp(prefix="groz_ai_")
        try:
            src, dst = os.path.join(work, "in"), os.path.join(work, "out")
            os.makedirs(src)
            os.makedirs(dst)
            for stem, real in group.items():
                on_white(real).save(os.path.join(src, stem + ".png"))
            log(f"Real-ESRGAN ({AI_MODEL}, {scale}x) on {len(group)} pictures...")
            subprocess.run([exe, "-i", src, "-o", dst, "-n", AI_MODEL, "-s", str(scale), "-f", "png"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=os.path.dirname(os.path.abspath(exe)))
            for stem in group:
                path = os.path.join(dst, stem + ".png")
                if os.path.exists(path):
                    with Image.open(path) as im:
                        out[stem] = im.convert("RGB")
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return out


def thumb_of(img: Image.Image) -> Image.Image:
    if max(img.size) <= THUMB_MAX:
        return img
    scale = THUMB_MAX / max(img.size)
    t = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    return t.filter(ImageFilter.UnsharpMask(radius=0.8, percent=35, threshold=2))


def load_manifest():
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def build(force: bool = False, ai: str = None, log=print) -> int:
    pictures = shown_pictures()
    manifest = load_manifest()
    natives = Natives()
    todo = {}  # stem -> (png, real pixels, method)
    try:
        for png in pictures:
            full, thumb = display_paths(png)
            stem = os.path.splitext(os.path.basename(png))[0]
            real = real_pixels(png, natives.factor(png))
            small = max(real.size) < AI_MAX_SIDE
            method = ("ai" if ai and small else "smooth") if max(real.size) < FULL_MAX * 0.9 else "resized"
            fresh = all(os.path.exists(p) and os.path.getmtime(p) >= os.path.getmtime(png) for p in (full, thumb))
            if force or not fresh or manifest.get(stem) != method:
                todo[stem] = (png, real, method)
    finally:
        natives.close()
    enlarged = ai_enlarge({s: r for s, (_, r, m) in todo.items() if m == "ai"}, ai, log) if ai else {}
    os.makedirs(os.path.join(OUT, "full"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "thumb"), exist_ok=True)
    for stem, (png, real, method) in todo.items():
        if method == "ai" and stem not in enlarged:
            method = "smooth"  # Real-ESRGAN gave nothing back for this one
        if method == "ai":
            img = enlarged[stem]
            img = resized(img, min(FULL_MAX, max(FULL_MIN, max(img.size))))
        elif method == "smooth":
            img = smooth(real)
        else:
            img = resized(real, min(FULL_MAX, max(real.size)))
        full, thumb = display_paths(png)
        img.save(full, "WEBP", quality=FULL_QUALITY, method=6)
        thumb_of(img).save(thumb, "WEBP", quality=THUMB_QUALITY, method=6)
        manifest[stem] = method
    shown = {os.path.splitext(os.path.basename(p))[0] for p in pictures}
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump({k: v for k, v in sorted(manifest.items()) if k in shown}, f, indent=0)
    counts = {m: sum(1 for k in shown if manifest.get(k) == m) for m in ("ai", "smooth", "resized")}
    log(f"{len(pictures)} pictures shown on the site; {len(todo)} built into {OUT}/full and {OUT}/thumb; {counts}")
    return len(todo)


if __name__ == "__main__":
    exe = sys.argv[sys.argv.index("--ai") + 1] if "--ai" in sys.argv else None
    if exe and not os.path.isfile(exe):
        sys.exit(f"--ai: {exe} not found")
    build(force="--force" in sys.argv, ai=exe)
