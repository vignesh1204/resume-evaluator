import os
import re
import json
import tempfile
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateSyntaxError
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from openai import OpenAI

# ----------------------------
# App setup
# ----------------------------
app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
API_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.2")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
TEMPLATE_TEX_PATH = os.path.join(TEMPLATES_DIR, "template.tex")
RESUME_CLS_PATH = os.path.join(TEMPLATES_DIR, "resume.cls")


# ----------------------------
# Utilities
# ----------------------------
def _safe_int(x: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return default


def _strip_control_chars(s: str) -> str:
    return "".join(ch for ch in s if ch == "\n" or ch == "\t" or ord(ch) >= 32)


def _extract_first_json(text: str) -> Dict[str, Any]:
    text = _strip_control_chars(text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model output did not contain a JSON object.")

    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except Exception as e:
        raise ValueError(f"Failed to parse JSON from model output: {e}")


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        s = str(it).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _clean_bullets(x: Any) -> List[str]:
    """
    Bullet sanitizer that avoids LaTeX itemize crashes:
    - ensures list[str]
    - strips empties
    - flattens accidental nested lists
    """
    if not isinstance(x, list):
        return []
    out: List[str] = []
    for b in x:
        if b is None:
            continue
        if isinstance(b, list):
            for bb in b:
                if bb is None:
                    continue
                s = str(bb).strip()
                if s:
                    out.append(s)
            continue
        s = str(b).strip()
        if s:
            out.append(s)
    return out


def derive_section_ids(doc: Dict[str, Any]) -> List[str]:
    """
    Convenience for frontend: get section ids in order from canonical doc.
    """
    if not isinstance(doc, dict):
        return []
    sections = doc.get("sections")
    if not isinstance(sections, list):
        return []
    ids = []
    for s in sections:
        if isinstance(s, dict) and s.get("id") is not None:
            sid = str(s["id"]).strip()
            if sid:
                ids.append(sid)
    return ids


# ----------------------------
# Canonical schema enforcement
# header + sections[]
# ----------------------------
def ensure_canonical_resume(doc: dict) -> dict:
    """
    Canonical schema:
      {
        "header": {"name": str, "contact_lines": [str,...]},
        "sections": [
          {"id": str, "title": str, "type": "paragraph"|"entries", ...}
        ]
      }

    This fills safe defaults so template rendering never crashes.
    Also ensures bullets are safe so LaTeX doesn't throw "missing \\item".
    """
    if not isinstance(doc, dict):
        doc = {}

    header = doc.get("header") if isinstance(doc.get("header"), dict) else {}
    name = header.get("name") or doc.get("name") or "Resume"

    contact_lines = header.get("contact_lines")
    if not isinstance(contact_lines, list):
        # Allow older header formats
        contact_lines = []
        for k in ["phone", "email", "location"]:
            v = header.get(k)
            if v:
                contact_lines.append(str(v))

    out: Dict[str, Any] = {
        "header": {
            "name": str(name),
            "contact_lines": [str(x) for x in contact_lines if x is not None and str(x).strip()],
        },
        "sections": [],
    }

    sections = doc.get("sections")
    if not isinstance(sections, list):
        sections = []

    norm_sections: List[Dict[str, Any]] = []
    for s in sections:
        if not isinstance(s, dict):
            continue

        sid = s.get("id") or s.get("title") or "section"
        title = s.get("title") or ""
        stype = str(s.get("type") or "entries").strip().lower()
        if stype not in ("paragraph", "entries"):
            stype = "entries"

        ns: Dict[str, Any] = {"id": str(sid), "title": str(title), "type": stype}

        if stype == "paragraph":
            ns["paragraph"] = str(s.get("paragraph") or "").strip()
            if not ns["paragraph"]:
                continue
        else:
            entries = s.get("entries")
            if not isinstance(entries, list):
                entries = []

            norm_entries: List[Dict[str, Any]] = []
            for e in entries:
                if not isinstance(e, dict):
                    continue

                entry = {
                    "heading_left": str(e.get("heading_left") or ""),
                    "heading_right": str(e.get("heading_right") or ""),
                    "subheading_left": str(e.get("subheading_left") or ""),
                    "subheading_right": str(e.get("subheading_right") or ""),
                    "bullets": _clean_bullets(e.get("bullets")),
                }

                # IMPORTANT:
                # If an entry has no bullets and also has no headings, drop it.
                # This prevents generating empty itemize or empty blocks.
                has_any_heading = (
                    entry["heading_left"].strip()
                    or entry["heading_right"].strip()
                    or entry["subheading_left"].strip()
                    or entry["subheading_right"].strip()
                )
                if (not entry["bullets"]) and (not has_any_heading):
                    continue

                norm_entries.append(entry)

            ns["entries"] = norm_entries

            # If after cleanup we have zero entries, skip section
            if len(norm_entries) == 0:
                continue

        norm_sections.append(ns)

    out["sections"] = norm_sections
    return out


def reorder_sections(doc: dict, section_order: List[str]) -> dict:
    """
    Reorder doc["sections"] according to section_order (list of section IDs).
    Unmentioned sections are appended after.
    """
    if not isinstance(doc, dict):
        return doc
    if not isinstance(doc.get("sections"), list):
        return doc
    if not isinstance(section_order, list) or not section_order:
        return doc

    order = [str(x) for x in section_order if str(x).strip()]
    sections = doc["sections"]

    by_id = {}
    for s in sections:
        if isinstance(s, dict) and s.get("id") is not None:
            by_id[str(s["id"])] = s

    new_sections = []
    used = set()

    for sid in order:
        if sid in by_id:
            new_sections.append(by_id[sid])
            used.add(sid)

    for s in sections:
        sid = str(s.get("id")) if isinstance(s, dict) and s.get("id") is not None else None
        if sid is None or sid not in used:
            new_sections.append(s)

    doc["sections"] = new_sections
    return doc

def filter_sections(doc: dict, enabled_section_ids: List[str]) -> dict:
    """
    Keep only sections whose id is in enabled_section_ids.
    If enabled_section_ids is empty or not provided, keep all.
    """
    if not isinstance(doc, dict):
        return doc
    if not isinstance(doc.get("sections"), list):
        return doc
    if not isinstance(enabled_section_ids, list) or not enabled_section_ids:
        return doc

    keep = set(str(x) for x in enabled_section_ids if str(x).strip())
    doc["sections"] = [
        s for s in doc["sections"]
        if isinstance(s, dict) and str(s.get("id", "")).strip() in keep
    ]
    return doc


def apply_keywords_canonical(doc: dict, keywords: List[str], keyword_count: int) -> dict:
    """
    Deterministically inject top-N keywords into a canonical resume.

    Strategy:
    - Choose top N deduped keywords.
    - Find a "Skills" section:
        - match id == "skills" OR title contains "skill"
    - If found:
        - if paragraph: append "Keywords: ..."
        - if entries: add an entry or add a bullet
    - If not found:
        - create a Skills paragraph section near top (after Summary if present).
    - Add trace field: doc["keywords_added"] = [...]
    """
    doc = json.loads(json.dumps(doc))  # deep copy
    keyword_count = max(3, min(10, int(keyword_count)))
    chosen = _dedupe_preserve_order(keywords)[:keyword_count]
    doc["keywords_added"] = chosen

    if not chosen:
        return doc

    def is_skills_section(s: dict) -> bool:
        sid = str(s.get("id", "")).lower()
        title = str(s.get("title", "")).lower()
        return sid == "skills" or "skill" in title

    sections = doc.get("sections")
    if not isinstance(sections, list):
        sections = []
        doc["sections"] = sections

    skills_idx = None
    for i, s in enumerate(sections):
        if isinstance(s, dict) and is_skills_section(s):
            skills_idx = i
            break

    payload_text = "Keywords: " + ", ".join(chosen)

    if skills_idx is None:
        # Insert after Summary if present, else near top
        insert_at = 0
        for i, s in enumerate(sections):
            if isinstance(s, dict) and str(s.get("id", "")).lower() == "summary":
                insert_at = i + 1
                break

        sections.insert(
            insert_at,
            {"id": "skills", "title": "Skills", "type": "paragraph", "paragraph": payload_text},
        )
        return doc

    skills = sections[skills_idx]
    stype = str(skills.get("type") or "entries").lower()

    if stype == "paragraph":
        p = str(skills.get("paragraph") or "").strip()
        skills["paragraph"] = (p + "  " + payload_text).strip() if p else payload_text
        return doc

    # entries
    entries = skills.get("entries")
    if not isinstance(entries, list):
        entries = []
        skills["entries"] = entries

    if len(entries) == 0:
        entries.append(
            {
                "heading_left": "",
                "heading_right": "",
                "subheading_left": "",
                "subheading_right": "",
                "bullets": [payload_text],
            }
        )
    else:
        b = entries[0].get("bullets")
        if not isinstance(b, list):
            b = []
            entries[0]["bullets"] = b
        b.append(payload_text)
        entries[0]["bullets"] = _clean_bullets(b)

    return doc


# ----------------------------
# (Optional) JD extraction
# ----------------------------
def try_extract_jd_from_link(url: str) -> Tuple[bool, str]:
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        return False, ""

    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or not r.text:
            return False, ""
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        text = soup.get_text(separator="\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) < 800:
            return False, ""
        return True, text
    except Exception:
        return False, ""


# ----------------------------
# LaTeX PDF generation
# ----------------------------
def latex_escape(value: Any) -> str:
    if value is None:
        return ""
    s = str(value)
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for a, b in replacements:
        s = s.replace(a, b)
    return s


def render_latex_from_canonical(canonical_doc: Dict[str, Any]) -> str:
    if not os.path.exists(TEMPLATE_TEX_PATH):
        raise FileNotFoundError(f"Missing template.tex at {TEMPLATE_TEX_PATH}")

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        # Prevent LaTeX {#1} from being parsed as Jinja comments
        comment_start_string="((#",
        comment_end_string="#))",
    )
    env.filters["latex_escape"] = latex_escape

    template = env.get_template("template.tex")

    try:
        ctx = ensure_canonical_resume(canonical_doc)
        return template.render(**ctx)
    except TemplateSyntaxError as e:
        raise RuntimeError(f"Jinja template syntax error at line {e.lineno}: {e.message}")


def compile_latex_to_pdf(tex_content: str) -> bytes:
    """
    Compile LaTeX and return PDF bytes.

    IMPORTANT:
    Some resume.cls templates can cause pdflatex to return non-zero even though
    a PDF is produced. We accept the PDF if it exists.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        pdf_path = os.path.join(tmpdir, "resume.pdf")

        # copy resume.cls if present
        if os.path.exists(RESUME_CLS_PATH):
            cls_dest = os.path.join(tmpdir, "resume.cls")
            with open(RESUME_CLS_PATH, "rb") as src, open(cls_dest, "wb") as dst:
                dst.write(src.read())

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        last_stdout = ""
        last_stderr = ""
        for _ in range(2):
            p = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "resume.tex"],
                cwd=tmpdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            last_stdout = p.stdout or ""
            last_stderr = p.stderr or ""

            if p.returncode != 0:
                # Accept PDF if produced anyway
                if os.path.exists(pdf_path):
                    break
                raise RuntimeError(
                    "LaTeX compilation failed.\n"
                    f"STDOUT:\n{last_stdout}\n\nSTDERR:\n{last_stderr}"
                )

        if not os.path.exists(pdf_path):
            raise RuntimeError(
                "PDF was not produced by pdflatex.\n"
                f"STDOUT:\n{last_stdout}\n\nSTDERR:\n{last_stderr}"
            )

        with open(pdf_path, "rb") as f:
            return f.read()


# ----------------------------
# OpenAI call (canonical output)
# ----------------------------
def call_llm_for_evaluation_canonical(
    resume_text: str,
    jd_text: str,
    changes_max: int = 5,
    keyword_suggestions_max: int = 10,
) -> Dict[str, Any]:
    """
    SINGLE call returns:
      - ats_score
      - optimized_ats_score
      - changes (exactly N)
      - keywords_suggested (up to M)
      - optimized_resume_canonical (header + sections[])
    """

    instructions = f"""
You are an ATS resume evaluator and resume optimizer.

Inputs:
1) RESUME_TEXT: plain text extracted from a resume PDF
2) JOB_DESCRIPTION: plain text of the job description

