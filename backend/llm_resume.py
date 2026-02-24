# backend/llm_resume.py
from __future__ import annotations

from typing import Any, Dict, Optional, Literal, Tuple, List
import os
import json
import time
import hashlib
import re
import difflib
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

Mode = Literal["fast", "quality"]

DEFAULT_MODEL = os.getenv("RESUME_MODEL", "gpt-5.2")

# Rough placeholder pricing (USD / 1M tokens). Update later with real numbers.
MODEL_PRICING_USD_PER_1M: Dict[str, Dict[str, float]] = {
    "gpt-4.1-mini": {"input": 0.5, "output": 1.5},
    "gpt-4.1": {"input": 5.0, "output": 15.0},
    "gpt-5.2": {"input": 10.0, "output": 30.0},
}

# ----------------------------
# Prompts
# ----------------------------

SYSTEM_PROMPT_BASE = """You are an expert resume parser + ATS evaluator.
You are writing output that the user may submit directly to real job applications.
Prioritize correctness, precision, and trust over creativity.

You will receive:
- Full extracted resume text (messy, from PDF)
- A job description

Return ONLY valid JSON (no markdown, no backticks) in EXACTLY this shape:

{
  "original": {
    "skeleton": {
      "header": { "lines": ["Full Name (MUST be first)", "contact info line(s)..."] },
      "sections": [
        {
          "id": "string",
          "title": "string",
          "enabled": true,
          "blocks": [
            { "type": "line", "text": "..." },
            { "type": "bullets", "items": ["..."] },
            {
              "type": "subsection",
              "title": "...",
              "blocks": [
                { "type": "meta", "text": "..." },
                { "type": "line", "text": "..." },
                { "type": "bullets", "items": ["..."] }
              ]
            }
          ]
        }
      ]
    },
    "ats": {
      "score": 0,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "notes": ["..."],
      "breakdown": [
        { "name": "Keyword & skill match (0-30)", "score": 0, "max": 30, "notes": "..." },
        { "name": "Responsibilities match (0-25)", "score": 0, "max": 25, "notes": "..." },
        { "name": "Impact & metrics (0-20)", "score": 0, "max": 20, "notes": "..." },
        { "name": "Seniority & relevance (0-15)", "score": 0, "max": 15, "notes": "..." },
        { "name": "ATS readability (0-10)", "score": 0, "max": 10, "notes": "..." }
      ]
    }
  },
  "improvements": {
    "missing_keywords": ["..."],
    "rewrite_suggestions": [
      { "target": "where to apply", "before": "...", "after": "...", "reason": "..." }
    ],
    "priority_actions": ["..."]
  },
  "optimized": {
    "resume": {
      "header": { "lines": ["..."] },
      "sections": [ ... ]
    },
    "ats": {
      "score": 0,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "notes": ["..."],
      "breakdown": [
        { "name": "Keyword & skill match (0-30)", "score": 0, "max": 30, "notes": "..." },
        { "name": "Responsibilities match (0-25)", "score": 0, "max": 25, "notes": "..." },
        { "name": "Impact & metrics (0-20)", "score": 0, "max": 20, "notes": "..." },
        { "name": "Seniority & relevance (0-15)", "score": 0, "max": 15, "notes": "..." },
        { "name": "ATS readability (0-10)", "score": 0, "max": 10, "notes": "..." }
      ]
    }
  },
  "debug": {
    "warnings": ["..."],
    "assumptions": ["..."]
  }
}

Rules:
- The user-submitted resume is the source of truth. Section names, order, and structure (Education, Skills, Experience, Projects, etc.) must come from what the user actually has — parse and preserve their sections; do not impose a fixed template. Different resumes may have different sections and order.
- Do NOT invent experience, skills, tools, or metrics. Every fact in the optimized resume and in rewrite_suggestions must be directly supported by the original resume text.
- missing_keywords: list JD keywords that are absent from the resume, for the user to consider adding only if true. Do NOT add these into the optimized skeleton or into skills/bullets unless the original already supports them.
- Optimized resume: do not insert missing_keywords; do not add structural elements (e.g. dates in projects) that the original did not have.
- Rewrite suggestions: only suggest changes grounded in actual content; do not suggest adding dates or sections the original does not have.
- Preserve section order and section titles from the submitted resume. enabled should be true for all detected sections.
- Use "subsection" for nested groupings exactly as in the user's resume (e.g. each skill category, each job, each project). Use a single "line" block for a subsection when the user has one line of items (comma-separated); use "bullets" when the user has bullet points. Mirror their structure.
- Put dates/locations/GPA in a "meta" block only where the original resume includes them. For Education subsections: use the pattern [meta(date range), line(school name), meta(location or GPA)] so degree+date pair on row 1 and school+GPA pair on row 2. Each "meta" pairs with the preceding left-side text. If any of these don't exist, ignore them.
- Bullets must be grouped as one block: {type:"bullets", items:[...]}.
- Rewrite suggestions: at least 5 when applicable, each grounded in actual resume content.

High-trust content policy:
- Prefer fewer, higher-confidence outputs over many weak ones.
- Never output generic filler advice like "improve communication", "be a team player", "work in a fast-paced environment", or "hard-working".
- For missing_keywords, include only concrete role-relevant terms from the JD:
  tools/technologies, methods/frameworks, domains, certifications, role-specific responsibilities.
- Exclude generic terms (e.g. responsible, collaborate, optimize, motivated, problem-solving, detail-oriented, communication).
- Favor 1-3 word keyword phrases used explicitly or very clearly implied by the JD.
- De-duplicate aggressively (case-insensitive, singular/plural variants, close synonyms).
- For each rewrite_suggestion:
  - "before" must be copied from original resume wording.
  - "after" must preserve truth and meaning while increasing clarity, ATS alignment, and specificity.
  - Keep length same or shorter than before unless one brief keyword insertion significantly improves relevance.
  - "reason" must explain exactly which JD requirement this rewrite targets.

ATS scoring rubric:
- Compute a breakdown with scores that sum to the final score (0–100).
- Keep breakdown consistent between original and optimized.
- Score conservatively; do not inflate if evidence is weak.

Header rules:
- header.lines[0] MUST be the person's full name. Never put phone, email, or URLs as the first line.
- header.lines[1..] are contact details (phone, email, links, location). Do not include stray braces {} or other noise.

Single-page constraint:
- The optimized resume MUST fit on 1 page. Do NOT add new bullets, sections, or content that would make the resume longer than the original.
- Optimization means REPLACING and REPHRASING existing bullets to be more impactful — not adding new ones. The optimized resume should have the same number of bullets and sections as the original.
- Only add content (~20% of the time) if it is a minor clarification that does not increase length (e.g. adding a keyword into an existing bullet).
- Preserve existing emphasis: if the original resume text has bold/emphasis markers for words or phrases, keep those same parts emphasized in optimized.resume (do not convert emphasized text to plain text).

Optimization:
- Return OPTIMIZED resume skeleton with improvements applied (rephrasing only; same length or shorter). Score OPTIMIZED vs JD.
- The PDF is rendered with a consistent visual style (font, spacing, rules); the skeleton you return determines sections, titles, and structure for any industry or role.
- Final quality gate before returning JSON:
  1) If any suggestion/keyword is not clearly supported by resume+JD evidence, remove it.
  2) If a rewrite sounds generic, replace it with a specific one or drop it.
  3) Ensure optimized resume reads like final application-ready copy, not draft notes.
"""

