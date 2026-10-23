import io
import re

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_PAGES = 30


class ParsePdfError(Exception):
    """Raised for PDFs we cannot turn into text. `status` maps to an HTTP code."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.message = message
        self.status = status


def _clean(text: str) -> str:
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def pdf_to_text(data: bytes) -> tuple[str, int]:
    """Return (text, page_count). Line breaks are kept: the matcher cites lines as evidence."""
    if not data.startswith(b"%PDF-"):
        raise ParsePdfError("File is not a PDF", status=400)

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise ParsePdfError("PDF is password protected")
        pages = len(reader.pages)
        if pages > MAX_PAGES:
            raise ParsePdfError(f"PDF has {pages} pages; the limit is {MAX_PAGES}")
        text = _clean("\n\n".join(page.extract_text() or "" for page in reader.pages))
    except ParsePdfError:
        raise
    except (PyPdfError, ValueError, KeyError, OSError):
        raise ParsePdfError("PDF could not be read; it may be corrupted")

    if not text:
        raise ParsePdfError("No extractable text found. Scanned PDFs need OCR, which is not supported yet")
    return text, pages
