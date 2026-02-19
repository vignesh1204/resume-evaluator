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


def _normalize_unicode_for_latex(s: str) -> str:
    """Replace Unicode that pdflatex can't handle (e.g. ⋄ U+22C4) with ASCII equivalents."""
    out = s
    for uc, replacement in _UNICODE_TO_ASCII.items():
        out = out.replace(uc, replacement)
    return out


def latex_escape(s: str) -> str:
    if not isinstance(s, str):
        return ""
    out = _normalize_unicode_for_latex(s)
    for k, v in _LATEX_ESCAPE_MAP.items():
        out = out.replace(k, v)
    return out


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
        return r"{\small " + left_tex + r" \hfill " + right + r"}"
    return r"{\small " + left_tex + r"}"


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
    current_left: Optional[str] = subsection_title if subsection_title else None
    left_is_title = bool(subsection_title)
    seen_bullets = False

    def _flush_left(bold: bool) -> str:
        if bold:
            left_tex = r"{\bf " + current_left + r"}"
        else:
            left_tex = current_left if education_mode else (r"{\em " + current_left + r"}")
        return r"{\small " + left_tex + r"}"

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
                out.append(r"{\small " + meta_txt + r"}")
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
                out.append(_flush_left(left_is_title))
                current_left = None
            out.append(r"\begin{tightitemize}")
            for it in (blk.get("items") or []):
                if isinstance(it, str) and it.strip():
                    if enable_bullet_bold and boldener:
                        item_txt = boldener.apply(it.strip())
                    else:
                        item_txt = latex_escape(it.strip())
                    out.append(r"\item " + item_txt)
            out.append(r"\end{tightitemize}")

    if current_left is not None and not seen_bullets:
        out.append(_flush_left(left_is_title))

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
    enable_bullet_bold = not section_is_skills
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type")

        if t == "line":
            txt = latex_escape(str(b.get("text", "")).strip())
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
                out.append(r"\begin{tightitemize}")
                for it in items:
                    out.append(r"\item " + it)
                out.append(r"\end{tightitemize}")
        elif t == "subsection":
            title = latex_escape(str(b.get("title", "")).strip())
            sub_blocks = b.get("blocks", []) or []
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


def skeleton_to_latex_body(resume: Dict[str, Any], *, boldener: Optional[_KeywordBoldener] = None) -> str:
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

    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = latex_escape(str(sec.get("title", "")).strip())
        if not title:
            continue

        lines.append(r"\begin{rSection}{" + title + r"}")

        blocks = sec.get("blocks", []) or []
        if isinstance(blocks, list):
            lines.extend(_blocks_to_latex(blocks, section_title=title, boldener=boldener))

        lines.append(r"\end{rSection}")

    return "\n".join(lines).strip() + "\n"


# -----------------------------
# Template placeholder injection (YOUR tokens)
# -----------------------------

TOKEN_NAME = "%%__NAME__%%"
TOKEN_CONTACT = "%%__CONTACT__%%"
TOKEN_BODY = "%%__BODY__%%"

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

    boldener = _KeywordBoldener(highlight_keywords, max_keywords=10)
    body = skeleton_to_latex_body(resume, boldener=boldener)
    name, contact = _derive_name_and_contact(resume)

    # Replace tokens exactly as provided
    out = template_tex.replace(TOKEN_NAME, name)
    out = out.replace(TOKEN_CONTACT, contact)
    out = out.replace(TOKEN_BODY, body)

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