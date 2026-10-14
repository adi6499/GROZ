"""Print a PDF page's words grouped into visual lines, with x positions, for inspecting table layouts.

Usage (from the project root):
    .venv/Scripts/python.exe tools/dump_page.py <pdf> <physical_page> [y_from] [y_to]

Read-only: opens the PDF and prints; writes nothing.
"""
import sys

import pymupdf


def main() -> None:
    pdf, pno = sys.argv[1], int(sys.argv[2])
    y_from = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    y_to = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
    page = pymupdf.open(pdf)[pno - 1]
    print(f"{pdf} p{pno}  size={page.rect.width:.0f}x{page.rect.height:.0f}")
    words = sorted((w for w in page.get_text("words") if y_from <= w[1] <= y_to), key=lambda w: (w[1], w[0]))
    line, cur_y = [], None
    for w in words + [None]:
        if w is None or (cur_y is not None and abs(w[1] - cur_y) >= 3.0):
            if line:
                line.sort(key=lambda t: t[0])
                print(f"y={cur_y:6.1f} | " + "  ".join(f"{t[4]}@{t[0]:.0f}" for t in line))
            line = []
        if w is not None:
            cur_y = w[1] if not line else cur_y
            line.append(w)


if __name__ == "__main__":
    main()
