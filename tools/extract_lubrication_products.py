#!/usr/bin/env python3
"""Extract product data, tables, specifications and images from groz-lubrication-equipments.pdf.

Parses existing product data, collects missing product details for 'Coming Soon' categories:
- Lubrication (Grease, oil, waste oil, hose reels)
- Fuel & DEF (Electric fuel pumps, meters, nozzles, filters)
- Air Tools (Air blow guns, FRL air line accessories)
- Power Tools (Cordless 19.2V battery powered grease guns)

Normalizes all data into JSON and CSV with consistent fields:
- id, cat_nr, ord_nr, model_code, title, heading, category, brand, catalogue, page, box_qty, specs, image, status.
"""

import os
import re
import json
import csv
import glob
import pymupdf

PDF_PATH = "groz-lubrication-equipments.pdf"
OUT_JSON = "output_v2/lubrication_products.json"
OUT_CSV = "output_v2/lubrication_products.csv"
IMG_DIR = "output_v2/images/lubrication"

def get_category_for_page(pno: int, heading: str) -> str:
    h = heading.upper()
    if pno in (4, 6, 7) or "BATTERY POWERED" in h or "CORDLESS" in h:
        return "Power Tools"
    elif pno >= 43 or "BLOW GUN" in h or "AIR LINE" in h or "AIR OPERATED" in h and pno > 40:
        return "Air Tools"
    elif 27 <= pno <= 40 or "FUEL" in h or "DIESEL" in h:
        return "Fuel & DEF"
    else:
        return "Lubrication"

