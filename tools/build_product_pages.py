"""One plain web page per product, for Google and for links that show a preview (task 4, 24 Nov 2026).

  .venv/Scripts/python.exe tools/build_product_pages.py

Reads site/data/catalogue.json (built by build_site_data.py) and writes, from it only:

- site/p/<product id>.html  one page per product: its printed title, CAT NR, ORD NR, brand, category,
                            picture, the values printed in its ordering table, the catalogue page it
                            comes from, and a link that opens it in the catalogue. Each page carries
                            schema.org Product data (JSON-LD) with the same facts and nothing else:
                            no prices, offers or ratings, because the catalogues print none.
- site/p/index.html         every product as a plain list, by category (a page search engines can follow).
- site/sitemap.xml          the catalogue, the list and every product page, for search engines.
- site/data/parts/          the same catalogue data in parts of PART_SIZE products plus index.json (meta,
                            categories, catalogues, the part names). The catalogue page loads these right
                            after its first paint and reads each part in its own short step (a phone reads
                            one 4 MB file in one long stall). Joined in order they are catalogue.json's
                            products exactly (site/tests/pages.test.mjs).

Every value comes from the catalogue data; nothing is added. The folder site/p/ belongs to this
script: pages of products no longer in the data are removed. The addresses written into the pages
(canonical, sitemap, pictures for link previews) are on groz.tools, the public copy of the site.
"""

import html
import json
import os
import re
import shutil
import sys
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
DATA = os.path.join(SITE, "data", "catalogue.json")
PAGES = os.path.join(SITE, "p")
SITEMAP = os.path.join(SITE, "sitemap.xml")
PARTS = os.path.join(SITE, "data", "parts")
PART_SIZE = 250  # products per part: about 0.35 MB, read in about 10 ms on a desktop, 40 ms on a slow phone
BASE = "https://groz.tools/site/"  # where the site is published (groz.in shows the same files)
NOTICE = "This is not the official GROZ website."  # no link to GROZ's own site (removed 25 Nov 2026)
# The catalogue's own groups (site/assets/js/core.mjs GROUPS): the category's group name, for the breadcrumb.
GROUP_OF = {
    "Greasing Equipment": "Lubrication", "Oiling Equipment": "Lubrication", "Hose Reels": "Lubrication",
    "Waste Oil Handling": "Lubrication", "Drum Handling": "Lubrication", "Fuel & DEF Handling": "Fuel & DEF",
    "Air Handling": "Air Tools", "LED Worklights": "Lighting", "Striking Tools": "Hand Tools",
    "Tool Storage": "Mechanic's Tools", "Battery Grease Guns": "Power Tools", "Precision Tools": "Precision Tools",
}
# Same theme as the catalogue page: the visitor's choice if any, else the device setting.
THEME_SCRIPT = ('<script>(function(){var d=document.documentElement,t=null;try{t=JSON.parse(localStorage.getItem("groz.theme"))}catch(e){}'
                'if(t!=="light"&&t!=="dark")t=window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";'
                'd.setAttribute("data-theme",t)})()</script>')
ICON = ("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Crect x=%272%27 y=%272%27 "
        "width=%2728%27 height=%2728%27 rx=%277%27 fill=%27%23f4511e%27/%3E%3Cpath d=%27M9 11h14M9 16h14M9 21h9%27 stroke=%27white%27 "
        "stroke-width=%273%27 stroke-linecap=%27round%27/%3E%3C/svg%3E")


def esc(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def display_title(p: Dict[str, Any]) -> Optional[str]:
    return p.get("title") or p.get("heading") or None


def detail_rows(p: Dict[str, Any]) -> List[List[str]]:
    """The printed values, as the catalogue page's details show them (core.mjs detailRows), without the gaps."""
    rows = [["CAT NR (catalogue number)", p.get("cat_nr")], ["ORD NR (order number)", p.get("ord_nr")],
            ["Size (inch)", p.get("dimensions_inch")], ["Size (mm)", p.get("dimensions_mm")],
            ["Box quantity", None if p.get("box_qty") is None else str(p["box_qty"])]]
    rows += [[s["label"], s["value"]] for s in p.get("specs") or []]
    return [[label, str(value)] for label, value in rows if value not in (None, "")]


def picture_size(rel: str) -> Optional[tuple]:
    try:
        with Image.open(os.path.join(SITE, rel)) as im:
            return im.size
    except OSError:
        return None


def json_ld(data: Dict[str, Any]) -> str:
    # "</" would end the script element early; JSON allows "<\/" for it.
    return json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")


def page_head(title: str, description: str, canonical: str, image: Optional[str], css: str, extra: str = "") -> str:
    og_image = f'\n<meta property="og:image" content="{esc(image)}"/>' if image else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="color-scheme" content="light dark"/>
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}"/>
<link rel="canonical" href="{esc(canonical)}"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="GROZ Catalogue (not the official GROZ website)"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(description)}"/>
<meta property="og:url" content="{esc(canonical)}"/>{og_image}
<meta name="twitter:card" content="{'summary_large_image' if image else 'summary'}"/>
<link rel="icon" href="{ICON}"/>
{THEME_SCRIPT}
<link rel="stylesheet" href="{css}"/>{extra}
</head>"""


def describe(p: Dict[str, Any], title: Optional[str]) -> str:
    """A one-line description from the record's own values (for search results and link previews)."""
    facts = [f"{label}: {value}" for label, value in detail_rows(p)[2:5]]
    parts = [f"GROZ {title}" if title else "GROZ product", f"CAT NR {p['cat_nr']}" if p.get("cat_nr") else "",
             f"ORD NR {p['ord_nr']}" if p.get("ord_nr") else ""]
    text = ", ".join(x for x in parts if x) + "."
    if facts:
        text += " " + "; ".join(facts) + "."
    text += f" From the {p['catalogue']['title']} catalogue, page {p.get('printed_page') or p.get('page')}."
    return text if len(text) <= 300 else text[:297].rstrip() + "…"


