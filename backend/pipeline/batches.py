"""Which catalogue pages belong to which extraction batch.

Every page of a source is processed unless `pages` lists specific physical pages. Pages without an
ordering table simply produce no records, so processing a whole catalogue cannot invent products;
it only stops pages from being skipped by mistake (as LED/695 on lighting page 5 once was).
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Source:
    pdf: str
    pages: Optional[Tuple[int, ...]] = None  # physical page numbers (1-based); None = every page


@dataclass(frozen=True)
class Batch:
    name: str
    description: str
    sources: Tuple[Source, ...]
    approved: bool = True  # unapproved batches refuse to run; approval = editing this flag in a commit
    output_dir: Optional[str] = None  # dedicated output folder; None = the main corrected dataset (output_v2)


BATCHES: Dict[str, Batch] = {
    "batch_1": Batch(
        "batch_1",
        "Tool storage + lighting, all pages (includes the former pilot pages 6-10 and page 5, LED/695)",
        (Source("tools_storage.pdf"), Source("GROZ_LIGHTING_GL-10_1.pdf")),
    ),
    "batch_2": Batch(
        "batch_2",
        "Estwing hammers + Precision measuring tools, all pages",
        (Source("Estwing_Hammer_E-03_Interactive_1.pdf"), Source("Precision_Catalogue_CA_03.pdf")),
    ),
    "batch_3_pilot": Batch(
        "batch_3_pilot",
        "Hand Tool catalogue pilot: p8 divider, p11 + p53 two-column tables, p12 standard table, "
        "p224 calipers already extracted from Precision. Approved by the project owner on 17 Oct 2026.",
        (Source("Hand_Tool_Catalogue_low_res_with_cover.pdf", (8, 11, 12, 53, 224)),),
        approved=True,
        output_dir="output_pilot_handtool",
    ),
    "batch_3_fluid": Batch(
        "batch_3_fluid",
        "Fluid Handling CC-07 (all 372 pages: lubrication, fuel & DEF, air handling) and FUEL CAT 400 (32 pages), "
        "read with the column reader of rules 3.0.x. Approved by the project owner on 21 Oct 2026 "
        "(\"Extract all, preview\"); the preview (output_preview_fluid/) was approved for the website the same day "
        "(\"approve the preview and make it live\"), so the batch is now part of the main dataset.",
        (Source("Fluid_Handling_Catalogue_spread.pdf", tuple(range(1, 373))), Source("FUEL.pdf")),
    ),
    "batch_3_striking": Batch(
        "batch_3_striking",
        "Workshop Tools CB-05 (the Hand Tool catalogue), its striking-tools pages with hammers, axes, mauls and "
        "mallets: physical pages 8-47 (printed 9-45; the chapter divider and introduction pages print no ordering "
        "table). Read with the column reader of rules 3.2.0. Approved by the project owner on 24 Nov 2026 to "
        "replace the Estwing hammers on the website (\"replace the 131 Estwing hammers with GROZ hammers from "
        "CI 37\"; \"Yes, that's CI 37\"; \"do all things first and then push the codes one go\").",
        (Source("Hand_Tool_Catalogue_low_res_with_cover.pdf", tuple(range(8, 48))),),
    ),
    "batch_3_workshop": Batch(
        "batch_3_workshop",
        "Workshop Tools CB-05 (the Hand Tool catalogue), the rest of its product pages after the hammers: "
        "physical pages 48-253 (printed 46-251): punches, chisels and bars, hacksaws, vices and clamps, "
        "woodworking tools, automotive tools, sockets, impact and ratchet wrenches, torque tools, tool storage, "
        "spanners and wrenches, pliers and cutters, measuring and marking, taps and dies, specialty hand tools. "
        "The numerical index (pages 254-257) is a checklist, not product pages. Read with rules 3.3.0. "
        "Approved by the project owner on 27 Nov 2026 to add GROZ's missing hand and mechanic's tools to the "
        "website, as Mitul's groz.tools plan asked (\"Shall I start on the Workshop Tools CB-05 pages next ... as "
        "a preview for your OK?\" - \"well do one and push it once\").",
        (Source("Hand_Tool_Catalogue_low_res_with_cover.pdf", tuple(range(48, 254))),),
    ),
}

BATCH_ORDER = ("batch_1", "batch_2", "batch_3_pilot", "batch_3_fluid", "batch_3_striking", "batch_3_workshop")

# Batch 3 catalogues: only the pages listed here may be processed, so no batch definition (or edit of
# one) can run more of them by accident. Hand Tool: the striking-tools pages 8-47 approved for
# batch_3_striking on 24 Nov 2026 and the product pages 48-253 approved for batch_3_workshop on 27 Nov
# 2026 (the pilot pages 53 and 224 are among them); the index pages 254-257 and the covers stay closed.
# Fluid Handling: every page, approved for batch_3_fluid on 21 Oct 2026.
RESTRICTED_SOURCES: Dict[str, Tuple[int, ...]] = {
    "Hand_Tool_Catalogue_low_res_with_cover.pdf": tuple(range(8, 254)),
    "Fluid_Handling_Catalogue_spread.pdf": tuple(range(1, 373)),
}

# Brochure editions without order numbers. Policy (approved 14 Oct 2026): supplementary sources for
# images, features and descriptions of products extracted from the full catalogues. They never
# create product records by default; genuinely new products or specifications are flagged for review.
SUPPLEMENTARY_SOURCES: Dict[str, str] = {
    "Workshop_mini-compress.pdf": "brochure edition of Hand Tool / workshop products (no ORD numbers)",
    "Fluid_Handling_mini_min_2.pdf": "brochure edition of Fluid_Handling_Catalogue_spread.pdf (no ORD numbers)",
}

# Catalogue pages that are numerical indexes (ORD NR -> printed page). Used as completeness checklists.
INDEX_PAGES: Dict[str, Tuple[int, ...]] = {
    "Precision_Catalogue_CA_03.pdf": (82, 83),
    "Hand_Tool_Catalogue_low_res_with_cover.pdf": (254, 255, 256, 257),
    "Fluid_Handling_Catalogue_spread.pdf": (365, 366, 367, 368, 369),
}
