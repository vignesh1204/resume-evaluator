# backend/pdf_latex.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
import os
import re
import shutil
import subprocess
import tempfile


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
TEMPLATE_TEX_PATH = os.path.join(TEMPLATES_DIR, "template.tex")
RESUME_CLS_PATH = os.path.join(TEMPLATES_DIR, "resume.cls")


# -----------------------------
# LaTeX escaping (pdflatex-safe: ASCII + escaped specials)
# -----------------------------

# Unicode chars that pdflatex doesn't support → ASCII equivalents
_UNICODE_TO_ASCII = {
    "\u22c4": " | ",   # ⋄ (diamond operator) — common as separator
    "\u00b7": " ",     # · middle dot
    "\u2022": " ",     # • bullet (we use \item for bullets)
    "\u2013": "-",     # – en dash
    "\u2014": "--",    # — em dash
    "\u2018": "'",     # ‘
    "\u2019": "'",     # '
    "\u201c": '"',     # “
    "\u201d": '"',     # "
    "\u2026": "...",   # …
}

_LATEX_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_BOLD_TOKEN_RE = re.compile(r"(\\textbf\{[^{}]+\}|\*\*[^*]+\*\*|__[^_]+__)")


def _normalize_unicode_for_latex(s: str) -> str:
    """Replace Unicode that pdflatex can't handle (e.g. ⋄ U+22C4) with ASCII equivalents."""
    out = s
    for uc, replacement in _UNICODE_TO_ASCII.items():
        out = out.replace(uc, replacement)
    return out


def _latex_escape_plain(s: str) -> str:
    if not isinstance(s, str):
        return ""
    out = _normalize_unicode_for_latex(s)
    for k, v in _LATEX_ESCAPE_MAP.items():
        out = out.replace(k, v)
    return out