SYSTEM_PROMPT_SCORE_ONLY = """You are a strict ATS-style evaluator.

You will receive:
- A ResumeSkeleton JSON (already structured)
- A job description

Return ONLY valid JSON (no markdown) in EXACTLY this shape:

{
  "ats": {
    "score": 0,
    "strengths": ["..."],
    "weaknesses": ["..."],
    "notes": ["..."],
    "breakdown": [
      { "name": "Keyword & skill match (0-30)", "score": 0, "max": 30, "notes": "..." },
      { "name": "Responsibilities match (0-25)", "score": 0, "max": 25, "notes": "..." },
      { "name": "Impact & metrics (0-20)", "score": 0, "max": 20, "notes": "..." },
      { "name": "Seniority & relevance (0-15)", "score": 0, "max": 15, "notes": "..." },
      { "name": "ATS readability (0-10)", "score": 0, "max": 10, "notes": "..." }
    ]
  },
  "missing_keywords": ["..."]
}

Rules:
- Do not invent experience. Scores must be internally consistent: sum(breakdown.score) == ats.score.
- missing_keywords: JD keywords that are missing from the resume (for user consideration only). Do not list keywords that would require inventing experience.
- Return only high-signal missing keywords: concrete technologies, frameworks, methods, domain terms, certifications, and role responsibilities.
- Exclude generic soft-skill words and generic corporate verbs.
- De-duplicate and keep only the most decision-relevant terms.
- Score conservatively and align notes with explicit resume evidence.
"""

