"""Summary metrics, summary Markdown and review dashboard -- every number computed from the data."""

import html
import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence

from ..pipeline.batches import BATCHES

ASSOC_LABEL = {
    "direct_product": "Direct product image",
    "product_family": "Product-family image",
    "unresolved": "Unresolved candidate",
}


def compute_metrics(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ords = Counter(r["ord_nr"] for r in records if r.get("ord_nr"))
    images = [im for r in records for im in r.get("images", [])]
    return {
        "records": len(records),
        "by_batch": dict(Counter(r.get("extraction_batch") or "unknown" for r in records)),
        "by_pdf": dict(Counter(r["source_pdf"] for r in records)),
        "verification_status": dict(Counter(r["verification_status"] for r in records)),
        "records_with_ord": sum(ords.values()),
        "unique_ords": len(ords),
        "duplicate_ords": {o: [(r["source_pdf"], r["physical_page_number"], r["cat_nr"]) for r in records if r.get("ord_nr") == o]
                           for o, n in sorted(ords.items()) if n > 1},
        "missing_ord": [(r["source_pdf"], r["physical_page_number"], r["cat_nr"]) for r in records if not r.get("ord_nr")],
        "missing_cat": sum(1 for r in records if not r.get("cat_nr")),
        "image_association": dict(Counter(im["association_type"] for im in images)),
        "records_without_image": sum(1 for r in records if not r.get("images")),
        "records_with_confirmed_image": sum(1 for r in records if any(
            im["association_type"] in ("direct_product", "product_family") for im in r.get("images", []))),
        "editorial_notes": [(r["source_pdf"], r["physical_page_number"], r["cat_nr"], r.get("ord_nr"), n)
                            for r in records for n in r.get("editorial_notes", [])],
        "box_qty_present": sum(1 for r in records if r.get("box_qty") is not None),
        "dimensions_present": sum(1 for r in records if r.get("dimensions_inch") or r.get("dimensions_mm")),
        "variant_labelled": sum(1 for r in records if (r.get("specifications") or {}).get("variant_label")),
    }


def _table(rows: List[List[Any]], header: List[str]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return "\n".join(out)


def write_summary_md(path: str, records: Sequence[Dict[str, Any]], coverage: Dict[str, Any],
                     manifests: Dict[str, Dict[str, Any]], problems: List[str]) -> Dict[str, Any]:
    m = compute_metrics(records)
    lines = ["# GROZ extraction summary (computed from data)", ""]
    lines.append("All numbers in this file are computed from the JSON records and the source PDFs when it is "
                 "generated. Nothing is typed by hand.")
    lines += ["", "## Batches", ""]
    lines.append(_table([[n, BATCHES[n].description if n in BATCHES else "", mf.get("record_count"), mf.get("code_version"),
                          mf.get("generated_at")] for n, mf in manifests.items()],
                        ["Batch", "Scope", "Records", "Code version", "Generated (UTC)"]))
    lines += ["", "## Records", ""]
    lines.append(_table([[pdf, n] for pdf, n in sorted(m["by_pdf"].items())] + [["**Total**", f"**{m['records']}**"]],
                        ["Catalogue", "Records"]))
    st = m["verification_status"]
    lines += ["", f"- Verification status: {st.get('unverified', 0)} unverified, {st.get('needs_review', 0)} needs_review, "
              f"**{st.get('verified', 0)} verified** (automatic verification is impossible by design).",
              f"- ORD NR: {m['records_with_ord']} records carry one, {m['unique_ords']} unique; "
              f"{len(m['missing_ord'])} records have none; {len(m['duplicate_ords'])} ORD values are printed more than once.",
              f"- Box quantity present on {m['box_qty_present']} records; dimensions on {m['dimensions_present']}; "
              f"printed column-group label (variant_label) on {m['variant_labelled']}."]
    if m["missing_ord"]:
        lines.append("- Records without ORD NR: " + "; ".join(f"{c} ({p[:24]} p{pg})" for p, pg, c in m["missing_ord"]))
    for o, where in m["duplicate_ords"].items():
        lines.append(f"- ORD {o} printed for: " + "; ".join(f"{c} ({p[:24]} p{pg})" for p, pg, c in where))
    ia = m["image_association"]
    lines += ["", "## Images", "",
              _table([[ASSOC_LABEL[k], ia.get(k, 0)] for k in ASSOC_LABEL] +
                     [["Records with a direct or family image", m["records_with_confirmed_image"]],
                      ["Records with no image candidate", m["records_without_image"]]], ["Association", "Count"]),
              "", "Unresolved candidates are linked by page position only and must not be shown as the product's image."]
    lines += ["", "## Editorial review notes", ""]
    lines.append(_table([[f"{c} / {o or '—'}", f"{p[:28]} p{pg}", n["field_name"], n["published_value"], n["review_status"]]
                         for p, pg, c, o, n in m["editorial_notes"]], ["CAT / ORD", "Source", "Field", "Published value", "Status"]))
    lines += ["", "## Coverage against the PDFs", ""]
    rows = []
    for pdf, c in coverage.items():
        idx = c["index"]
        rows.append([pdf, c["pages_checked"], c["printed_ord_tokens"], c["extracted_ords"],
                     sum(len(v) for v in c["printed_not_extracted"].values()),
                     sum(len(v) for v in c["extracted_not_printed"].values()),
                     len(c["cat_nr_not_printed_as_word"]),
                     f"{idx['indexed']} indexed, {len(idx['missing_from_dataset'])} missing" if idx else "—"])
    lines.append(_table(rows, ["Catalogue", "Pages", "Printed ORDs", "Extracted ORDs", "Printed, not extracted",
                               "Extracted, not printed", "CAT not a printed word", "Index check"]))
    lines += ["", f"**Gate findings: {len(problems)}**", ""] + [f"- {p}" for p in problems[:200]]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return m


def write_review_html(path: str, records: Sequence[Dict[str, Any]], changes: Optional[Dict[str, List[str]]] = None,
                      image_prefix: str = "") -> None:
    """Review dashboard. `changes` maps record key -> changed field names (from the change report)."""
    e = html.escape
    m = compute_metrics(records)
    changes = changes or {}
    cards = []
    for r in records:
        key = record_key(r)
        im = r["images"][0] if r.get("images") else None
        assoc = im["association_type"] if im else "none"
        if im:
            img = (f'<img src="{e(image_prefix + im["file_path"])}" alt="{e(r["cat_nr"] or "")}" loading="lazy">'
                   f'<span class="assoc assoc-{assoc}" title="{e(im.get("evidence") or "")}">{e(ASSOC_LABEL[assoc])}</span>')
        else:
            img = '<div class="noimg">No image</div>'
        specs = dict(r.get("specifications") or {})
        variant = specs.pop("variant_label", None)
        spec_rows = []
        if r.get("dimensions_inch") or r.get("dimensions_mm"):
            spec_rows.append(("Size", " / ".join(x for x in (r.get("dimensions_inch") and f'{r["dimensions_inch"]} in',
                                                             r.get("dimensions_mm") and f'{r["dimensions_mm"]} mm') if x)))
        if r.get("box_qty") is not None:
            spec_rows.append(("Box qty", r["box_qty"]))
        spec_rows += [(k.replace("_", " ").capitalize(), v) for k, v in specs.items()]
        notes = "".join(f'<div class="note"><b>{e(n["field_name"])}</b>: {e(n["suspected_issue"])}</div>'
                        for n in r.get("editorial_notes", []))
        chg = changes.get(key)
        chg_html = f'<div class="chg">{e(", ".join(chg))}</div>' if chg else ""
        search = " ".join(str(x) for x in (r.get("cat_nr"), r.get("ord_nr"), r.get("product_name"), r.get("sub_title"),
                                           variant, r["source_pdf"]) if x)
        cards.append(f"""<article class="card" data-pdf="{e(r['source_pdf'])}" data-assoc="{assoc}" data-status="{e(r['verification_status'])}"
 data-flag="{'1' if r.get('editorial_notes') else '0'}" data-chg="{'1' if chg else '0'}" data-search="{e(search.lower())}">
 <div class="thumb">{img}</div>
 <div class="body">
  <div class="codes"><span class="cat">{e(r.get('cat_nr') or 'NO CAT')}</span><span class="ord{' missing' if not r.get('ord_nr') else ''}">{e(r.get('ord_nr') or 'NO ORD')}</span><span class="st st-{e(r['verification_status'])}">{e(r['verification_status'])}</span></div>
  {f'<div class="variant">{e(variant)}</div>' if variant else ''}
  <div class="sub">{e(r.get('sub_title') or '')}</div>
  <table>{''.join(f'<tr><td>{e(str(k))}</td><td>{e(str(v))}</td></tr>' for k, v in spec_rows)}</table>
  {notes}{chg_html}
  <div class="src">{e(r['source_pdf'])} · physical p{r['physical_page_number']} · printed {e(str(r.get('catalog_page_label') or '—'))}</div>
 </div></article>""")
    pdf_opts = "".join(f'<option value="{e(p)}">{e(p)} ({n})</option>' for p, n in sorted(m["by_pdf"].items()))
    ia = m["image_association"]
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GROZ Extraction Review</title><style>
:root{{--bg:#f6f7f9;--card:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--orange:#f97316}}
*{{box-sizing:border-box}}body{{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text)}}
header{{background:#0b0f17;color:#fff;padding:20px 24px;border-bottom:3px solid var(--orange)}}header h1{{margin:0;font-size:20px}}
.kpis{{display:flex;flex-wrap:wrap;gap:18px;margin-top:10px;color:#cbd5e1;font-size:13px}}.kpis b{{color:#fff;font-size:17px;display:block}}
.controls{{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid var(--line);padding:10px 24px;display:flex;flex-wrap:wrap;gap:8px}}
.controls select,.controls input{{padding:7px 9px;border:1px solid var(--line);border-radius:6px;font:inherit}}.controls input{{flex:1;min-width:180px}}
#count{{align-self:center;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px;padding:16px 24px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}}
.thumb{{position:relative;height:170px;background:#f1f5f9;display:flex;align-items:center;justify-content:center}}
.thumb img{{max-width:92%;max-height:150px;object-fit:contain}}.noimg{{color:var(--muted)}}
.assoc{{position:absolute;left:8px;bottom:8px;font-size:11px;padding:2px 7px;border-radius:4px;color:#fff}}
.assoc-direct_product{{background:#15803d}}.assoc-product_family{{background:#1d4ed8}}.assoc-unresolved{{background:#b45309}}
.card[data-assoc=unresolved] .thumb img{{opacity:.55;outline:2px dashed #b45309;outline-offset:4px}}
.body{{padding:10px 12px;display:flex;flex-direction:column;gap:5px}}.codes{{display:flex;flex-wrap:wrap;gap:5px}}
.codes span{{font-size:12px;font-weight:600;padding:2px 6px;border-radius:4px;background:#f1f5f9}}.ord{{background:#e0e7ff!important}}
.missing{{background:#fee2e2!important;color:#991b1b}}.st{{margin-left:auto;font-weight:500!important}}.st-needs_review{{background:#fee2e2!important}}
.variant{{font-size:12px;font-weight:600;color:#9a3412}}.sub{{color:var(--muted);font-size:12px}}
table{{border-collapse:collapse;font-size:12px}}td{{padding:2px 0;vertical-align:top}}td:first-child{{color:var(--muted);padding-right:8px;white-space:nowrap}}
.note{{background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:5px 7px;font-size:11px;color:#7f1d1d}}
.chg{{background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;padding:4px 7px;font-size:11px;color:#9a3412}}
.src{{color:var(--muted);font-size:11px;margin-top:auto}}
</style></head><body>
<header><h1>GROZ extraction review</h1><div class="kpis">
<div><b>{m['records']}</b>records</div><div><b>{m['unique_ords']}</b>unique ORD</div>
<div><b>{m['verification_status'].get('verified', 0)}</b>verified</div><div><b>{m['verification_status'].get('needs_review', 0)}</b>needs review</div>
<div><b>{ia.get('direct_product', 0)}</b>direct images</div><div><b>{ia.get('product_family', 0)}</b>family images</div>
<div><b>{ia.get('unresolved', 0)}</b>unresolved candidates</div><div><b>{len(changes)}</b>changed vs legacy</div></div></header>
<div class="controls"><select id="pdf"><option value="">All catalogues</option>{pdf_opts}</select>
<select id="assoc"><option value="">Any image evidence</option><option value="direct_product">Direct product image</option>
<option value="product_family">Product-family image</option><option value="unresolved">Unresolved candidate</option><option value="none">No image</option></select>
<select id="flag"><option value="">All records</option><option value="flag">Editorial notes</option><option value="review">Needs review</option><option value="chg">Changed vs legacy</option></select>
<input id="q" placeholder="Search CAT NR, ORD NR, name, label"><span id="count"></span></div>
<main class="grid" id="grid">{''.join(cards)}</main>
<script>
const els=[...document.querySelectorAll('.card')],f=id=>document.getElementById(id);
function apply(){{const p=f('pdf').value,a=f('assoc').value,g=f('flag').value,q=f('q').value.trim().toLowerCase();let n=0;
for(const c of els){{const d=c.dataset;const ok=(!p||d.pdf===p)&&(!a||d.assoc===a)&&(!g||(g==='flag'&&d.flag==='1')||(g==='review'&&d.status==='needs_review')||(g==='chg'&&d.chg==='1'))&&(!q||d.search.includes(q));
c.style.display=ok?'':'none';if(ok)n++;}}f('count').textContent=n+' shown';}}
['pdf','assoc','flag'].forEach(i=>f(i).addEventListener('change',apply));f('q').addEventListener('input',apply);apply();
</script></body></html>"""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)


def record_key(r: Dict[str, Any]) -> str:
    return f'{r["source_pdf"]}|{r["physical_page_number"]}|{r.get("cat_nr")}|{r.get("ord_nr")}'


def load_manifests(out_dir: str) -> Dict[str, Dict[str, Any]]:
    folder = os.path.join(out_dir, "batches")
    out = {}
    for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if fn.endswith(".manifest.json"):
            with open(os.path.join(folder, fn), encoding="utf-8") as f:
                mf = json.load(f)
            out[mf["batch"]] = mf
    return out


def pages_by_pdf(manifests: Dict[str, Dict[str, Any]]) -> Dict[str, List[int]]:
    pages = defaultdict(set)
    for mf in manifests.values():
        for pdf, ps in mf["pages_processed"].items():
            pages[pdf].update(ps)
    return {pdf: sorted(ps) for pdf, ps in pages.items()}
