# backend/latex_renderer.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple
import os
import subprocess
import textwrap

def _latex_escape(s: str) -> str:
    replacements = {
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
    out = []
    for ch in s:
        out.append(replacements.get(ch, ch))
    return "".join(out)

def render_latex_from_skeleton(
    skeleton: Dict[str, Any],
    template_tex_path: str,
    resume_cls_path: str,
) -> str:
    with open(template_tex_path, "r", encoding="utf-8") as f:
        template = f.read()

    header_lines = skeleton.get("header_lines", [])
    sections = skeleton.get("sections", [])

    name = header_lines[0] if len(header_lines) >= 1 else ""
    contact = header_lines[1] if len(header_lines) >= 2 else " ".join(header_lines[1:])

    name_tex = _latex_escape(name)
    contact_tex = _latex_escape(contact)

    body_parts: List[str] = []
    for sec in sections:
        title = _latex_escape(sec.get("title", ""))
        body_parts.append(rf"\begin{{rSection}}{{{title}}}")
        for blk in sec.get("blocks", []):
            if blk.get("type") == "line":
                line = _latex_escape(blk.get("text", ""))
                body_parts.append(rf"{line}\\")
            elif blk.get("type") == "bullets":
                items = blk.get("items", [])
                body_parts.append(r"\begin{tightitemize}")
                for it in items:
                    body_parts.append(rf"\item {_latex_escape(it)}")
                body_parts.append(r"\end{tightitemize}")
        body_parts.append(r"\end{rSection}")

    body = "\n".join(body_parts)

    tex = template
    tex = tex.replace("%%__NAME__%%", name_tex)
    tex = tex.replace("%%__CONTACT__%%", contact_tex)
    tex = tex.replace("%%__BODY__%%", body)

    return tex

def compile_latex_to_pdf(tex_path: str, workdir: str, out_pdf_path: str) -> Tuple[bool, str]:
    """
    Runs pdflatex twice for stable layout.
    """
    cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", os.path.basename(tex_path)]
    errlog = []
    for _ in range(2):
        p = subprocess.run(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        errlog.append(p.stdout)
        if p.returncode != 0:
            return False, "\n".join(errlog)

    produced_pdf = os.path.join(workdir, os.path.splitext(os.path.basename(tex_path))[0] + ".pdf")
    if not os.path.exists(produced_pdf):
        return False, "\n".join(errlog)

    with open(produced_pdf, "rb") as src, open(out_pdf_path, "wb") as dst:
        dst.write(src.read())

    return True, "\n".join(errlog)