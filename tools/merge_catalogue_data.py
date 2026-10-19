#!/usr/bin/env python3
"""Merge extracted lubrication, fuel, air, and power tool products into site/data/catalogue.json and site/data/catalogue.csv.

Normalizes fields and updates categories, catalogues, and metadata.
"""

import json
import csv
from collections import Counter

CATALOGUE_JSON = "site/data/catalogue.json"
CATALOGUE_CSV = "site/data/catalogue.csv"
LUB_JSON = "output_v2/lubrication_products.json"

def main():
    with open(CATALOGUE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    with open(LUB_JSON, "r", encoding="utf-8") as f:
        new_prods = json.load(f)
        
    existing_ids = {p["id"] for p in data["products"]}
    added_prods = []
    for p in new_prods:
        if p["id"] not in existing_ids:
            existing_ids.add(p["id"])
            added_prods.append(p)
            
    all_products = data["products"] + added_prods
    data["products"] = all_products
    data["meta"]["records"] = len(all_products)
    
    # Update category counts
    by_cat = Counter(p["category"] for p in all_products)
    
    cat_meta = {
        "Tool Storage": {"art": "storage", "blurb": "Cabinets, tool boxes & workbenches"},
        "LED Worklights": {"art": "light", "blurb": "Worklights, floodlights & inspection lamps"},
        "Striking Tools": {"art": "sledge", "blurb": "Sledgehammers, mallets, axes & bars"},
        "Precision Tools": {"art": "measure", "blurb": "Measuring tools & machine accessories"},
        "Lubrication": {"art": "grease", "blurb": "Grease, oil and waste-oil handling, drum handling & hose reels"},
        "Fuel & DEF": {"art": "fuel", "blurb": "Fuel and DEF pumps, meters, nozzles & specialty pumps"},
        "Air Tools": {"art": "air", "blurb": "Impact wrenches & ratchets, blow guns & air control units"},
        "Power Tools": {"art": "drill", "blurb": "Cordless impact wrenches, drill drivers & grease guns"}
    }
    
    categories = []
    for name, info in cat_meta.items():
        if name in by_cat:
            categories.append({
                "name": name,
                "art": info["art"],
                "blurb": info["blurb"],
                "records": by_cat[name]
            })
    data["categories"] = categories
    
    # Ensure groz-lubrication-equipments.pdf is in catalogues list
    lub_records = sum(1 for p in all_products if p.get("catalogue", {}).get("pdf") == "groz-lubrication-equipments.pdf")
    lub_cat_entry = {
        "pdf": "groz-lubrication-equipments.pdf",
        "href": "../groz-lubrication-equipments.pdf",
        "category": "Lubrication",
        "brand": "GROZ",
        "title": "GROZ Lubrication Equipment",
        "art": "grease",
        "blurb": "Grease, oil and waste-oil handling, drum handling & hose reels",
        "records": lub_records
    }
    
    existing_pdfs = {c["pdf"] for c in data["catalogues"]}
    if "groz-lubrication-equipments.pdf" not in existing_pdfs:
        data["catalogues"].append(lub_cat_entry)
    else:
        for c in data["catalogues"]:
            if c["pdf"] == "groz-lubrication-equipments.pdf":
                c["records"] = lub_records
                
    # Write JSON
    with open(CATALOGUE_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=None)
    print(f"Updated {CATALOGUE_JSON}: total {len(all_products)} products across {len(categories)} categories")
    
    # Write complete site catalogue CSV
    with open(CATALOGUE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "cat_nr", "ord_nr", "title", "category", "brand", "catalogue_pdf", "page", "specs"])
        for p in all_products:
            specs_str = " | ".join(f"{s.get('label')}: {s.get('value')}" for s in p.get("specs", []))
            writer.writerow([
                p.get("id"),
                p.get("cat_nr"),
                p.get("ord_nr") or "",
                p.get("title") or p.get("heading") or "",
                p.get("category"),
                p.get("brand"),
                p.get("catalogue", {}).get("pdf"),
                p.get("page"),
                specs_str
            ])
    print(f"Exported complete normalized catalogue to {CATALOGUE_CSV}")

if __name__ == "__main__":
    main()