def latex_escape(s: str) -> str:
    """
    Escape LaTeX-special characters while preserving bold emphasis markers:
    - \\textbf{...}
    - **...**
    - __...__
    """
    if not isinstance(s, str):
        return ""
    parts = _BOLD_TOKEN_RE.split(s)
    out_parts: List[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith(r"\textbf{") and part.endswith("}"):
            inner = part[8:-1].strip()
            if inner:
                out_parts.append(r"{\bf " + _latex_escape_plain(inner) + r"}")
            continue
        if (part.startswith("**") and part.endswith("**")) or (part.startswith("__") and part.endswith("__")):
            inner = part[2:-2].strip()
            if inner:
                out_parts.append(r"{\bf " + _latex_escape_plain(inner) + r"}")
            continue
        out_parts.append(_latex_escape_plain(part))
    return "".join(out_parts)


class _KeywordBoldener:
    """
    Bold up to max_keywords unique keyword matches across the whole resume.
    Only bolds keywords already present in text (no content injection).
    """

    _FALLBACK = [
        "SQL", "Python", "RAG", "API", "APIs", "Tableau", "Power BI", "Snowflake",
        "React", "Spring Boot", "Kubernetes", "Docker", "AWS", "GraphQL",
        "PostgreSQL", "MongoDB", "LLM", "REST", "Selenium", "JUnit",
    ]

    def __init__(self, candidates: Optional[List[str]], max_keywords: int = 10):
        self.max_keywords = max_keywords
        self.used = set()
        ordered: List[str] = []
        for src in (candidates or []) + self._FALLBACK:
            kw = str(src or "").strip()
            if not kw:
                continue
            key = kw.lower()
            if key in self.used:
                continue
            self.used.add(key)
            ordered.append(kw)
        self.used.clear()
        self.keywords = sorted(ordered, key=len, reverse=True)

    def apply(self, text: str) -> str:
        if not text:
            return ""
        raw = text
        for kw in self.keywords:
            if len(self.used) >= self.max_keywords:
                break
            key = kw.lower()
            if key in self.used:
                continue
            pat = re.compile(rf"(?<![A-Za-z0-9])({re.escape(kw)})(?![A-Za-z0-9])", re.IGNORECASE)
            m = pat.search(raw)
            if not m:
                continue
            start, end = m.span(1)
            raw = raw[:start] + "@@BOPEN@@" + raw[start:end] + "@@BCLOSE@@" + raw[end:]
            self.used.add(key)

        escaped = latex_escape(raw)
        escaped = escaped.replace("@@BOPEN@@", r"{\bf ")
        escaped = escaped.replace("@@BCLOSE@@", "}")
        return escaped


# -----------------------------
# Apply section order + enabled
# -----------------------------

def apply_order_and_enabled(
    resume: Dict[str, Any],
    section_order: Optional[List[str]],
    enabled_section_ids: Optional[List[str]],
) -> Dict[str, Any]:
    if not isinstance(resume, dict):
        return resume

    sections = resume.get("sections", [])
    if not isinstance(sections, list):
        return resume

    enabled_set = set([str(x) for x in (enabled_section_ids or []) if str(x).strip()])

    by_id: Dict[str, Dict[str, Any]] = {}
    for s in sections:
        if isinstance(s, dict):
            sid = str(s.get("id", "")).strip()
            if sid:
                by_id[sid] = s

    ordered: List[Dict[str, Any]] = []
    if section_order:
        for sid in section_order:
            sid = str(sid).strip()
            if sid in by_id:
                ordered.append(by_id[sid])

    seen = set([str(s.get("id")) for s in ordered if isinstance(s, dict)])
    for s in sections:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id", "")).strip()
        if sid and sid not in seen:
            ordered.append(s)

    if enabled_set:
        ordered = [s for s in ordered if str(s.get("id", "")).strip() in enabled_set]

    resume["sections"] = ordered
    return resume


# -----------------------------
# Keyword injection (preserves section style)
# -----------------------------

# Section title substrings that suggest a "skills-like" section (any industry).
_SKILLS_SECTION_HINTS = ("skill", "tool", "technical", "competenc", "expertise", "growth", "proficien")


def _section_uses_inline_subsections(section: Dict[str, Any]) -> bool:
    """True if all subsections in this section are inline-only (line/meta only, no bullets)."""
    blocks = section.get("blocks", []) or []
    for b in blocks:
        if not isinstance(b, dict) or b.get("type") != "subsection":
            continue
        sub = b.get("blocks", []) or []
        for s in sub:
            if isinstance(s, dict) and s.get("type") == "bullets":
                return False
    return True


def inject_keywords_into_skeleton(
    resume: Dict[str, Any],
    keywords: List[str],
    *,
    subsection_title: str = "Keywords",
) -> Dict[str, Any]:
    """
    Adds a Keywords subsection to a skills-like section (Skills, Technical Skills,
    Growth Tools, etc.). Preserves that section's style: if subsections are
    inline (one line per category), add Keywords as one line; otherwise bullets.
    """
    if not isinstance(resume, dict):
        return resume

    keywords = [k.strip() for k in (keywords or []) if isinstance(k, str) and k.strip()]
    if not keywords:
        return resume

    sections = resume.get("sections", [])
    if not isinstance(sections, list):
        return resume

    skills_idx = None
    for i, s in enumerate(sections):
        if not isinstance(s, dict):
            continue
        title = str(s.get("title", "")).strip().lower()
        if any(hint in title for hint in _SKILLS_SECTION_HINTS):
            skills_idx = i
            break

    use_inline = True
    if skills_idx is not None:
        use_inline = _section_uses_inline_subsections(sections[skills_idx])

    if use_inline:
        keyword_block = {
            "type": "subsection",
            "title": subsection_title,
            "blocks": [{"type": "line", "text": ", ".join(keywords)}],
        }
    else:
        keyword_block = {
            "type": "subsection",
            "title": subsection_title,
            "blocks": [{"type": "bullets", "items": keywords}],
        }

    if skills_idx is None:
        new_sec = {
            "id": "keywords-1",
            "title": "Keywords",
            "enabled": True,
            "blocks": [keyword_block],
        }
        sections.insert(0, new_sec)
    else:
        blocks = sections[skills_idx].get("blocks", [])
        if not isinstance(blocks, list):
            blocks = []
            sections[skills_idx]["blocks"] = blocks

        replaced = False
        for j, b in enumerate(blocks):
            if isinstance(b, dict) and b.get("type") == "subsection":
                if str(b.get("title", "")).strip().lower() == subsection_title.lower():
                    blocks[j] = keyword_block
                    replaced = True
                    break
        if not replaced:
            blocks.append(keyword_block)

    resume["sections"] = sections
    return resume


# -----------------------------
# Skeleton -> LaTeX body using YOUR resume.cls helpers
# -----------------------------

def _subsection_is_inline_only(sub_blocks: List[Any]) -> bool:
    """True if subsection has only line/meta blocks (no bullets) — can render on one line."""
    if not sub_blocks:
        return False
    for b in sub_blocks:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "bullets":
            return False
    return True


def _subsection_inline_content(sub_blocks: List[Any]) -> str:
    """Join line and meta block texts with ', ' for one-line subsection rendering."""
    parts: List[str] = []
    for b in sub_blocks or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "line" or t == "meta":
            txt = str(b.get("text", "")).strip()
            if txt:
                parts.append(latex_escape(txt))
    return ", ".join(parts)


def _header_line(left: str, right: str, bold_left: bool, education_mode: bool) -> str:
    """
    Render a header row at slightly reduced font size:
    left text (bold or italic) + right-aligned meta.
    """
    if bold_left:
        left_tex = r"{\bf " + left + r"}"
    else:
        left_tex = left if education_mode else (r"{\em " + left + r"}")
    if right:
        return r"{\small " + left_tex + r" \hfill " + right + r"} \\"
    return r"{\small " + left_tex + r"} \\"


def _subsection_header_rows(
    subsection_title: str,
    sub_blocks: List[Any],
    *,
    education_mode: bool,
    boldener: Optional[_KeywordBoldener],
    enable_bullet_bold: bool,
) -> List[str]:
    """
    Render subsection header rows with flexible (left, right) pairing.
    Each (left, meta) pair is one row. Title row is bold, subsequent rows italic.
    All header rows use slightly smaller font.
    """
    out: List[str] = []

    if education_mode:
        edu_lines: List[str] = []
        edu_meta: List[str] = []
        has_bullets = False
        for blk in sub_blocks or []:
            if not isinstance(blk, dict):
                continue
            t = blk.get("type")
            if t == "line":
                txt = latex_escape(str(blk.get("text", "")).strip())
                if txt:
                    edu_lines.append(txt)
            elif t == "meta":
                txt = latex_escape(str(blk.get("text", "")).strip())
                if txt:
                    edu_meta.append(txt)
            elif t == "bullets":
                has_bullets = True

        if not has_bullets:
            degree = subsection_title if subsection_title else (edu_lines[0] if len(edu_lines) > 0 else "")
            college = edu_lines[0] if subsection_title else (edu_lines[1] if len(edu_lines) > 1 else "")
            date_range = edu_meta[0] if len(edu_meta) > 0 else ""
            location = edu_meta[1] if len(edu_meta) > 1 else ""

            row1 = " - ".join([x for x in [degree, date_range] if x])
            row2 = " - ".join([x for x in [college, location] if x])
            if row1:
                out.append(r"{\small {\bf " + row1 + r"}}")
            if row2:
                out.append(r"{\small " + row2 + r"}")
            return out

    current_left: Optional[str] = subsection_title if subsection_title else None
    left_is_title = bool(subsection_title)
    seen_bullets = False

    def _flush_left(bold: bool, with_break: bool = True) -> str:
        if bold:
            left_tex = r"{\bf " + current_left + r"}"
        else:
            left_tex = current_left if education_mode else (r"{\em " + current_left + r"}")
        row = r"{\small " + left_tex + r"}"
        return row + (r" \\" if with_break else "")

    for blk in sub_blocks or []:
        if not isinstance(blk, dict):
            continue
        t = blk.get("type")
        if t == "meta":
            meta_txt = latex_escape(str(blk.get("text", "")).strip())
            if current_left is not None:
                out.append(_header_line(current_left, meta_txt, left_is_title, education_mode))
                current_left = None
                left_is_title = False
            elif meta_txt:
                out.append(r"{\small " + meta_txt + r"} \\")
        elif t == "line":
            line_txt = latex_escape(str(blk.get("text", "")).strip())
            if not line_txt:
                continue
            if current_left is not None:
                out.append(_flush_left(left_is_title))
            current_left = line_txt
            left_is_title = False
        elif t == "bullets":
            seen_bullets = True
            if current_left is not None:
                # Avoid extra blank gap before list: no forced linebreak here.
                out.append(_flush_left(left_is_title, with_break=False))
                current_left = None
            out.append(r"\vspace{-3pt}")
            out.append(r"\begin{tightitemize}")
            for it in (blk.get("items") or []):
                if isinstance(it, str) and it.strip():
                    if enable_bullet_bold and boldener:
                        item_txt = boldener.apply(it.strip())
                    else:
                        item_txt = latex_escape(it.strip())
                    out.append(r"\item " + item_txt)
            out.append(r"\end{tightitemize}")
            out.append(r"\vspace{-3pt}")

    if current_left is not None and not seen_bullets:
        out.append(_flush_left(left_is_title))

    return out


def _education_rows_from_line(raw_line: str) -> List[str]:
    """
    Fallback formatter for education entries that arrive as a single line.
    Target shape:
      1) Degree - Date Range
      2) College Name - Location
    """
    text = str(raw_line or "").strip()
    if not text:
        return []

    # Split by commas first: usually [degree+date, college, location...]
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return []

    first = parts[0]
    college = parts[1] if len(parts) > 1 else ""
    location = ", ".join(parts[2:]) if len(parts) > 2 else ""

    # Find a month-year date range inside first part, then split degree/date.
    date_pat = re.compile(
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4}\s*-\s*"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4})",
        re.IGNORECASE,
    )
    m = date_pat.search(first)
    if m:
        date_range_raw = m.group(1).strip()
        degree_raw = (first[: m.start()] + first[m.end() :]).strip(" ,-")
    else:
        degree_raw = first
        date_range_raw = ""

    left1 = latex_escape(degree_raw)
    right1 = latex_escape(date_range_raw)
    left2 = latex_escape(college)
    right2 = latex_escape(location)

    out: List[str] = []
    if left1 or right1:
        if left1 and right1:
            out.append(r"{\small {\bf " + left1 + r"} \hfill " + right1 + r"} \\")
        elif left1:
            out.append(r"{\small {\bf " + left1 + r"}} \\")
        else:
            out.append(r"{\small " + right1 + r"} \\")
    if left2 or right2:
        if left2 and right2:
            out.append(r"{\small " + left2 + r" \hfill " + right2 + r"} \\")
        else:
            out.append(r"{\small " + (left2 or right2) + r"} \\")
    return out


