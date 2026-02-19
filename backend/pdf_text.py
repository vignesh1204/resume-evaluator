# backend/pdf_text.py
from __future__ import annotations

from typing import List
import re


def _normalize_text(s: str) -> str:
    # normalize spacing and odd chars that confuse LLM sectioning
    s = s.replace("\u00A0", " ")
    s = s.replace("\ufb01", "fi").replace("\ufb02", "fl")  # ligatures
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Try PyMuPDF first (best); fall back to pdfplumber.
    """
    # PyMuPDF
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        parts: List[str] = []
        for page in doc:
            parts.append(page.get_text("text"))
        doc.close()
        text = "\n".join(parts)
        text = _normalize_text(text)
        if text:
            return text
    except Exception:
        pass

    # pdfplumber
    import pdfplumber
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            parts.append(p.extract_text() or "")
    text = "\n".join(parts)
    return _normalize_text(text)