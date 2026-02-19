# backend/resume_skeleton.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
import re


def _extract_text_pymupdf(pdf_path: str) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    parts: List[str] = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    return "\n".join(parts)


def _extract_text_pdfplumber(pdf_path: str) -> str:
    import pdfplumber
    parts: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            parts.append(p.extract_text() or "")
    return "\n".join(parts)


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Try PyMuPDF first (better extraction), fallback to pdfplumber.
    """
    try:
        return _extract_text_pymupdf(pdf_path)
    except Exception:
        return _extract_text_pdfplumber(pdf_path)


# -------------------------
# Normalization & detectors
# -------------------------

BULLET_PREFIX_RE = re.compile(r"^\s*[•\-\u2022\u25CF\u25A0\u25AA\u2043\u2219]\s+")
LONE_BULLET_RE = re.compile(r"^\s*[•\-\u2022\u25CF\u25A0\u25AA\u2043\u2219]\s*$")

# Common resume section headings (case-insensitive; allows weird i/l from PDF extraction)
KNOWN_SECTIONS = {
    "summary",
    "professional summary",
    "experience",
    "work experience",
    "professional experience",
    "projects",
    "project experience",
    "education",
    "skills",
    "technical skills",
    "certifications",
    "certification",
    "publications",
    "awards",
    "leadership",
    "volunteering",
    "volunteer experience",
    "activities",
}

# Date-ish patterns
MONTHS_RE = r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)"
YEAR_RE = r"(?:19|20)\d{2}"
DATE_RANGE_RE = re.compile(
    rf"(?i)\b({MONTHS_RE}[A-Z]*\s+{YEAR_RE})\s*[\-\u2013\u2014]\s*({MONTHS_RE}[A-Z]*\s+{YEAR_RE}|PRESENT|CURRENT)\b"
)
SINGLE_DATE_RE = re.compile(rf"(?i)\b({MONTHS_RE}[A-Z]*\s+{YEAR_RE}|{YEAR_RE})\b")

# Skills inline "Category: items"
INLINE_SUBSECTION_RE = re.compile(r"^\s*(.{2,60}?)\s*:\s*(.+?)\s*$")

ONE_LINE_ENTRY_WITH_DATES_RE = re.compile(
    rf"^(?P<title>.+?)\s+(?P<meta>{MONTHS_RE}[A-Z]*\s+{YEAR_RE}\s*[\-\u2013\u2014]\s*(?:{MONTHS_RE}[A-Z]*\s+{YEAR_RE}|PRESENT|CURRENT))\s*$",
    re.IGNORECASE,
)
PIPE_ENTRY_RE = re.compile(r"^.{3,120}\s+\|\s+.{2,200}$")  # Project | Tech
DASHED_ROLE_COMPANY_RE = re.compile(r"^.{3,120}\s+[\-\u2010\u2011\u2012\u2013\u2014]\s+.{2,160}$")


def _normalize_line(line: str) -> str:
    line = line.replace("\u00A0", " ")
    line = re.sub(r"[ \t]+", " ", line).strip()
    # normalize weird dashes from PDF
    line = line.replace("-", "-").replace("–", "-").replace("—", "-")
    return line


def _only_punct(line: str) -> bool:
    return bool(line) and not any(ch.isalnum() for ch in line)


def _uppercase_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    upper = sum(1 for c in letters if c.isupper())
    return upper / max(1, len(letters))


def _normalize_heading_key(s: str) -> str:
    # tolerate weird “i” vs “I” extraction: PROFESSiONAL -> professional
    # also strip non-letters except spaces
    s2 = s.lower()
    s2 = re.sub(r"[^a-z\s]", "", s2)
    s2 = re.sub(r"\s+", " ", s2).strip()
    return s2


def _looks_like_section_title(line: str) -> bool:
    if not line:
        return False
    if len(line) > 60:
        return False

    key = _normalize_heading_key(line)
    if key in KNOWN_SECTIONS:
        return True

    # Heuristic: short, mostly uppercase, few words
    ratio = _uppercase_ratio(line)
    word_count = len(line.split())
    if 1 <= word_count <= 4 and ratio >= 0.80 and len(line) >= 4:
        if any(w.lower() in {"university", "college", "school"} for w in line.split()):
            return False
        if "@" in line or re.search(r"\b\d{3}[\)\- ]\d{3}", line):
            return False
        return True

    return False


def _is_bullet_line(line: str) -> bool:
    return bool(BULLET_PREFIX_RE.match(line))


def _strip_bullet(line: str) -> str:
    return BULLET_PREFIX_RE.sub("", line).strip()


def _looks_like_meta_date(line: str) -> bool:
    if not line:
        return False
    if DATE_RANGE_RE.search(line):
        return True
    if SINGLE_DATE_RE.fullmatch(line.strip(), re.IGNORECASE):
        return True
    if re.fullmatch(rf"(?i){YEAR_RE}\s*-\s*{YEAR_RE}", line.strip()):
        return True
    return False


def _split_title_and_meta_from_one_line(line: str) -> Optional[Dict[str, str]]:
    """
    If line ends with a recognizable date-range meta, split it out.
    """
    m = ONE_LINE_ENTRY_WITH_DATES_RE.match(line)
    if m:
        title = m.group("title").strip(" -|")
        meta = m.group("meta").strip()
        return {"title": title, "meta": meta}
    return None


def _looks_like_entry_header(line: str) -> bool:
    """
    Used inside sections like PROJECTS / EXPERIENCE to detect a subsection header.
    """
    if not line or len(line) > 180:
        return False

    if PIPE_ENTRY_RE.match(line):
        return True

    if DASHED_ROLE_COMPANY_RE.match(line) and _uppercase_ratio(line) >= 0.55:
        return True

    if _split_title_and_meta_from_one_line(line):
        return True

    # Often project titles are Title Case and short-ish
    # Avoid “W. P. Carey School...” type lines by checking for school/university keywords
    if 3 <= len(line) <= 90:
        if any(w.lower() in {"university", "college", "school"} for w in line.split()):
            return False
        # If it has a tech stack comma list and no bullet prefix, it's probably a header in projects
        if "|" in line or "," in line:
            return True

    return False


def extract_skeleton_from_pdf(pdf_path: str) -> Dict[str, Any]:
    raw = extract_text_from_pdf(pdf_path)
    lines = [_normalize_line(l) for l in raw.splitlines()]
    lines = [l for l in lines if l and not _only_punct(l)]

    # -------------------------
    # Header (top-of-resume)
    # -------------------------
    header_lines: List[str] = []
    i = 0
    while i < len(lines) and not _looks_like_section_title(lines[i]):
        header_lines.append(lines[i])
        i += 1

    sections: List[Dict[str, Any]] = []

    current_section_title: Optional[str] = None
    current_section_blocks: List[Dict[str, Any]] = []

    # For bullets that get split like:
    #   line: "•"
    #   line: "Did something..."
    pending_lone_bullet = False

    # Subsection state
    current_sub_title: Optional[str] = None
    current_sub_blocks: List[Dict[str, Any]] = []
    current_sub_meta: Optional[str] = None

    current_bullets: Optional[List[str]] = None  # applies inside current scope (subsection if open else section)

    def _target_blocks() -> List[Dict[str, Any]]:
        return current_sub_blocks if current_sub_title is not None else current_section_blocks

    def flush_bullets():
        nonlocal current_bullets
        if current_bullets is not None:
            _target_blocks().append({"type": "bullets", "items": current_bullets})
            current_bullets = None

    def flush_subsection():
        nonlocal current_sub_title, current_sub_blocks, current_sub_meta
        if current_sub_title is None:
            return
        flush_bullets()
        block: Dict[str, Any] = {"type": "subsection", "title": current_sub_title, "blocks": current_sub_blocks}
        if current_sub_meta:
            block["meta"] = current_sub_meta
        current_section_blocks.append(block)
        current_sub_title = None
        current_sub_blocks = []
        current_sub_meta = None

    def flush_section():
        nonlocal current_section_title, current_section_blocks
        if current_section_title is None:
            return
        flush_subsection()
        flush_bullets()
        sections.append({"title": current_section_title, "blocks": current_section_blocks})
        current_section_title = None
        current_section_blocks = []

    def open_subsection(title: str, meta: Optional[str] = None):
        nonlocal current_sub_title, current_sub_blocks, current_sub_meta
        flush_subsection()
        current_sub_title = title.strip()
        current_sub_blocks = []
        current_sub_meta = meta.strip() if meta else None

    while i < len(lines):
        line = lines[i]

        # Section title
        if _looks_like_section_title(line):
            flush_section()
            current_section_title = line.strip()
            current_section_blocks = []
            pending_lone_bullet = False
            i += 1
            continue

        # If we still haven't found a section title, treat as header spillover
        if current_section_title is None:
            header_lines.append(line)
            i += 1
            continue

        # Bullet split artifact handling
        if LONE_BULLET_RE.match(line):
            pending_lone_bullet = True
            i += 1
            continue

        # Real bullet lines
        if _is_bullet_line(line):
            pending_lone_bullet = False
            if current_bullets is None:
                current_bullets = []
            current_bullets.append(_strip_bullet(line))
            i += 1
            continue

        # If previous line was a lone bullet, treat this line as bullet content
        if pending_lone_bullet:
            pending_lone_bullet = False
            if current_bullets is None:
                current_bullets = []
            current_bullets.append(line)
            i += 1
            continue

        # Inline skills subsection: "Data & Analytics : SQL • Python ..."
        inline = INLINE_SUBSECTION_RE.match(line)
        if inline and len(inline.group(1).strip()) <= 40:
            left = inline.group(1).strip()
            right = inline.group(2).strip()
            # If we're already in a subsection, don't accidentally open nested subsections — treat as line.
            if current_sub_title is None:
                open_subsection(left)
                # store inline content as a line block (so you can recreate exactly)
                current_sub_blocks.append({"type": "line", "text": right})
                i += 1
                continue

        # Inside PROJECTS/EXPERIENCE-like sections, detect entry headers as subsections
        sec_key = _normalize_heading_key(current_section_title)
        in_entry_sections = sec_key in {
            "projects",
            "project experience",
            "professional experience",
            "work experience",
            "experience",
        }

        if in_entry_sections and _looks_like_entry_header(line):
            # If line includes trailing dates, split into title/meta
            split = _split_title_and_meta_from_one_line(line)
            if split:
                open_subsection(split["title"], split["meta"])
                i += 1
                continue

            # Otherwise open subsection with title=line, and if next line is meta date, attach it
            open_subsection(line)

            # Lookahead: if the next line is a meta date, consume it
            if i + 1 < len(lines) and _looks_like_meta_date(lines[i + 1]):
                current_sub_meta = lines[i + 1].strip()
                i += 2
                continue

            i += 1
            continue

        # Also: if we are currently inside a subsection and encounter a line that is just a date,
        # treat it as meta if meta isn't set yet.
        if current_sub_title is not None and current_sub_meta is None and _looks_like_meta_date(line):
            current_sub_meta = line.strip()
            i += 1
            continue

        # Default: normal text line
        flush_bullets()
        _target_blocks().append({"type": "line", "text": line})
        i += 1

    flush_section()

    style = {
        "bullet_char": "•",
        "header_line_count": len(header_lines),
        "section_count": len(sections),
    }

    return {
        "header_lines": header_lines,
        "sections": sections,
        "style": style,
    }