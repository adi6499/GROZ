"""Prototype Extraction Runner for Milestone 1.

Processes pages 6–10 of GROZ_LIGHTING_GL-10_1.pdf, extracts products,
crops images, calculates confidence, and creates visual review reports.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.extractor.pdf_reader import PDFPageReader
from backend.extractor.image_extractor import ImageExtractor
from backend.extractor.product_builder import ProductBuilder
from backend.validator.schema import ProductRecord


def main():
    pdf_filename = "GROZ_LIGHTING_GL-10_1.pdf"
    if not os.path.exists(pdf_filename):
        print(f"Error: Target catalogue '{pdf_filename}' does not exist in workspace.")
        sys.exit(1)

    output_dir = "output"
    images_dir = os.path.join(output_dir, "images")
    previews_dir = os.path.join(output_dir, "previews")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(previews_dir, exist_ok=True)

    print(f"Starting Milestone 1 extraction on '{pdf_filename}' (Pages 6 to 10)...")
    reader = PDFPageReader(pdf_filename)
    image_extractor = ImageExtractor(output_dir=images_dir)
    builder = ProductBuilder(image_extractor=image_extractor)

    all_products: list[ProductRecord] = []
    page_summaries = []

    target_pages = [6, 7, 8, 9, 10]

    for pno in target_pages:
        print(f"\n--- Processing Physical Page {pno} ---")
        # 1. Render page preview
        preview_path = os.path.join(previews_dir, f"page_{pno}_preview.png")
        reader.render_page_preview(pno, preview_path, dpi=130)
        print(f"Rendered page preview: {preview_path}")

        # 2. Extract page data & determine method
        page_data = reader.extract_page_data(pno)
        method = page_data["extraction_method"]
        print(f"Extraction method: {method} (Native text chars: {len(page_data['full_text'])})")

        # 3. Process products on page
        page_obj = reader.get_page(pno)
        products = builder.process_page(
            page=page_obj,
            source_pdf=pdf_filename,
            page_number=pno,
            extraction_method=method,
        )

        print(f"Extracted {len(products)} product record(s) on Page {pno}:")
        for p in products:
            img_count = len(p.images)
            print(f"  • {p.product_name} | CAT: {p.cat_nr} | ORD: {p.ord_nr} | Conf: {p.confidence} | Status: {p.verification_status} | Imgs: {img_count}")

        all_products.extend(products)
        page_summaries.append({
            "page_number": pno,
            "preview_relpath": os.path.relpath(preview_path, output_dir),
            "extraction_method": method,
            "char_count": len(page_data["full_text"]),
            "text_sample": page_data["full_text"][:350],
            "product_count": len(products),
        })

    reader.close()

    # Save JSON database
    json_path = os.path.join(output_dir, "extracted_products.json")
    products_dict = [p.model_dump() for p in all_products]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(products_dict, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(all_products)} products to {json_path}")

    # Generate Review Report HTML
    generate_html_report(all_products, page_summaries, output_dir)
    # Generate Review Report Markdown
    generate_markdown_report(all_products, page_summaries, output_dir)

    print("\nMilestone 1 prototype execution completed successfully!")


def generate_html_report(products: list[ProductRecord], page_summaries: list[dict], output_dir: str):
    """Generates a customer-facing review report in Apple-inspired Orange/Black/White theme."""
    report_path = os.path.join(output_dir, "review_report.html")

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GROZ Product Catalogue - Extraction Review Report</title>
<style>
  :root {
    --groz-orange: #FF5500;
    --groz-dark: #121214;
    --groz-card-bg: #1B1B1E;
    --groz-border: #2C2C30;
    --text-primary: #FFFFFF;
    --text-secondary: #A0A0A5;
    --badge-unverified: #E58E26;
    --badge-review: #EB4D4B;
  }
  body {
    margin: 0;
    padding: 24px;
    background: var(--groz-dark);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .header {
    max-width: 1200px;
    margin: 0 auto 32px auto;
    border-bottom: 1px solid var(--groz-border);
    padding-bottom: 24px;
  }
  .brand-badge {
    background: var(--groz-orange);
    color: #fff;
    padding: 4px 12px;
    font-weight: 700;
    border-radius: 4px;
    font-size: 13px;
    letter-spacing: 1px;
    display: inline-block;
  }
  h1 { margin: 12px 0 6px 0; font-size: 28px; font-weight: 700; }
  p.subtitle { color: var(--text-secondary); margin: 0; font-size: 15px; }
  .container { max-width: 1200px; margin: 0 auto; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 24px; margin-bottom: 40px; }
  .card {
    background: var(--groz-card-bg);
    border: 1px solid var(--groz-border);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }
  .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
  .product-title { font-size: 20px; font-weight: 700; color: #fff; margin: 0; }
  .product-sub { color: var(--groz-orange); font-size: 13px; font-weight: 600; text-transform: uppercase; margin-top: 4px; }
  .badge {
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
  }
  .badge-unverified { background: rgba(229, 142, 38, 0.2); color: var(--badge-unverified); border: 1px solid var(--badge-unverified); }
  .badge-review { background: rgba(235, 77, 75, 0.2); color: var(--badge-review); border: 1px solid var(--badge-review); }
  .image-container {
    width: 100%;
    height: 180px;
    background: #0D0D0E;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    margin: 12px 0;
    border: 1px solid #232326;
  }
  .image-container img { max-width: 90%; max-height: 90%; object-fit: contain; }
  .spec-table { width: 100%; font-size: 12px; border-collapse: collapse; margin-top: 10px; }
  .spec-table td { padding: 6px 0; border-bottom: 1px solid #252529; }
  .spec-key { color: var(--text-secondary); width: 45%; }
  .spec-val { color: #fff; font-weight: 500; }
  .source-box {
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid #252529;
    font-size: 11px;
    color: var(--text-secondary);
    display: flex;
    justify-content: space-between;
  }
  .preview-section { margin-top: 40px; }
  .preview-item { background: var(--groz-card-bg); border: 1px solid var(--groz-border); border-radius: 12px; padding: 16px; margin-bottom: 24px; }
  .preview-item img { max-width: 100%; border-radius: 8px; border: 1px solid #333; margin-top: 12px; }
</style>
</head>
<body>
<div class="header">
  <span class="brand-badge">GROZ INDUSTRIAL</span>
  <h1>Milestone 1: Extraction & Lineage Review Report</h1>
  <p class="subtitle">Catalogue: <strong>GROZ_LIGHTING_GL-10_1.pdf</strong> | Physical Pages: 6 – 10 | Target SKUs: 11</p>
</div>

<div class="container">
  <h2>Extracted Product Records (11 Products)</h2>
  <div class="grid">
"""

    for p in products:
        img_src = p.images[0].file_path if p.images else ""
        badge_cls = "badge-review" if p.verification_status == "needs_review" else "badge-unverified"
        
        specs_rows = f"""
          <tr><td class="spec-key">CAT NR</td><td class="spec-val"><strong>{p.cat_nr or '—'}</strong></td></tr>
          <tr><td class="spec-key">ORD NR</td><td class="spec-val"><strong>{p.ord_nr or '—'}</strong></td></tr>
          <tr><td class="spec-key">Box Qty</td><td class="spec-val">{p.box_qty or '—'}</td></tr>
          <tr><td class="spec-key">Dimensions (in)</td><td class="spec-val">{p.dimensions_inch or '—'}</td></tr>
          <tr><td class="spec-key">Dimensions (mm)</td><td class="spec-val">{p.dimensions_mm or '—'}</td></tr>
        """
        for k, v in p.specifications.items():
            specs_rows += f'<tr><td class="spec-key">{k.replace("_", " ").title()}</td><td class="spec-val">{v}</td></tr>'

        img_html = f'<div class="image-container"><img src="{img_src}" alt="{p.product_name}" /></div>' if img_src else '<div class="image-container" style="color:#666;font-size:12px;">No Direct Image</div>'

        # Editorial review notes block
        editorial_html = ""
        if p.editorial_notes:
            for note in p.editorial_notes:
                editorial_html += f"""
                <div style="margin-top:12px; padding:10px; background:rgba(229,142,38,0.12); border-left:3px solid var(--badge-unverified); border-radius:4px; font-size:12px;">
                  <strong style="color:var(--badge-unverified);">Editorial Review Flag ({note.field_name}):</strong>
                  <div style="margin-top:4px; color:#ccc;">{note.suspected_issue}</div>
                  <div style="margin-top:4px; color:#aaa; font-size:11px;">Suggested: <em>{note.suggested_correction}</em></div>
                </div>
                """

        html += f"""
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="product-title">{p.product_name}</h3>
              <div class="product-sub">{p.sub_title or 'LED Industrial Lighting'}</div>
            </div>
            <span class="badge {badge_cls}">{p.verification_status} ({int(p.confidence*100)}%)</span>
          </div>
          {img_html}
          <table class="spec-table">
            <tbody>
              {specs_rows}
            </tbody>
          </table>
          {editorial_html}
          <div class="source-box">
            <span>PDF: Page {p.physical_page_number} (Printed: {p.catalog_page_label})</span>
            <span>Method: {p.extraction_method}</span>
          </div>
        </div>
        """

    html += """
  </div>

  <div class="preview-section">
    <h2>Source Page Previews & Physical Spread References</h2>
"""
    for sm in page_summaries:
        html += f"""
        <div class="preview-item">
          <h3>Physical Page {sm['page_number']} — Extracted {sm['product_count']} Products ({sm['extraction_method']})</h3>
          <p style="color:#aaa; font-size:13px;">Extracted text character count: {sm['char_count']} chars</p>
          <img src="{sm['preview_relpath']}" alt="Page {sm['page_number']} Preview" />
        </div>
        """

    html += """
  </div>
</div>
</body>
</html>
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated HTML review report: {report_path}")


def generate_markdown_report(products: list[ProductRecord], page_summaries: list[dict], output_dir: str):
    """Generates a GitHub-flavored Markdown review report."""
    md_path = os.path.join(output_dir, "review_report.md")
    
    lines = [
        "# GROZ Product Catalogue — Milestone 1 Extraction Report",
        "",
        "**Target Catalogue**: `GROZ_LIGHTING_GL-10_1.pdf`  ",
        "**Pages Processed**: Physical Pages 6 to 10 (Printed Pages 8 to 17)  ",
        f"**Total Records Extracted**: {len(products)}  ",
        "**Anti-Hallucination Policy**: Strictly enforced (no invented fields; verification status initialized to `unverified` / `needs_review`).",
        "",
        "---",
        "",
        "## 1. Extracted Product Records Summary",
        "",
        "| Physical Page | Model / Product | CAT NR | ORD NR | Box Qty | Dimensions (Inch / MM) | Confidence | Status | Images Attached |",
        "| :---: | :--- | :--- | :--- | :---: | :--- | :---: | :---: | :---: |",
    ]

    for p in products:
        dim = f"{p.dimensions_inch or '—'} / {p.dimensions_mm or '—'}"
        img_str = f"✅ {len(p.images)} image(s)" if p.images else "❌ None"
        lines.append(
            f"| Page {p.physical_page_number} | **{p.product_name}** | `{p.cat_nr or '—'}` | `{p.ord_nr or '—'}` | {p.box_qty or '—'} | {dim} | {int(p.confidence*100)}% | `{p.verification_status}` | {img_str} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 2. Technical Specifications & Verified Attributes",
        "",
    ])

    for p in products:
        lines.append(f"### {p.product_name} (`{p.cat_nr}` / ORD: `{p.ord_nr}`)")
        lines.append(f"- **Subtitle**: {p.sub_title or '—'}")
        lines.append(f"- **Source Lineage**: Page {p.physical_page_number} (Printed: {p.catalog_page_label}) | Extraction: `{p.extraction_method}`")
        lines.append(f"- **Confidence Score**: {p.confidence} | **Status**: `{p.verification_status}`")
        if p.description:
            lines.append(f"- **Description**: {p.description}")
        if p.specifications:
            lines.append("- **Specifications**:")
            for k, v in p.specifications.items():
                lines.append(f"  - `{k}`: {v}")
        if p.images:
            lines.append("- **Associated Image Crops**:")
            for img in p.images:
                lines.append(f"  - `[{img.association_type}]` `{img.file_path}` (BBox: x0={img.bounding_box.x0}, y0={img.bounding_box.y0}, x1={img.bounding_box.x1}, y1={img.bounding_box.y1}, Conf: {img.confidence})")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated Markdown review report: {md_path}")


if __name__ == "__main__":
    main()