def _mode_instructions(mode: Mode) -> str:
    if mode == "fast":
        return """MODE=FAST
- Keep output compact and high-signal.
- missing_keywords: max 20
- rewrite_suggestions: max 10
- priority_actions: max 5
- Keep bullets concise.
"""
    return """MODE=QUALITY
- Be thorough, precise, and evidence-based.
- missing_keywords: max 45
- rewrite_suggestions: max 15
- priority_actions: max 6
- Prefer quality over quantity. Do not add weak or generic suggestions to hit limits.
"""

# ----------------------------
# Helpers: stable IDs, usage, cost
# ----------------------------

_slug_cleanup_re = re.compile(r"[^a-z0-9]+")
def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = _slug_cleanup_re.sub("-", s)
    s = s.strip("-")
    return s or "section"

def _ensure_stable_section_ids(result: Dict[str, Any]) -> None:
    def fix_sections(sections: Any) -> None:
        if not isinstance(sections, list):
            return
        for i, sec in enumerate(sections):
            if not isinstance(sec, dict):
                continue
            title = sec.get("title") or f"Section {i+1}"
            sec["id"] = sec.get("id") or f"{_slug(title)}-{i+1}"
            sec["enabled"] = bool(sec.get("enabled", True))

    orig = result.get("original", {}).get("skeleton", {})
    if isinstance(orig, dict):
        fix_sections(orig.get("sections"))

    opt = result.get("optimized", {}).get("resume", {})
    if isinstance(opt, dict):
        fix_sections(opt.get("sections"))

def _extract_usage(resp: Any) -> Tuple[Optional[int], Optional[int]]:
    usage = getattr(resp, "usage", None)
    if usage is None and isinstance(resp, dict):
        usage = resp.get("usage")
    if usage is None:
        return None, None

    inp = getattr(usage, "input_tokens", None)
    out = getattr(usage, "output_tokens", None)
    if inp is None and isinstance(usage, dict):
        inp = usage.get("input_tokens")
        out = usage.get("output_tokens")
    return inp, out

def _estimate_cost_usd(model: str, input_tokens: Optional[int], output_tokens: Optional[int]) -> Optional[float]:
    if input_tokens is None or output_tokens is None:
        return None
    pricing = MODEL_PRICING_USD_PER_1M.get(model)
    if not pricing:
        return None
    return (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]

def _stable_hash(resume_text: str, job_description: str, model: str, mode: Mode) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(mode.encode("utf-8"))
    h.update(b"\n---RESUME---\n")
    h.update(resume_text.encode("utf-8", errors="ignore"))
    h.update(b"\n---JD---\n")
    h.update(job_description.encode("utf-8", errors="ignore"))
    return h.hexdigest()

def _basic_validate_one_call_payload(data: Dict[str, Any]) -> None:
    for top in ("original", "improvements", "optimized", "debug"):
        if top not in data:
            raise ValueError(f"Model JSON missing key: {top}")

    if "skeleton" not in data["original"]:
        raise ValueError("Model JSON missing original.skeleton")
    if "ats" not in data["original"]:
        raise ValueError("Model JSON missing original.ats")
    if "resume" not in data["optimized"]:
        raise ValueError("Model JSON missing optimized.resume")
    if "ats" not in data["optimized"]:
        raise ValueError("Model JSON missing optimized.ats")


def _default_max_output_tokens(mode: Mode) -> int:
    # Your JSON can be big (optimized skeleton + suggestions)
    return 4200 if mode == "fast" else 9000

# ----------------------------
# Robust JSON extraction (fixes occasional truncation/extra text)
# ----------------------------

def _extract_json_object(raw: str) -> str:
    """
    Best-effort extraction of a top-level JSON object from a model response.
    Handles accidental leading/trailing text.
    """
    if not raw:
        raise ValueError("Empty model response")

    raw = raw.strip()

    # If it already starts with { and ends with }, try direct
    if raw.startswith("{") and raw.endswith("}"):
        return raw

    # Otherwise find first { and last } and slice
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Could not locate JSON object in model response")
    return raw[start : end + 1]