def _education_rows_from_subsection(subsection_title: str, sub_blocks: List[Any]) -> List[str]:
    """
    Deterministic Education subsection renderer:
      1) Degree - Date Range
      2) College Name - Location
    """
    lines: List[str] = []
    metas: List[str] = []
    for blk in sub_blocks or []:
        if not isinstance(blk, dict):
            continue
        t = blk.get("type")
        if t == "line":
            txt = str(blk.get("text", "")).strip()
            if txt:
                lines.append(txt)
        elif t == "meta":
            txt = str(blk.get("text", "")).strip()
            if txt:
                metas.append(txt)

    # If the first line is a merged "degree+date, college, location" row, parse it directly.
    if lines and "," in lines[0]:
        parsed = _education_rows_from_line(lines[0])
        if parsed:
            return parsed

    degree_raw = subsection_title.strip() if subsection_title else ""
    date_raw = metas[0] if len(metas) > 0 else ""
    college_raw = lines[0] if len(lines) > 0 else ""
    location_raw = metas[1] if len(metas) > 1 else ""

    # Fallback: when degree/date are merged in first line without subsection title.
    if not degree_raw and lines:
        merged = _education_rows_from_line(lines[0])
        if merged:
            if len(lines) > 1:
                row1 = merged[0]
                row2_college = latex_escape(lines[1])
                row2_location = location_raw
                row2_location_esc = latex_escape(row2_location)
                if row2_college and row2_location_esc:
                    row2 = r"{\small " + row2_college + r" \hfill " + row2_location_esc + r"} \\"
                else:
                    row2 = r"{\small " + (row2_college or row2_location_esc) + r"} \\"
                return [row1 + r" \\", row2] if (row2_college or row2_location_esc) else merged
            return merged

    left1 = latex_escape(degree_raw)
    right1 = latex_escape(date_raw)
    left2 = latex_escape(college_raw)
    right2 = latex_escape(location_raw)
    out: List[str] = []
    if left1 or right1:
        if left1 and right1:
            out.append(r"{\small {\bf " + left1 + r"} \hfill " + right1 + r"} \\")
        elif left1:
            out.append(r"{\small {\bf " + left1 + r"}} \\")
        else:
            out.append(r"{\small " + right1 + r"} \\")
    if left2 or right2:
        if left2 and right2:
            out.append(r"{\small " + left2 + r" \hfill " + right2 + r"} \\")
        else:
            out.append(r"{\small " + (left2 or right2) + r"} \\")
    return out