def product_page(p: Dict[str, Any]) -> str:
    title = display_title(p)
    name = " ".join(x for x in (title, p.get("cat_nr")) if x) or p["id"]
    url = f"{BASE}p/{p['id']}.html"
    img = p.get("image")
    image_url = BASE + img["src"] if img else None
    description = describe(p, title)
    rows = detail_rows(p)
    group = GROUP_OF.get(p["category"])
    printed = p.get("printed_page") or p.get("page")
    pdf_href = "../" + p["catalogue"]["href"]  # the data's links are relative to site/; these pages are in site/p/

    ld: Dict[str, Any] = OrderedDict([("@context", "https://schema.org"), ("@type", "Product"), ("name", name)])
    if image_url:
        ld["image"] = image_url
    ld["description"] = description
    ld["brand"] = {"@type": "Brand", "name": p.get("brand") or "GROZ"}
    if p.get("cat_nr"):
        ld["mpn"] = p["cat_nr"]
    if p.get("ord_nr"):
        ld["sku"] = p["ord_nr"]
    ld["category"] = " > ".join(x for x in (group if group != p["category"] else None, p["category"]) if x)
    ld["url"] = url
    props = [{"@type": "PropertyValue", "name": label, "value": value} for label, value in rows[2:]]
    if props:
        ld["additionalProperty"] = props

    size = picture_size(img["src"]) if img else None
    dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
    figure = (f'<figure class="pp-pic"><img src="../{esc(img["src"])}" alt="{esc(name)}"{dims}/>'
              f'<figcaption>Picture from the GROZ catalogue, page {esc(printed)}'
              f'{" (the picture shared by this family of products)" if img.get("evidence") == "product_family" else ""}.</figcaption></figure>'
              if img else "")
    review = (f'<p class="pp-note"><b>Under review:</b> {esc(", ".join(u["label"] for u in p["under_review"]))}: '
              "a corrected reading is awaiting approval, so it is not shown.</p>" if p.get("under_review") else "")
    crumbs = " › ".join(x for x in (group if group != p["category"] else None, p["category"]) if x)
    return page_head(f"{name} — GROZ Catalogue", description, url, image_url, "../assets/product-page.css",
                     f'\n<script type="application/ld+json">\n{json_ld(ld)}\n</script>') + f"""
<body>
<div class="pp-notice" role="note">{NOTICE}</div>
<main class="pp">
  <nav class="pp-crumbs" aria-label="Breadcrumb"><a href="../">GROZ Catalogue</a> › <a href="./#{slug(p['category'])}">{esc(crumbs)}</a></nav>
  <article class="pp-card">
    {figure}
    <div class="pp-copy">
      <p class="pp-eyebrow">{esc(p.get('brand') or 'GROZ')} · {esc(p['category'])}</p>
      <h1>{esc(title or p.get('cat_nr') or 'GROZ product')}</h1>
      <p class="pp-codes">{f"CAT NR <b>{esc(p['cat_nr'])}</b>" if p.get('cat_nr') else ""}{" · " if p.get('cat_nr') and p.get('ord_nr') else ""}{f"ORD NR <b>{esc(p['ord_nr'])}</b>" if p.get('ord_nr') else ""}</p>
      <table class="pp-specs"><caption>As printed in the catalogue</caption>
{"".join(f"        <tr><th scope='row'>{esc(label)}</th><td>{esc(value)}</td></tr>{chr(10)}" for label, value in rows)}      </table>
      {review}
      <p class="pp-actions"><a class="pp-btn" href="../#p-{esc(p['id'])}">Ask for a quote</a>
        <a class="pp-link" href="{esc(pdf_href)}" target="_blank" rel="noopener">The catalogue PDF, page {esc(printed)}</a></p>
      <p class="pp-small">“Ask for a quote” opens this product in the catalogue: add it to your quote and send it. Buyers from
        Africa, the Gulf and worldwide are welcome; prices in USD, EUR or INR.</p>
      <p class="pp-small">From the {esc(p['catalogue']['title'])} catalogue. {esc(p.get('status_label') or '')}: these details were
        read from the printed catalogue automatically; check the catalogue page before ordering.</p>
    </div>
  </article>
</main>
<footer class="pp-foot">Not the official GROZ website.</footer>
</body>
</html>
"""