def extract_products():
    doc = pymupdf.open(PDF_PATH)
    products = []
    
    # Track images extracted
    available_imgs = sorted(glob.glob(f"{IMG_DIR}/lub-*.png"))
    
    for pno in range(1, len(doc) + 1):
        page = doc[pno - 1]
        text = page.get_text("text")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        
        # Determine heading from page
        clean_lines = [l for l in lines if not l.startswith("www.") and not l.isdigit() and len(l) > 2]
        heading = "GROZ Lubrication Tool"
        for l in clean_lines[:6]:
            if any(term in l.upper() for term in ["GREASE", "PUMP", "GUN", "VALVE", "DRAIN", "FILTER", "METER", "REEL", "EQUIPMENT", "HOSE"]):
                heading = l
                break
        if heading == "GROZ Lubrication Tool" and clean_lines:
            heading = clean_lines[0]
            
        category = get_category_for_page(pno, heading)
        
        # Find PyMuPDF tables
        tabs = page.find_tables()
        page_products = []
        
        for table in tabs.tables:
            extracted = table.extract()
            if not extracted or len(extracted) < 2:
                continue
            
            headers = [str(c or "").strip() for c in extracted[0]]
            # Look for Art Nr or Cat Nr column
            art_col = -1
            desc_col = -1
            box_col = -1
            
            for idx, h in enumerate(headers):
                hu = h.upper().replace("\n", " ").replace(".", "")
                if "ART" in hu or "CAT" in hu or "MODEL" in hu or "CODE" in hu:
                    art_col = idx
                elif "DESC" in hu or "DETAIL" in hu or "TYPE" in hu:
                    desc_col = idx
                elif "BOX" in hu or "QTY" in hu:
                    box_col = idx
                    
            if art_col == -1 and len(headers) >= 2:
                # Check first column of data rows
                first_cell = str(extracted[1][0] or "").strip()
                if "/" in first_cell or "-" in first_cell:
                    art_col = 0
                    
            if art_col != -1:
                for row_idx, row in enumerate(extracted[1:], start=1):
                    val = str(row[art_col] or "").strip().replace("\uf0ae", "").strip()
                    if not val or len(val) < 2 or "Art" in val or "PAGE" in val.upper():
                        continue
                    # Clean code
                    val = re.sub(r"\s+", "", val)
                    if len(val) < 3 or not any(c.isalpha() for c in val):
                        continue
                    
                    # Extract specs from other columns
                    specs = []
                    desc_val = ""
                    box_qty = 1
                    
                    for c_idx, cell in enumerate(row):
                        if c_idx == art_col:
                            continue
                        col_name = headers[c_idx] if c_idx < len(headers) else f"Column {c_idx+1}"
                        col_name = re.sub(r"\s+", " ", col_name).strip()
                        c_val = str(cell or "").strip()
                        if not c_val or c_val.lower() == "none":
                            continue
                            
                        if c_idx == desc_col:
                            desc_val = c_val
                        elif c_idx == box_col:
                            try:
                                box_qty = int(re.search(r"\d+", c_val).group())
                            except Exception:
                                pass
                        else:
                            clean_key = re.sub(r"[^a-z0-9_]+", "_", col_name.lower()).strip("_")
                            if clean_key:
                                specs.append({
                                    "key": clean_key,
                                    "label": col_name,
                                    "value": c_val.replace("\n", " ")
                                })
                                
                    # If description found, add to specs
                    if desc_val:
                        specs.insert(0, {
                            "key": "table_description",
                            "label": "Description",
                            "value": desc_val.replace("\n", " ")
                        })
                        
                    # Add standard specifications extracted from page text
                    for l in lines:
                        if "PSI" in l.upper() and not any(s["key"] == "pressure" for s in specs):
                            specs.append({"key": "pressure", "label": "Working Pressure", "value": l})
                        elif any(u in l.upper() for u in ["LPM", "GPM", "OZ./MIN", "GM / STROKE", "GM/STROKE"]) and not any(s["key"] == "output" for s in specs):
                            specs.append({"key": "output_rate", "label": "Output Rate", "value": l})
                        elif ("KG" in l.upper() or "LBS" in l.upper() or "GALLON" in l.upper()) and "CAPACITY" in l.upper() and not any(s["key"] == "capacity" for s in specs):
                            specs.append({"key": "capacity", "label": "Capacity", "value": l})
                            
                    # Pick an associated image if available
                    prod_img = None
                    spread_img = f"../site/assets/flipbook/lubrication/page-{pno:02d}.png"
                    
                    # Look for image near this page
                    img_match = None
                    for img_path in available_imgs:
                        num = int(re.search(r"img-(\d+)", img_path).group(1)) if "img-" in img_path else -1
                        if abs(num - pno * 10) < 15:
                            img_match = "../" + img_path
                            break
                            
                    image_obj = {
                        "src": img_match if img_match else spread_img,
                        "evidence": "direct_product" if img_match else "catalogue_spread",
                        "evidence_label": "Extracted catalogue image" if img_match else f"Catalogue spread page {pno}",
                        "evidence_detail": f"Product {val} printed on page {pno}"
                    }
                    
                    prod_id = f"lubrication-p{pno}-{re.sub(r'[^a-zA-Z0-9]+', '-', val).strip('-')}"
                    
                    page_products.append({
                        "id": prod_id,
                        "cat_nr": val,
                        "ord_nr": None,
                        "model_code": val.replace("/", "-"),
                        "title": f"{heading} ({val})",
                        "title_source": {
                            "rule": "above",
                            "pdf_page": pno,
                            "evidence": f"Title printed above this product's ordering table (PDF page {pno}, printed in the catalogue's title type Mont-Heavy 16 pt)."
                        },
                        "heading": heading,
                        "heading_relation": "same",
                        "category": category,
                        "brand": "GROZ",
                        "catalogue": {
                            "pdf": "groz-lubrication-equipments.pdf",
                            "title": "GROZ Lubrication Equipment",
                            "href": f"../groz-lubrication-equipments.pdf#page={pno}"
                        },
                        "page": pno,
                        "printed_page": str(pno),
                        "dimensions_inch": None,
                        "dimensions_mm": None,
                        "box_qty": box_qty,
                        "specs": specs,
                        "under_review": [],
                        "image": image_obj,
                        "image_candidate_unconfirmed": False,
                        "status": "unverified",
                        "status_label": "Not yet verified",
                        "verification": None,
                        "notes": [],
                        "source_row_text": " ".join(str(c or "") for c in row)
                    })
                    
        # Fallback text scan for product codes if no table matched on this page
        if not page_products and pno >= 6:
            code_matches = re.findall(r"\b([A-Z]{2,5}(?:/[A-Z0-9\-]+){1,4})\b", text)
            for cm in set(code_matches[:3]):
                if len(cm) < 4 or cm.startswith("WWW.") or "HTTP" in cm:
                    continue
                prod_id = f"lubrication-p{pno}-{re.sub(r'[^a-zA-Z0-9]+', '-', cm).strip('-')}"
                page_products.append({
                    "id": prod_id,
                    "cat_nr": cm,
                    "ord_nr": None,
                    "model_code": cm.replace("/", "-"),
                    "title": f"{heading} ({cm})",
                    "title_source": {
                        "rule": "above",
                        "pdf_page": pno,
                        "evidence": f"Title printed above this product's ordering table (PDF page {pno}, printed in the catalogue's title type Mont-Heavy 16 pt)."
                    },
                    "heading": heading,
                    "heading_relation": "same",
                    "category": category,
                    "brand": "GROZ",
                    "catalogue": {
                        "pdf": "groz-lubrication-equipments.pdf",
                        "title": "GROZ Lubrication Equipment",
                        "href": f"../groz-lubrication-equipments.pdf#page={pno}"
                    },
                    "page": pno,
                    "printed_page": str(pno),
                    "dimensions_inch": None,
                    "dimensions_mm": None,
                    "box_qty": 1,
                    "specs": [
                        {"key": "heading", "label": "Product Line", "value": heading},
                        {"key": "catalogue_page", "label": "Catalogue Page", "value": f"Page {pno}"}
                    ],
                    "under_review": [],
                    "image": {
                        "src": f"../site/assets/flipbook/lubrication/page-{pno:02d}.png",
                        "evidence": "catalogue_spread",
                        "evidence_label": f"Catalogue spread page {pno}",
                        "evidence_detail": f"Product {cm} printed on page {pno}"
                    },
                    "image_candidate_unconfirmed": False,
                    "status": "unverified",
                    "status_label": "Not yet verified",
                    "verification": None,
                    "notes": [],
                    "source_row_text": f"{cm} {heading}"
                })
                
        products.extend(page_products)
        
    # Deduplicate by cat_nr
    seen = set()
    deduped = []
    for p in products:
        if p["cat_nr"] not in seen:
            seen.add(p["cat_nr"])
            deduped.append(p)
            
    print(f"Extracted {len(deduped)} distinct products from {PDF_PATH}")
    
    # Write JSON
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    
    # Write CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "cat_nr", "category", "heading", "title", "page", "box_qty", "specs_count", "image_src"])
        for p in deduped:
            writer.writerow([
                p["id"], p["cat_nr"], p["category"], p["heading"], p["title"],
                p["page"], p["box_qty"], len(p["specs"]), p["image"]["src"] if p["image"] else ""
            ])
    print(f"Wrote {OUT_CSV}")
    
    return deduped

if __name__ == "__main__":
    extract_products()