def _blocks_to_latex(
    blocks: List[Any],
    *,
    section_title: str = "",
    boldener: Optional[_KeywordBoldener] = None,
) -> List[str]:
    out: List[str] = []
    section_lower = section_title.lower()
    section_is_skills = any(hint in section_lower for hint in _SKILLS_SECTION_HINTS)
    section_is_education = "education" in section_lower
    enable_bullet_bold = not section_is_skills
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type")

        if t == "line":
            raw_txt = str(b.get("text", "")).strip()
            if section_is_education:
                edu_rows = _education_rows_from_line(raw_txt)
                if edu_rows:
                    out.extend(edu_rows)
                    continue
            txt = latex_escape(raw_txt)
            if txt:
                out.append(txt + r" \\")
        elif t == "meta":
            txt = latex_escape(str(b.get("text", "")).strip())
            if txt:
                out.append(r"{" + txt + r"}")
        elif t == "bullets":
            raw_items = b.get("items", []) or []
            items = []
            for x in raw_items:
                if not isinstance(x, str) or not x.strip():
                    continue
                if enable_bullet_bold and boldener:
                    items.append(boldener.apply(str(x).strip()))
                else:
                    items.append(latex_escape(str(x).strip()))
            if items:
                out.append(r"\vspace{-3pt}")
                out.append(r"\begin{tightitemize}")
                for it in items:
                    out.append(r"\item " + it)
                out.append(r"\end{tightitemize}")
                out.append(r"\vspace{-3pt}")
        elif t == "subsection":
            title = latex_escape(str(b.get("title", "")).strip())
            sub_blocks = b.get("blocks", []) or []
            if section_is_education:
                edu_rows = _education_rows_from_subsection(str(b.get("title", "")).strip(), sub_blocks)
                if edu_rows:
                    out.extend(edu_rows)
                    continue
            if title and _subsection_is_inline_only(sub_blocks):
                content = _subsection_inline_content(sub_blocks)
                if content:
                    out.append(r"{\small {\bf " + title + r"} " + content + r"} \\")
            else:
                out.extend(
                    _subsection_header_rows(
                        title,
                        sub_blocks,
                        education_mode=("education" in section_title.lower()),
                        boldener=boldener,
                        enable_bullet_bold=enable_bullet_bold,
                    )
                )
        else:
            continue

    return out