# ----------------------------
# Deterministic keyword coverage
# ----------------------------

_STOPWORDS = {
    "the","a","an","and","or","to","of","in","for","on","with","by","as","at","from","is","are","was","were",
    "this","that","these","those","you","your","we","our","they","their","it","its","be","been","being",
    "will","can","may","should","must","not","no","yes","if","then","else","than","into","over","under",
    "about","across","within","per","via","using","use","used","build","built","design","designed",
}

_TECH_HINTS = {
    # common tech tokens that are meaningful as keywords even if short-ish
    "aws","gcp","azure","sql","nosql","rest","graphql","grpc","kafka","spark","hadoop","redis","docker",
    "kubernetes","terraform","ci/cd","cicd","git","linux","java","python","javascript","typescript",
    "react","node","spring","flask","django","postgres","postgresql","mysql","mongodb","snowflake",
    "airflow","dbt","pandas","numpy","etl","elt","llm","rag","vector","prometheus","grafana",
}

_TOKEN_RE = re.compile(r"[a-z0-9\+\#\/\.\-]{2,}", re.IGNORECASE)

def _normalize_text_for_match(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def extract_jd_keywords_deterministic(job_description: str, max_keywords: int = 120) -> List[str]:
    """
    Simple deterministic keyword extractor:
    - keeps tech-like tokens
    - keeps longer tokens that look like skills (3+ chars)
    - de-dupes, preserves rough importance by frequency
    """
    jd = _normalize_text_for_match(job_description)
    tokens = _TOKEN_RE.findall(jd)

    freq: Dict[str, int] = {}
    for t in tokens:
        tt = t.strip().lower()
        if tt in _STOPWORDS:
            continue
        if len(tt) < 3 and tt not in _TECH_HINTS:
            continue
        # normalize common variants
        tt = tt.replace("c++", "cpp").replace("c#", "csharp")
        freq[tt] = freq.get(tt, 0) + 1

    # boost tech hints slightly
    for k in list(freq.keys()):
        if k in _TECH_HINTS:
            freq[k] += 2

    # sort by (freq desc, length desc)
    ranked = sorted(freq.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    out: List[str] = []
    seen = set()
    for k, _ in ranked:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
        if len(out) >= max_keywords:
            break
    return out

def skeleton_to_plain_text(resume_skeleton: Dict[str, Any]) -> str:
    parts: List[str] = []
    header = resume_skeleton.get("header", {}) if isinstance(resume_skeleton, dict) else {}
    if isinstance(header, dict):
        lines = header.get("lines", [])
        if isinstance(lines, list):
            for l in lines:
                if isinstance(l, str) and l.strip():
                    parts.append(l.strip())

    sections = resume_skeleton.get("sections", []) if isinstance(resume_skeleton, dict) else []
    if isinstance(sections, list):
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            title = sec.get("title")
            if isinstance(title, str) and title.strip():
                parts.append(title.strip())

            blocks = sec.get("blocks", [])
            if isinstance(blocks, list):
                parts.extend(_blocks_to_text(blocks))

    return "\n".join(parts)

def _blocks_to_text(blocks: List[Any]) -> List[str]:
    out: List[str] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "line" or t == "meta":
            txt = b.get("text")
            if isinstance(txt, str) and txt.strip():
                out.append(txt.strip())
        elif t == "bullets":
            items = b.get("items", [])
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, str) and it.strip():
                        out.append(it.strip())
        elif t == "subsection":
            title = b.get("title")
            if isinstance(title, str) and title.strip():
                out.append(title.strip())
            sub_blocks = b.get("blocks", [])
            if isinstance(sub_blocks, list):
                out.extend(_blocks_to_text(sub_blocks))
    return out

def compute_keyword_coverage(resume_text: str, job_description: str, max_keywords: int = 120) -> Dict[str, Any]:
    jd_keywords = extract_jd_keywords_deterministic(job_description, max_keywords=max_keywords)
    hay = " " + _normalize_text_for_match(resume_text) + " "

    matched: List[str] = []
    missing: List[str] = []
    for kw in jd_keywords:
        # phrase-ish match (simple substring with boundaries)
        # we keep it simple; frontend can show coverage as a trust signal.
        if kw and kw in hay:
            matched.append(kw)
        else:
            missing.append(kw)

    total = len(jd_keywords) if jd_keywords else 0
    coverage = (len(matched) / total * 100.0) if total else 0.0

    return {
        "total_keywords": total,
        "matched_count": len(matched),
        "missing_count": len(missing),
        "coverage_percent": round(coverage, 1),
        "matched": matched[:200],
        "missing": missing[:200],
    }

# ----------------------------
# Rewrite suggestion diff (machine-readable)
# ----------------------------

def word_diff(before: str, after: str) -> List[Dict[str, str]]:
    """
    Returns segments like:
    [{"op":"equal","text":"Built "}, {"op":"del","text":"old"}, {"op":"ins","text":"new"}]
    """
    a = (before or "")
    b = (after or "")

    a_words = re.split(r"(\s+)", a)  # keep whitespace tokens
    b_words = re.split(r"(\s+)", b)

    sm = difflib.SequenceMatcher(a=a_words, b=b_words)
    segments: List[Dict[str, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            txt = "".join(a_words[i1:i2])
            if txt:
                segments.append({"op": "equal", "text": txt})
        elif tag == "delete":
            txt = "".join(a_words[i1:i2])
            if txt:
                segments.append({"op": "del", "text": txt})
        elif tag == "insert":
            txt = "".join(b_words[j1:j2])
            if txt:
                segments.append({"op": "ins", "text": txt})
        elif tag == "replace":
            del_txt = "".join(a_words[i1:i2])
            ins_txt = "".join(b_words[j1:j2])
            if del_txt:
                segments.append({"op": "del", "text": del_txt})
            if ins_txt:
                segments.append({"op": "ins", "text": ins_txt})
    return segments

def attach_diffs_to_rewrite_suggestions(result: Dict[str, Any]) -> None:
    """
    Adds rewrite_suggestions[i].diff = [segments...]
    Safe: frontend can use segments to highlight.
    """
    improvements = result.get("improvements")
    if not isinstance(improvements, dict):
        return
    rs = improvements.get("rewrite_suggestions")
    if not isinstance(rs, list):
        return
    for item in rs:
        if not isinstance(item, dict):
            continue
        before = item.get("before", "")
        after = item.get("after", "")
        if isinstance(before, str) and isinstance(after, str):
            item["diff"] = word_diff(before, after)

# ----------------------------
# Main: one-call analyze
# ----------------------------

def analyze_resume_one_call(
    resume_text: str,
    job_description: str,
    *,
    model: Optional[str] = None,
    mode: Mode = "quality",
    use_cache: bool = False,
    cache_dir: str = ".cache_resume",
    max_output_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL
    client = OpenAI()

    resume_text = (resume_text or "").strip()
    job_description = (job_description or "").strip()

    # guardrails (still generous)
    if len(resume_text) > 140_000:
        resume_text = resume_text[:140_000]
    if len(job_description) > 100_000:
        job_description = job_description[:100_000]

    cache_key = _stable_hash(resume_text, job_description, model, mode)
    cache_path = None
    if use_cache:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached.setdefault("telemetry", {})
            cached["telemetry"]["cache_hit"] = True
            return cached

    if max_output_tokens is None:
        max_output_tokens = _default_max_output_tokens(mode)

    system_prompt = SYSTEM_PROMPT_BASE + "\n\n" + _mode_instructions(mode)

    # retry on JSON parsing failure (usually truncation)
    attempts = [
        {"max_output_tokens": max_output_tokens, "extra_user_note": ""},
        {
            "max_output_tokens": min(max_output_tokens * 2, 16000),
            "extra_user_note": (
                "\n\nIMPORTANT: If you cannot fit everything, shorten long bullets and notes. "
                "Return COMPLETE VALID JSON only."
            ),
        },
    ]

    last_raw: Optional[str] = None
    last_err: Optional[Exception] = None

    for idx, a in enumerate(attempts):
        t0 = time.time()
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "RESUME TEXT:\n"
                        "-----------------\n"
                        f"{resume_text}\n\n"
                        "JOB DESCRIPTION:\n"
                        "-----------------\n"
                        f"{job_description}\n"
                        f"{a['extra_user_note']}"
                    ),
                },
            ],
            text={"format": {"type": "json_object"}},
            max_output_tokens=a["max_output_tokens"],
            temperature=0.2,
        )
        latency_ms = int((time.time() - t0) * 1000)

        raw = getattr(resp, "output_text", None)
        last_raw = raw

        try:
            if not raw:
                raise ValueError("No output_text returned by model")

            raw_json = _extract_json_object(raw)
            data = json.loads(raw_json)

            _basic_validate_one_call_payload(data)
            _ensure_stable_section_ids(data)

            # Attach diffs for rewrite suggestions
            attach_diffs_to_rewrite_suggestions(data)

            # Deterministic coverage for trust signal
            coverage_original = compute_keyword_coverage(resume_text, job_description)
            # For optimized, compute from optimized skeleton (more accurate than original text)
            opt_skel = data.get("optimized", {}).get("resume", {})
            opt_text = skeleton_to_plain_text(opt_skel) if isinstance(opt_skel, dict) else resume_text
            coverage_optimized = compute_keyword_coverage(opt_text, job_description)

            in_toks, out_toks = _extract_usage(resp)
            est_cost = _estimate_cost_usd(model, in_toks, out_toks)

            data["telemetry"] = {
                "model": model,
                "mode": mode,
                "latency_ms": latency_ms,
                "input_tokens": in_toks,
                "output_tokens": out_toks,
                "estimated_cost_usd": est_cost,
                "cache_hit": False,
                "cache_key": cache_key,
                "attempt": idx + 1,
                "max_output_tokens": a["max_output_tokens"],
            }

            data["signals"] = {
                "keyword_coverage": {
                    "original": coverage_original,
                    "optimized": coverage_optimized,
                },
                "optimized_auto_applied": True,
            }

            if use_cache and cache_path:
                data["telemetry"]["cached_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            return data

        except Exception as e:
            last_err = e
            continue

    preview = (last_raw or "")[:800]
    raise ValueError(f"Failed to parse model JSON after retries: {last_err}. Raw preview: {preview}")

# ----------------------------
# Score-only (for after UI edits)
# ----------------------------

def score_resume_skeleton(
    resume_skeleton: Dict[str, Any],
    job_description: str,
    *,
    model: Optional[str] = None,
    use_cache: bool = False,
    cache_dir: str = ".cache_score",
    max_output_tokens: int = 1800,
) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL
    client = OpenAI()

    jd = (job_description or "").strip()
    resume_json = json.dumps(resume_skeleton, ensure_ascii=False)

    # cache key
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\n---RESUME_JSON---\n")
    h.update(resume_json.encode("utf-8", errors="ignore"))
    h.update(b"\n---JD---\n")
    h.update(jd.encode("utf-8", errors="ignore"))
    cache_key = h.hexdigest()

    cache_path = None
    if use_cache:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached.setdefault("telemetry", {})
            cached["telemetry"]["cache_hit"] = True
            return cached

    t0 = time.time()
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT_SCORE_ONLY},
            {
                "role": "user",
                "content": (
                    "RESUME_SKELETON_JSON:\n"
                    "-----------------\n"
                    f"{resume_json}\n\n"
                    "JOB DESCRIPTION:\n"
                    "-----------------\n"
                    f"{jd}\n"
                ),
            },
        ],
        text={"format": {"type": "json_object"}},
        max_output_tokens=max_output_tokens,
        temperature=0.2,
    )
    latency_ms = int((time.time() - t0) * 1000)

    raw = getattr(resp, "output_text", None)
    if not raw:
        raise ValueError("No output_text returned by model")

    raw_json = _extract_json_object(raw)
    data = json.loads(raw_json)

    # Deterministic coverage signal for THIS skeleton
    sk_text = skeleton_to_plain_text(resume_skeleton)
    coverage = compute_keyword_coverage(sk_text, jd)

    in_toks, out_toks = _extract_usage(resp)
    est_cost = _estimate_cost_usd(model, in_toks, out_toks)

    data["telemetry"] = {
        "model": model,
        "latency_ms": latency_ms,
        "input_tokens": in_toks,
        "output_tokens": out_toks,
        "estimated_cost_usd": est_cost,
        "cache_hit": False,
        "cache_key": cache_key,
    }

    data["signals"] = {
        "keyword_coverage": coverage,
    }

    if use_cache and cache_path:
        data["telemetry"]["cached_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return data