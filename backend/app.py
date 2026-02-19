# backend/app.py
from __future__ import annotations

import os
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from resume_skeleton import extract_text_from_pdf
from llm_resume import analyze_resume_one_call, score_resume_skeleton

from pdf_latex import (
    apply_order_and_enabled,
    compile_pdf_from_skeleton,
)

app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}},
)

DEFAULT_MODE = os.getenv("RESUME_MODE", "quality")
DEFAULT_MODEL = os.getenv("RESUME_MODEL", "gpt-5.2")


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/analyze_resume")
def analyze_resume():
    """
    Supports TWO input modes:

    1) multipart/form-data:
       - resume: PDF file
       - job_description: string
       - model, mode, use_cache optional

    2) application/json:
       {
         "resume_text": "...",   # already extracted
         "job_description": "...",
         "model": "...",
         "mode": "fast|quality",
         "use_cache": true|false
       }
    """
    try:
        model = DEFAULT_MODEL
        mode = DEFAULT_MODE
        use_cache = False

        # ---- JSON mode ----
        if request.is_json:
            payload = request.get_json() or {}
            resume_text = (payload.get("resume_text") or "").strip()
            job_description = (payload.get("job_description") or "").strip()
            model = (payload.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
            mode = (payload.get("mode") or DEFAULT_MODE).strip().lower()
            use_cache = bool(payload.get("use_cache", False))

            if mode not in ("fast", "quality"):
                mode = DEFAULT_MODE

            if not resume_text:
                return jsonify({"error": "Missing resume_text"}), 400
            if not job_description:
                return jsonify({"error": "Missing job_description"}), 400

        # ---- Multipart mode ----
        else:
            if "resume" not in request.files:
                return jsonify({"error": "Missing resume file field 'resume'"}), 400

            resume_file = request.files["resume"]
            job_description = (request.form.get("job_description") or "").strip()
            if not job_description:
                return jsonify({"error": "Missing job_description"}), 400

            use_cache = (request.form.get("use_cache", "false").lower() == "true")
            mode = (request.form.get("mode", DEFAULT_MODE) or DEFAULT_MODE).strip().lower()
            model = (request.form.get("model", DEFAULT_MODEL) or DEFAULT_MODEL).strip()

            if mode not in ("fast", "quality"):
                mode = DEFAULT_MODE

            # save PDF temporarily and extract
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = os.path.join(tmpdir, resume_file.filename or "resume.pdf")
                resume_file.save(pdf_path)
                resume_text = extract_text_from_pdf(pdf_path)

        result = analyze_resume_one_call(
            resume_text=resume_text,
            job_description=job_description,
            model=model,
            mode=mode,
            use_cache=use_cache,
        )
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"LLM call failed: {str(e)}"}), 500


@app.post("/score_resume")
def score_resume():
    """
    Score-only endpoint for UI edits.
    Accepts JSON:
    {
      "resume_skeleton": {...},
      "job_description": "...",
      "model": "...",
      "use_cache": true|false
    }
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Send JSON body"}), 400

        payload = request.get_json() or {}
        resume_skeleton = payload.get("resume_skeleton")
        job_description = (payload.get("job_description") or "").strip()
        model = (payload.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
        use_cache = bool(payload.get("use_cache", False))

        if not resume_skeleton:
            return jsonify({"error": "Missing resume_skeleton"}), 400
        if not job_description:
            return jsonify({"error": "Missing job_description"}), 400

        result = score_resume_skeleton(
            resume_skeleton=resume_skeleton,
            job_description=job_description,
            model=model,
            use_cache=use_cache,
        )
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"Score call failed: {str(e)}"}), 500


@app.route("/generate_pdf", methods=["POST", "OPTIONS"])
def generate_pdf():
    """
    JSON:
    {
      "resume_canonical": { ...optimized.resume skeleton... },
      "keywords_suggested": ["..."],

      "section_order": ["id1", "id2", ...],            # optional
      "enabled_section_ids": ["id1", "id3", ...]       # optional
    }

    Returns: application/pdf
    """
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        if not request.is_json:
            return jsonify({"error": "Send JSON body"}), 400

        payload = request.get_json() or {}

        resume = payload.get("resume_canonical")
        if not isinstance(resume, dict):
            return jsonify({"error": "Missing resume_canonical"}), 400

        keywords = payload.get("keywords_suggested") or []
        if not isinstance(keywords, list):
            keywords = []

        section_order = payload.get("section_order") or []
        enabled_ids = payload.get("enabled_section_ids") or []

        # Apply ordering + enabled selection
        resume = apply_order_and_enabled(resume, section_order, enabled_ids)

        pdf_bytes = compile_pdf_from_skeleton(
            resume,
            highlight_keywords=keywords,
        )

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(pdf_bytes)
        tmp.flush()
        tmp.close()

        return send_file(
            tmp.name,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="Resume_Optimized.pdf",
        )

    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)