def skeleton_to_latex_body(
    resume: Dict[str, Any],
    *,
    boldener: Optional[_KeywordBoldener] = None,
    stretch_sections: bool = False,
) -> str:
    """
    Builds LaTeX body from the resume skeleton. Structure is preserved: section
    and subsection titles, inline vs bullets, and block layout come from the
    skeleton (user's resume). We only apply visual style (font, spacing, rules)
    via resume.cls; no hardcoded section names or layout.
    Keeps natural section flow with compact spacing (no forced \\vfill gaps).
    """
    lines: List[str] = []

    sections = resume.get("sections", []) if isinstance(resume, dict) else []
    if not isinstance(sections, list):
        sections = []

    rendered = 0
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = latex_escape(str(sec.get("title", "")).strip())
        if not title:
            continue

        if stretch_sections and rendered > 0:
            lines.append(r"\vspace{0pt plus 1fill}")

        lines.append(r"\begin{rSection}{" + title + r"}")

        blocks = sec.get("blocks", []) or []
        if isinstance(blocks, list):
            lines.extend(_blocks_to_latex(blocks, section_title=title, boldener=boldener))

        lines.append(r"\end{rSection}")
        rendered += 1

    return "\n".join(lines).strip() + "\n"


# -----------------------------
# Template placeholder injection (YOUR tokens)
# -----------------------------