Tasks:
A) Compute ATS score of the original resume vs the job description (0-100).
B) Provide EXACTLY {changes_max} high-impact improvements.
C) Provide up to {keyword_suggestions_max} keywords/phrases to add (ranked, deduplicated).
D) Produce OPTIMIZED_RESUME_CANONICAL as a canonical structured resume that works for ANY resume type (tech or non-tech).
E) Compute OPTIMIZED_ATS_SCORE for the optimized resume.

Return ONLY valid JSON (no markdown, no extra text). Schema must match exactly:

{{
  "ats_score": <integer 0-100>,
  "optimized_ats_score": <integer 0-100>,
  "changes": [
    {{
      "type": "Keywords|Bullets|Formatting|Structure|Experience|Projects|Skills|Other",
      "title": "<short title>",
      "detail": "<1-3 sentences, concrete action>",
      "priority": "High|Medium|Low"
    }}
    ... exactly {changes_max} items
  ],
  "keywords_suggested": ["<keyword1>", "<keyword2>", ... up to {keyword_suggestions_max}],
  "optimized_resume_canonical": {{
    "header": {{
      "name": "<full name or 'Resume'>",
      "contact_lines": ["<line1>", "<line2>", "..."]
    }},
    "sections": [
      {{
        "id": "<stable id like summary|skills|experience|education|projects|certifications|...>",
        "title": "<section title>",
        "type": "paragraph",
        "paragraph": "<text>"
      }},
      {{
        "id": "<stable id>",
        "title": "<section title>",
        "type": "entries",
        "entries": [
          {{
            "heading_left": "<left heading>",
            "heading_right": "<right heading>",
            "subheading_left": "<left subheading>",
            "subheading_right": "<right subheading>",
            "bullets": ["<bullet1>", "<bullet2>"]
          }}
        ]
      }}
    ]
  }}
}}

