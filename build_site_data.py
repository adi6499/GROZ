"""Build site/data/catalogue.json for the catalogue website from output_v2 (read-only).

  python build_site_data.py

Re-run after output_v2 or review/preview_*.csv change. See backend/site/catalogue_export.py.
"""

import sys

from backend.site.catalogue_export import SITE_DATA, build, write


def main() -> int:
    data = build()
    write(data)
    m = data["meta"]
    print(f"{SITE_DATA}: {m['records']} products ({m['with_confirmed_image']} with a confirmed image, "
          f"{m['verified']} verified, {m['fields_under_review']} fields withheld as under review)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