TOKEN_NAME = "%%__NAME__%%"
TOKEN_CONTACT = "%%__CONTACT__%%"
TOKEN_BODY = "%%__BODY__%%"
TOKEN_ITEMSEP = "%%__ITEMSEP__%%"
TOKEN_TOPSEP = "%%__TOPSEP__%%"
TOKEN_SECTION_SKIP = "%%__SECTION_SKIP__%%"
TOKEN_SECTION_LINE_SKIP = "%%__SECTION_LINE_SKIP__%%"
TOKEN_ADDRESS_SKIP = "%%__ADDRESS_SKIP__%%"
TOKEN_AFTER_RULE_SKIP = "%%__AFTER_RULE_SKIP__%%"
TOKEN_TOP_PULL = "%%__TOP_PULL__%%"


def _resume_density_score(resume: Dict[str, Any]) -> int:
    """Estimate content density to choose stretch/compact spacing profile."""
    score = 0
    sections = resume.get("sections", []) if isinstance(resume, dict) else []
    if not isinstance(sections, list):
        return score

    for sec in sections:
        if not isinstance(sec, dict):
            continue
        score += 3
        blocks = sec.get("blocks", []) or []
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t in ("line", "meta"):
                score += 1
            elif t == "bullets":
                items = b.get("items", []) or []
                if isinstance(items, list):
                    score += len([x for x in items if isinstance(x, str) and x.strip()]) * 2
            elif t == "subsection":
                score += 2
                sub = b.get("blocks", []) or []
                if not isinstance(sub, list):
                    continue
                for sb in sub:
                    if not isinstance(sb, dict):
                        continue
                    st = sb.get("type")
                    if st in ("line", "meta"):
                        score += 1
                    elif st == "bullets":
                        items = sb.get("items", []) or []
                        if isinstance(items, list):
                            score += len([x for x in items if isinstance(x, str) and x.strip()]) * 2
    return score


def _layout_profile(resume: Dict[str, Any]) -> Dict[str, Any]:
    density = _resume_density_score(resume)
    if density <= 28:
        return {
            "itemsep": "0pt plus 0.6pt minus 0.2pt",
            "topsep": "1pt plus 0.8pt minus 0.2pt",
            "section_skip": "1pt plus 2pt minus 0.5pt",
            "section_line_skip": "4pt plus 1pt minus 0.5pt",
            "address_skip": "1pt",
            "after_rule_skip": "1pt plus 0.8pt minus 0.2pt",
            "top_pull": "-2mm",
            "stretch_sections": True,
        }
    if density >= 62:
        return {
            "itemsep": "-2pt plus 0.2pt minus 0.6pt",
            "topsep": "0pt",
            "section_skip": "0pt",
            "section_line_skip": "3pt",
            "address_skip": "0pt",
            "after_rule_skip": "0.5pt",
            "top_pull": "-3mm",
            "stretch_sections": False,
        }
    return {
        "itemsep": "-1pt plus 0.3pt minus 0.4pt",
        "topsep": "0.5pt plus 0.3pt minus 0.2pt",
        "section_skip": "0.5pt plus 0.8pt minus 0.3pt",
        "section_line_skip": "4pt",
        "address_skip": "1pt",
        "after_rule_skip": "1pt",
        "top_pull": "-3mm",
        "stretch_sections": False,
    }

def _clean_header_text(s: str) -> str:
    """Clean a header line: strip braces, normalize separators, remove noise."""
    out = s.replace("{", "").replace("}", "")
    out = _normalize_unicode_for_latex(out)
    # Escape only the truly special chars (not { } since we stripped them)
    for ch, esc in (("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                    ("_", r"\_"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")):
        out = out.replace(ch, esc)
    return out.strip()


def _looks_like_name(s: str) -> bool:
    """Heuristic: a name line is mostly alphabetic words, no @ or digits-heavy."""
    stripped = s.strip()
    if "@" in stripped or stripped.startswith("(") or stripped.startswith("+"):
        return False
    alpha_count = sum(1 for c in stripped if c.isalpha())
    return alpha_count > len(stripped) * 0.5


