import os
import re
import json
import tempfile
import subprocess
from io import BytesIO

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

import trafilatura
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from openai import OpenAI

load_dotenv()

app = Flask(__name__)
CORS(app)

client = OpenAI()

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
TEMPLATE_TEX_PATH = os.path.join(TEMPLATES_DIR, "template_new.tex")
RESUME_CLS_PATH = os.path.join(TEMPLATES_DIR, "resume.cls")

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def looks_like_jd(text: str) -> bool:
    if not text:
        return False
    if len(text) < 800:
        return False
    markers = [
        "responsibilities", "qualifications", "requirements",
        "preferred qualifications", "minimum qualifications",
        "about the role", "what you'll do", "what you will do", "skills"
    ]
    lower = text.lower()
    return any(m in lower for m in markers)

def looks_like_login_wall(html_or_text: str) -> bool:
    if not html_or_text:
        return False
    s = html_or_text.lower() 
    return any(k in s for k in [
        "not logged in", "log in", "login", "sign in", "create an account"
    ])

def extract_jd_trafilatura(url: str) -> tuple[str, str]:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return "", "trafilatura_fetch_failed"

    if looks_like_login_wall(downloaded):
        return "", "login_wall_detected"

    jd = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        include_links=False,
        favor_precision=True,
    )
    jd = clean_text(jd or "")
    if not jd:
        return "", "trafilatura_extract_empty"
    return jd, "ok"

def extract_jd_playwright(url: str, timeout_ms: int = 20000) -> tuple[str, str]:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = page.content()
            browser.close()

        if looks_like_login_wall(html):
            return "", "login_wall_detected"

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
            tag.decompose()

        main = soup.find("main")
        text = main.get_text("\n") if main else soup.get_text("\n")
        text = clean_text(text)

        return text, "ok"
    except Exception as e:
        return "", f"playwright_error:{str(e)}"


def extract_job_description(url: str) -> dict:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "job_description": "", "method": "", "warning": "Empty URL."}

    jd1, dbg1 = extract_jd_trafilatura(url)
    if looks_like_jd(jd1):
        return {"ok": True, "job_description": jd1, "method": "trafilatura", "warning": None}
    if dbg1 == "login_wall_detected":
        return {
            "ok": False,
            "job_description": "",
            "method": "trafilatura",
            "warning": "This link appears to require login (cannot extract). Please paste the job description text."
        }

    jd2, dbg2 = extract_jd_playwright(url)
    if looks_like_jd(jd2):
        return {
            "ok": True,
            "job_description": jd2,
            "method": "playwright",
            "warning": "Used JS-rendered fallback."
        }

    if jd2 and len(jd2) >= 300:
        return {
            "ok": True,
            "job_description": jd2,
            "method": "playwright",
            "warning": "Extraction may be incomplete. If this looks wrong, paste the JD text instead."
        }

    return {
        "ok": False,
        "job_description": "",
        "method": "playwright" if "playwright" in dbg2 else "trafilatura",
        "warning": "Could not extract job description from link. Please paste JD text."
    }

def latex_escape(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = re.sub(r"\s+", " ", s).strip()

    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\texttildelow{}",
        "^": r"\textasciicircum{}",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)

    return s

def limit_list_by_chars(items, max_chars):
    """
    Keep items in order until the joined string would exceed max_chars.
    """
    out = []
    curr_len = 0
    for it in items:
        it = str(it).strip()
        if not it:
            continue
        add_len = len(it) + (2 if out else 0)  # ", "
        if curr_len + add_len > max_chars:
            break
        out.append(it)
        curr_len += add_len
    return out

def normalize_skills_for_one_line(resume: dict) -> dict:
    skills = (resume.get("skills") or {})
    tools = skills.get("tools") or []
    skills["tools"] = limit_list_by_chars(tools, max_chars=105)
    resume["skills"] = skills
    return resume

def normalize_projects(resume: dict) -> dict:
    projects = resume.get("projects") or []
    fixed = []
    for p in projects[:2]:
        p = dict(p or {})
        lines = [str(x).strip() for x in (p.get("lines") or []) if str(x).strip()]
        p["lines"] = lines[:2]
        fixed.append(p)
    resume["projects"] = fixed
    return resume


@app.route("/extract", methods=["POST"])
def extract():
    data = request.get_json() or {}
    url = data.get("job_description_link", "")

    result = extract_job_description(url)
    if not result["ok"]:
        return jsonify({
            "needs_paste": True,
            "error": "JD extraction failed",
            "warning": result.get("warning") or "Could not extract JD."
        }), 422

    payload = {
        "job_description": result["job_description"],
        "method": result["method"]
    }
    if result.get("warning"):
        payload["warning"] = result["warning"]

    return jsonify(payload), 200