Rules:
- "changes" MUST be exactly {changes_max}.
- keywords_suggested must be ranked (most important first) and deduplicated.
- Canonical resume must not omit required keys. Use empty strings/lists if needed.
"""

    user_input = f"""
RESUME_TEXT:
{resume_text}

JOB_DESCRIPTION:
{jd_text}
"""

    resp = client.responses.create(
        model=API_MODEL,
        instructions=instructions.strip(),
        input=user_input.strip(),
    )

    data = _extract_first_json(resp.output_text)
    return data


# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/extract")
def extract():
    data = request.get_json() or {}
    link = (data.get("job_description_link") or "").strip()
    if not link:
        return jsonify({"error": "job_description_link is required"}), 400

    ok, text = try_extract_jd_from_link(link)
    if not ok:
        return jsonify(
            {"warning": "Could not extract job description from the link. Please paste the job description text."}
        ), 422

    return jsonify({"job_description": text})


@app.post("/evaluate")
def evaluate():
    data = request.get_json() or {}

    resume_json = data.get("resume_json") or {}
    resume_text = (resume_json.get("raw_text") or "").strip()

    jd_text = (data.get("job_description_text") or "").strip()
    jd_link = (data.get("job_description_link") or "").strip()

    changes_max = _safe_int(data.get("changes_max"), 5) or 5
    keyword_suggestions_max = _safe_int(data.get("keyword_suggestions_max"), 10) or 10

    if not resume_text:
        return jsonify({"error": "resume_json.raw_text is required"}), 400

    if not jd_text:
        if not jd_link:
            return jsonify({"error": "Provide either job_description_text or job_description_link"}), 400
        ok, extracted = try_extract_jd_from_link(jd_link)
        if not ok:
            return jsonify(
                {"warning": "Could not extract job description from the link. Please paste the job description text."}
            ), 422
        jd_text = extracted

    try:
        llm_out = call_llm_for_evaluation_canonical(
            resume_text=resume_text,
            jd_text=jd_text,
            changes_max=changes_max,
            keyword_suggestions_max=keyword_suggestions_max,
        )

        ats_score = _safe_int(llm_out.get("ats_score"), None)
        optimized_ats_score = _safe_int(llm_out.get("optimized_ats_score"), None)

        changes = llm_out.get("changes") or []
        if not isinstance(changes, list):
            changes = []
        changes = changes[:changes_max]

        keywords = llm_out.get("keywords_suggested") or []
        if not isinstance(keywords, list):
            keywords = []
        keywords = _dedupe_preserve_order([str(k) for k in keywords])[:keyword_suggestions_max]

        optimized_resume_canonical = llm_out.get("optimized_resume_canonical") or {}
        optimized_resume_canonical = ensure_canonical_resume(optimized_resume_canonical)

        return jsonify(
            {
                "ats_score": ats_score,
                "optimized_ats_score": optimized_ats_score,
                "changes": changes,
                "keywords_suggested": keywords,
                "optimized_resume_canonical": optimized_resume_canonical,
                # helpful for frontend ordering UI
                "section_ids": derive_section_ids(optimized_resume_canonical),
            }
        )

    except Exception as e:
        return jsonify({"error": f"Evaluation failed: {str(e)}"}), 500


@app.post("/generate_pdf")
def generate_pdf():
    data = request.get_json() or {}

    resume_canonical = data.get("resume_canonical")
    keywords_suggested = data.get("keywords_suggested") or []
    keyword_count = _safe_int(data.get("keyword_count"), 5) or 5
    section_order = data.get("section_order") or []
    enabled_section_ids = data.get("enabled_section_ids") or []

    if not isinstance(resume_canonical, dict):
        return jsonify({"error": "resume_canonical is required and must be an object"}), 400

    if keyword_count < 3 or keyword_count > 10:
        return jsonify({"error": "keyword_count must be between 3 and 10"}), 400

    if not isinstance(section_order, list):
        return jsonify({"error": "section_order must be a list"}), 400
    section_order = [str(x) for x in section_order if str(x).strip()]

    if not isinstance(enabled_section_ids, list):
        return jsonify({"error": "enabled_section_ids must be a list"}), 400
    enabled_section_ids = [str(x) for x in enabled_section_ids if str(x).strip()]

    if not isinstance(keywords_suggested, list):
        keywords_suggested = []
    keywords_suggested = [str(k) for k in keywords_suggested if str(k).strip()]

    try:
        doc = ensure_canonical_resume(resume_canonical)

        # 1) Apply reorder (ids)
        if section_order:
            doc = reorder_sections(doc, section_order)

        # 2) NEW: Keep only checked sections (if provided)
        if enabled_section_ids:
            doc = filter_sections(doc, enabled_section_ids)

        # Safety: prevent empty PDF sections (optional but recommended)
        if not doc.get("sections"):
            return jsonify({"error": "No sections selected. Please select at least one section."}), 400

        # 3) Apply keywords (top-N)
        doc = apply_keywords_canonical(
            doc=doc,
            keywords=keywords_suggested,
            keyword_count=keyword_count,
        )

        # Re-ensure canonical after mutations
        doc = ensure_canonical_resume(doc)

        tex_content = render_latex_from_canonical(doc)
        pdf_bytes = compile_latex_to_pdf(tex_content)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(pdf_bytes)
        tmp.flush()
        tmp.close()

        return send_file(
            tmp.name,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="resume.pdf",
        )

    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