def _derive_name_and_contact(resume: Dict[str, Any]) -> tuple[str, str]:
    """
    Pulls from resume['header']['lines']:
      - Finds the name line (mostly alphabetic, no phone/email markers)
      - Everything else is contact info joined with ' \\\\ ' (cls renders \\\\ as diamond)
    """
    header = resume.get("header", {}) if isinstance(resume, dict) else {}
    if not isinstance(header, dict):
        return ("", "")

    lines = header.get("lines", [])
    if not isinstance(lines, list):
        return ("", "")

    clean = [_clean_header_text(str(x)) for x in lines if isinstance(x, str) and str(x).strip()]
    if not clean:
        return ("", "")

    name_idx = 0
    for i, line in enumerate(clean):
        if _looks_like_name(line):
            name_idx = i
            break

    name = clean[name_idx]
    contact_parts = [l for j, l in enumerate(clean) if j != name_idx]
    contact = r" \\ ".join(contact_parts)
    return (name, contact)


def render_main_tex_from_template(
    resume: Dict[str, Any],
    *,
    highlight_keywords: Optional[List[str]] = None,
) -> str:
    if not os.path.exists(TEMPLATE_TEX_PATH):
        raise FileNotFoundError(f"Missing template.tex at: {TEMPLATE_TEX_PATH}")
    if not os.path.exists(RESUME_CLS_PATH):
        raise FileNotFoundError(f"Missing resume.cls at: {RESUME_CLS_PATH}")

    with open(TEMPLATE_TEX_PATH, "r", encoding="utf-8") as f:
        template_tex = f.read()

    profile = _layout_profile(resume)
    boldener = _KeywordBoldener(highlight_keywords, max_keywords=10)
    body = skeleton_to_latex_body(
        resume,
        boldener=boldener,
        stretch_sections=bool(profile.get("stretch_sections", False)),
    )
    name, contact = _derive_name_and_contact(resume)

    # Replace tokens exactly as provided
    out = template_tex.replace(TOKEN_NAME, name)
    out = out.replace(TOKEN_CONTACT, contact)
    out = out.replace(TOKEN_BODY, body)
    out = out.replace(TOKEN_ITEMSEP, str(profile["itemsep"]))
    out = out.replace(TOKEN_TOPSEP, str(profile["topsep"]))
    out = out.replace(TOKEN_SECTION_SKIP, str(profile["section_skip"]))
    out = out.replace(TOKEN_SECTION_LINE_SKIP, str(profile["section_line_skip"]))
    out = out.replace(TOKEN_ADDRESS_SKIP, str(profile["address_skip"]))
    out = out.replace(TOKEN_AFTER_RULE_SKIP, str(profile["after_rule_skip"]))
    out = out.replace(TOKEN_TOP_PULL, str(profile["top_pull"]))

    # Guard: make sure body token existed
    if TOKEN_BODY in template_tex and TOKEN_BODY in out:
        # If token still present, replacement failed somehow
        raise RuntimeError("Failed to inject %%__BODY__%% into template.tex")

    return out


# -----------------------------
# Compile LaTeX -> PDF bytes
# -----------------------------

def compile_pdf_from_skeleton(
    resume: Dict[str, Any],
    *,
    highlight_keywords: Optional[List[str]] = None,
) -> bytes:
    main_tex = render_main_tex_from_template(resume, highlight_keywords=highlight_keywords)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy resume.cls because template references \documentclass{resume}
        shutil.copy2(RESUME_CLS_PATH, os.path.join(tmpdir, "resume.cls"))

        tex_path = os.path.join(tmpdir, "main.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(main_tex)

        # Ensure pdflatex exists
        if shutil.which("pdflatex") is None:
            raise RuntimeError("pdflatex not found. Install TeX (MacTeX/BasicTeX) and ensure pdflatex is on PATH.")

        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]

        # Run twice for stable layout
        for _ in range(2):
            p = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError(
                    "pdflatex failed:\n"
                    + (p.stdout[-2000:] if p.stdout else "")
                    + "\n"
                    + (p.stderr[-2000:] if p.stderr else "")
                )

        pdf_path = os.path.join(tmpdir, "main.pdf")
        if not os.path.exists(pdf_path):
            raise RuntimeError("PDF not produced by pdflatex")

        with open(pdf_path, "rb") as f:
            return f.read()