@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json() or {}
    resume_json = data.get("resume_json")
    jd_text = (data.get("job_description_text") or "").strip()
    jd_link = (data.get("job_description_link") or "").strip()

    if not resume_json:
        return jsonify({"error": "resume_json is required"}), 400

    jd_method = "pasted"
    warning = None

    if not jd_text:
        result = extract_job_description(jd_link)
        if not result["ok"]:
            return jsonify({
                "needs_paste": True,
                "error": "Could not extract job description from link",
                "warning": result.get("warning") or "Please paste JD text."
            }), 422
        jd_text = result["job_description"]
        jd_method = result["method"]
        warning = result.get("warning")

    prompt = f"""
    You are an ATS resume optimizer and resume writer.

    You will be given:
    1) resume_json (already extracted from a resume)
    2) job_description_text

    GOAL:
    Make the resume as competitive as possible for the given job description while remaining truthful.

    RULES (must follow):
    - DO NOT invent or fabricate experience, projects, employers, dates, education, tools used, certifications, metrics, or outcomes.
    - You can strengthen wording, clarify scope, and add realistic impact framing when it is logically consistent with the original bullet.
    - You can add missing keywords from the job description when they are supported or implied by the existing content.
    - Prefer editing Experience and Projects bullets first (most impact).
    - Skills: You may add at most 3 to 4 skills/keywords total across the whole Skills section, and only if they are consistent with the resume content.
    - Remove or de-emphasize clearly unrelated skills to make space for relevant ones.
    - Avoid keyword stuffing. Keep bullets concise and credible.
    - Make the resume as competitive as possible for the given job description while remaining truthful.

    PROCESS:
    1) Extract the top ATS keywords/phrases from the job description (tools, frameworks, concepts, responsibilities).
    2) Compare against resume_json to identify missing-but-supported keywords.
    3) Update the resume_json:
    - Rewrite Experience and Projects bullets to incorporate supported keywords naturally.
    - Strengthen bullets using action + scope + impact structure (no fake numbers).
    - Update Skills by removing unrelated items and inserting up to 3 to 4 supported skills.

    OUTPUT:
    Return ONLY valid JSON with this exact shape:
    {{
    "updated_resume_json": {{
        "name": "string",
        "contact_lines": ["string", "string", "string"],
        "education": [
        {{
            "degree": "string",
            "date": "string",
            "school": "string",
            "location": "string"
        }}
        ],
        "skills": {{
        "languages": ["string"],
        "frameworks": ["string"],
        "tools": ["string"]
        }},
        "experience": [
        {{
            "title": "string",
            "dates": "string",
            "company": "string",
            "location": "string",
            "bullets": ["string", "string", "string"]
        }}
        ],
        "projects": [
        {{
            "name": "string",
            "tech": ["string"],
            "date": "string",
            "lines": ["string", "string"]
        }}
        ]
    }},
    "keywords_added": [
        {{
        "keyword": "string",
        "location": "skills|experience|projects",
        "where": "short description"
        }}
    ],
    "skills_removed": ["string"],
    "notes": ["string"]
    }}

    IMPORTANT FORMATTING RULES:
    - Keep bullets short (ideally 1 line each).
    - Keep 3 bullets per experience entry (if resume_text supports it).
    - Projects: "lines" should be 1–2 lines (summary + detail).
    - If you are unsure about a detail, keep it generic rather than inventing specifics.

    resume_text:
    {resume_json.get("raw_text", "")[:12000]}

    job_description_text:
    {jd_text[:12000]}
    """.strip()

    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input=prompt,
            text={"format": {"type": "json_object"}},
        )

        raw = resp.output_text
        out = json.loads(raw)

        payload = {
            "updated_resume_json": out["updated_resume_json"],
            "keywords_added": out.get("keywords_added", []),
            "jd_method": jd_method
        }
        if warning:
            payload["warning"] = warning

        return jsonify(payload), 200

    except json.JSONDecodeError:
        return jsonify({"error": "Model returned invalid JSON", "raw_response": raw}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def render_latex_from_json(resume_data: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        undefined=StrictUndefined,
        autoescape=False,
        comment_start_string="((#",
        comment_end_string="#))",
    )
    env.filters["latex_escape"] = latex_escape
    template = env.get_template("template_new.tex")
    return template.render(resume=resume_data)




@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    data = request.get_json() or {}
    resume_data = normalize_projects(data.get("updated_resume_json"))
    resume_data = normalize_skills_for_one_line(resume_data)
    if not resume_data:
        return jsonify({"error": "updated_resume_json is required"}), 400
    
    print("TEMPLATES_DIR:", TEMPLATES_DIR)
    print("TEMPLATE_TEX_PATH:", TEMPLATE_TEX_PATH)
    print("RESUME_CLS_PATH:", RESUME_CLS_PATH)
    print("Template exists?", os.path.exists(TEMPLATE_TEX_PATH))

    try:
        tex_content = render_latex_from_json(resume_data)
        print("---- DEBUG: updated_resume_json keys ----")
        print(list(resume_data.keys()) if isinstance(resume_data, dict) else type(resume_data))

        print("---- DEBUG: rendered TeX preview ----")
        print(tex_content[:800])

    except Exception as e:
        return jsonify({"error": f"Template render failed: {str(e)}"}), 500

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        cls_path = os.path.join(tmpdir, "resume.cls")
        pdf_path = os.path.join(tmpdir, "resume.pdf")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        with open(RESUME_CLS_PATH, "rb") as src, open(cls_path, "wb") as dst:
            dst.write(src.read())

        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "resume.tex"]
        try:
            subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            subprocess.run(cmd, cwd=tmpdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        except subprocess.CalledProcessError as e:
            return jsonify({
                "error": "LaTeX compilation failed",
                "latex_output": (e.stdout or b"").decode("utf-8", errors="ignore")[:4000]
            }), 500
        except subprocess.TimeoutExpired:
            return jsonify({"error": "LaTeX compilation timed out"}), 500

        if not os.path.exists(pdf_path):
            return jsonify({"error": "PDF not generated"}), 500

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="optimized_resume.pdf"
    )


@app.get("/health")
def health():
    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
