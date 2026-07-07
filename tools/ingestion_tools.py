"""Local file-ingestion helpers for user-supplied career evidence.

The helpers extract text only. They do not execute documents, follow links or
submit data to a model. The Streamlit app shows the extracted text so the user
can review and edit it before building an application pack.
"""

from __future__ import annotations

import io
import pathlib
from typing import Dict

MAX_UPLOAD_BYTES = 2_000_000
MAX_EXTRACTED_CHARS = 20_000
MAX_PDF_PAGES = 12
TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS


def _normalise_text(text: str) -> str:
    lines = []
    for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        cleaned = " ".join(line.split())
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines).strip()


def _truncate(text: str) -> tuple[str, str]:
    if len(text) <= MAX_EXTRACTED_CHARS:
        return text, ""
    return (
        text[:MAX_EXTRACTED_CHARS].rstrip(),
        f"Extracted text was truncated to {MAX_EXTRACTED_CHARS} characters for review.",
    )


def _decode_text_file(data: bytes) -> str:
    for encoding in ["utf-8-sig", "utf-8", "cp1252"]:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_pdf_text(data: bytes) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depends on optional package install
        raise RuntimeError("PDF CV parsing requires pypdf. Run `python -m pip install -r requirements.txt`.") from exc

    reader = PdfReader(io.BytesIO(data))
    page_count = len(reader.pages)
    pages_to_read = min(page_count, MAX_PDF_PAGES)
    text_parts = []
    for page in reader.pages[:pages_to_read]:
        text_parts.append(page.extract_text() or "")
    warning = ""
    if page_count > MAX_PDF_PAGES:
        warning = f"PDF had {page_count} pages; only the first {MAX_PDF_PAGES} were parsed."
    return "\n".join(text_parts), warning


def extract_career_profile_from_file(filename: str, data: bytes) -> Dict[str, object]:
    """Extract editable career evidence text from a user-uploaded CV/profile file."""
    suffix = pathlib.Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return {
            "ok": False,
            "text": "",
            "warning": "",
            "error": "Unsupported file type. Upload a .txt, .md or .pdf file.",
            "source_name": filename,
            "source_type": suffix or "unknown",
        }

    if len(data or b"") > MAX_UPLOAD_BYTES:
        return {
            "ok": False,
            "text": "",
            "warning": "",
            "error": f"File is too large. Maximum supported size is {MAX_UPLOAD_BYTES // 1_000_000} MB.",
            "source_name": filename,
            "source_type": suffix,
        }

    warning = ""
    if suffix in TEXT_EXTENSIONS:
        raw_text = _decode_text_file(data or b"")
    else:
        raw_text, warning = _extract_pdf_text(data or b"")

    text, truncation_warning = _truncate(_normalise_text(raw_text))
    combined_warning = " ".join([part for part in [warning, truncation_warning] if part])
    return {
        "ok": True,
        "text": text,
        "warning": combined_warning,
        "error": "",
        "source_name": filename,
        "source_type": suffix,
        "char_count": len(text),
    }
