"""Build site/data/catalogue.json for the catalogue website from output_v2 (read-only).

  .venv/Scripts/python.exe build_site_data.py

Also writes review/display_titles.csv: every product whose display title (read from the catalogue
PDF) differs from its extracted heading, with the evidence. Re-run after output_v2 or
review/preview_*.csv change. See backend/site/catalogue_export.py and backend/site/titles.py.
"""

import sys

from backend.site.catalogue_export import SITE_DATA, TITLE_REVIEW, build, write, write_title_review


def main() -> int:
    data = build()
    write(data)
    n = write_title_review(data)
    m = data["meta"]
    print(f"{SITE_DATA}: {m['records']} products ({m['with_confirmed_image']} with a confirmed image, "
          f"{m['verified']} verified, {m['fields_under_review']} fields withheld as under review)")
    print(f"Display titles by rule: {m['titles_by_rule']}")
    print(f"{TITLE_REVIEW}: {n} products whose display title differs from the extracted heading "
          f"({m['heading_relations']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