def index_page(products: List[Dict[str, Any]], categories: List[str]) -> str:
    by_cat: Dict[str, List[Dict[str, Any]]] = OrderedDict((c, []) for c in categories)
    for p in products:
        by_cat.setdefault(p["category"], []).append(p)
    sections = []
    for cat, items in by_cat.items():
        if not items:
            continue
        lis = "".join(f'<li><a href="{esc(p["id"])}.html"><b>{esc(p.get("cat_nr") or "")}</b> {esc(display_title(p) or "")}</a></li>\n'
                      for p in items)
        sections.append(f'<section id="{slug(cat)}"><h2>{esc(cat)} <span>{len(items)}</span></h2>\n<ul class="pp-list">\n{lis}</ul></section>')
    toc = " · ".join(f'<a href="#{slug(c)}">{esc(c)}</a>' for c, items in by_cat.items() if items)
    return page_head("All GROZ products — GROZ Catalogue",
                     f"Every product in this GROZ catalogue website ({len(products)} products), by category, with its CAT NR.",
                     f"{BASE}p/", None, "../assets/product-page.css") + f"""
<body>
<div class="pp-notice" role="note">{NOTICE}</div>
<main class="pp pp-wide">
  <nav class="pp-crumbs" aria-label="Breadcrumb"><a href="../">GROZ Catalogue</a> › All products</nav>
  <h1>All products</h1>
  <p class="pp-toc">{toc}</p>
  {chr(10).join(sections)}
</main>
<footer class="pp-foot">Not the official GROZ website.</footer>
</body>
</html>
"""


def sitemap(products: List[Dict[str, Any]], day: str) -> str:
    urls = [BASE, f"{BASE}flipbook.html", f"{BASE}p/"] + [f"{BASE}p/{p['id']}.html" for p in products]
    body = "".join(f"  <url><loc>{esc(u)}</loc><lastmod>{day}</lastmod></url>\n" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'


def write_parts(data: Dict[str, Any]) -> int:
    """site/data/parts/: index.json (everything but the products, plus the part names) and the parts."""
    if os.path.isdir(PARTS):
        shutil.rmtree(PARTS)  # this script's own output only
    os.makedirs(PARTS)
    products = data["products"]
    names = []
    for i in range(0, len(products), PART_SIZE):
        name = f"{i // PART_SIZE}.json"
        with open(os.path.join(PARTS, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(products[i:i + PART_SIZE], f, ensure_ascii=False, separators=(",", ":"))
        names.append(name)
    index = {k: v for k, v in data.items() if k != "products"}
    index["parts"] = names
    with open(os.path.join(PARTS, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    return len(names)


def main() -> int:
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    products = data["products"]
    ids = [p["id"] for p in products]
    bad = [i for i in ids if not re.fullmatch(r"[A-Za-z0-9._-]+", i)]
    if bad:
        raise SystemExit(f"Product ids that cannot be file names: {bad[:5]}")
    lower = {}
    for i in ids:
        if lower.setdefault(i.lower(), i) != i:
            raise SystemExit(f"Two products differ only in capitals ({lower[i.lower()]}, {i}): their pages would clash on Windows.")
    if os.path.isdir(PAGES):
        shutil.rmtree(PAGES)  # this script's own output only: pages of products no longer in the data go
    os.makedirs(PAGES)
    for p in products:
        with open(os.path.join(PAGES, f"{p['id']}.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(product_page(p))
    with open(os.path.join(PAGES, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(index_page(products, [c["name"] for c in data["categories"]]))
    with open(SITEMAP, "w", encoding="utf-8", newline="\n") as f:
        f.write(sitemap(products, data["meta"]["generated_at"][:10]))
    n = write_parts(data)
    print(f"site/data/parts/: index.json and {n} parts of up to {PART_SIZE} products")
    print(f"{len(products)} product pages in site/p/, the list site/p/index.html, and site/sitemap.xml "
          f"({len(products) + 3} addresses)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
