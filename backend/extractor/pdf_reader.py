"""PDF Reader module with PyMuPDF and OCR fallback router."""

from typing import List, Dict, Any, Tuple
import os
import pymupdf
from PIL import Image
import io

try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
except Exception:
    ocr_engine = None


class PDFPageReader:
    """Reads PDF pages, handles native text extraction, and routes to OCR if text is absent."""

    def __init__(self, pdf_path: str):
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
        self.pdf_path = pdf_path
        self.doc = pymupdf.open(pdf_path)

    @property
    def total_pages(self) -> int:
        return len(self.doc)

    def get_page(self, page_number_1based: int) -> pymupdf.Page:
        """Returns 0-indexed pymupdf.Page for 1-based page number."""
        if page_number_1based < 1 or page_number_1based > len(self.doc):
            raise IndexError(f"Page number {page_number_1based} out of range [1, {len(self.doc)}]")
        return self.doc[page_number_1based - 1]

    def extract_page_data(self, page_number_1based: int) -> Dict[str, Any]:
        """Extracts text, blocks, images, and determines extraction method for a physical page."""
        page = self.get_page(page_number_1based)
        page_rect = page.rect
        native_text = page.get_text("text").strip()

        # Check if native text is sufficient
        has_adequate_native_text = len(native_text) >= 50
        extraction_method = "native_pdf" if has_adequate_native_text else "ocr"

        ocr_results = None
        if not has_adequate_native_text and ocr_engine is not None:
            # Render page to raster image for OCR
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            ocr_out, _ = ocr_engine(img_bytes)
            ocr_results = ocr_out or []
            # Combine OCR text
            ocr_text = "\n".join([line[1] for line in ocr_results])
            full_text = ocr_text
        else:
            full_text = native_text

        # Extract structured text blocks (x0, y0, x1, y1, text, block_no, block_type)
        raw_blocks = page.get_text("blocks")
        text_blocks = []
        for b in raw_blocks:
            if b[6] == 0:  # text block
                text_blocks.append({
                    "bbox": (b[0], b[1], b[2], b[3]),
                    "text": b[4],
                    "block_id": b[5],
                })

        return {
            "page_number": page_number_1based,
            "page_width": page_rect.width,
            "page_height": page_rect.height,
            "extraction_method": extraction_method,
            "full_text": full_text,
            "text_blocks": text_blocks,
            "ocr_results": ocr_results,
            "is_spread": page_rect.width > 900,  # e.g., 1190pt double spread
        }

    def render_page_preview(self, page_number_1based: int, output_path: str, dpi: int = 150) -> str:
        """Renders page to high-quality PNG for visual verification."""
        page = self.get_page(page_number_1based)
        pix = page.get_pixmap(dpi=dpi)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pix.save(output_path)
        return output_path

    def close(self):
        self.doc.close()
