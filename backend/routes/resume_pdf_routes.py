# routes/resume_pdf_routes.py
"""Resume PDF Generation Route"""

import json
import logging
import os
import shutil
import subprocess
import tempfile

from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

resume_pdf_bp = Blueprint("resume_pdf", __name__)

# Absolute path to the folder that contains resume.tex and resume.cls
TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),  # backend/
    "uploads",
    "resume-template",
)


def _make_jinja_env(template_dir: str) -> Environment:
    """
    Create a Jinja2 environment whose delimiters match the custom ones used in
    resume.tex:  (( )) for variables  and  ((* *)) for blocks.
    Standard {{ }} / {% %} delimiters are left untouched so they never clash
    with LaTeX braces.
    """
    return Environment(
        loader=FileSystemLoader(template_dir),
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="((*",
        block_end_string="*))",
        comment_start_string="((#",
        comment_end_string="#))",
        autoescape=False,
        keep_trailing_newline=True,
    )


def _sanitize_latex(value: str) -> str:
    """Escape the handful of LaTeX special characters that appear in user data."""
    if not isinstance(value, str):
        return str(value) if value is not None else ""
    replacements = [
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
    for char, escaped in replacements:
        value = value.replace(char, escaped)
    return value


def _sanitize_resume(data: dict) -> dict:
    """
    Recursively escape LaTeX special characters in all string values
    EXCEPT URLs (linkedin, github, portfolio, link) which must stay raw.
    """
    URL_KEYS = {"linkedin", "github", "portfolio", "link"}

    def _walk(obj, parent_key=None):
        if isinstance(obj, dict):
            return {k: _walk(v, parent_key=k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(item, parent_key=parent_key) for item in obj]
        if isinstance(obj, str):
            if parent_key in URL_KEYS:
                return obj  # keep URLs raw
            return _sanitize_latex(obj)
        return obj

    return _walk(data)


def _flatten_resume_json(raw: dict) -> dict:
    """
    Normalise the resume JSON so that template variables are always available,
    regardless of which top-level key name the LLM used.
    Returns a flat dict ready to be passed to the Jinja template.
    """
    # Personal info – several possible key names
    personal = (
        raw.get("personal_info")
        or raw.get("personal_information")
        or raw.get("contact")
        or {}
    )

    education = raw.get("education") or []
    experience = raw.get("experience") or []
    projects = raw.get("projects") or []
    certifications = raw.get("certifications") or []

    # Skills may be a list of strings or a dict of categories
    skills_raw = raw.get("skills") or []
    if isinstance(skills_raw, dict):
        skills = []
        for items in skills_raw.values():
            if isinstance(items, list):
                skills.extend(str(s) for s in items)
            else:
                skills.append(str(items))
    else:
        skills = [str(s) for s in skills_raw]

    return {
        "personal_info": {
            "name": personal.get("name") or "",
            "email": personal.get("email") or "",
            "phone": personal.get("phone") or "",
            "location": personal.get("location") or "",
            "linkedin": personal.get("linkedin") or "",
            "github": personal.get("github") or "",
            "portfolio": personal.get("portfolio") or "",
        },
        "education": education,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "skills": skills,
    }


@resume_pdf_bp.route("/generate-resume-pdf", methods=["POST", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def generate_resume_pdf():
    """
    Compile the user's resume JSON into a PDF using pdflatex + LaTeX template.

    Expected JSON payload:
        { "resume_json": { ...optimized resume object... } }

    Returns:
        application/pdf  on success
        application/json with { "error": "..." } on failure
    """
    if request.method == "OPTIONS":
        return ("", 204)

    # ── 1. Parse request ────────────────────────────────────────────────────
    data = request.get_json(silent=True) or {}
    resume_json = data.get("resume_json")

    if not resume_json:
        # Also accept a plain JSON string (from textarea)
        resume_str = data.get("resume_text") or ""
        if resume_str:
            try:
                resume_json = json.loads(resume_str)
            except json.JSONDecodeError:
                return jsonify({"error": "resume_json is required and must be valid JSON"}), 400
        else:
            return jsonify({"error": "resume_json is required"}), 400

    # ── 2. Validate pdflatex is installed ──────────────────────────────────
    if not shutil.which("pdflatex"):
        return jsonify({
            "error": "pdflatex is not installed on this server. "
                     "Please install TeX Live (e.g. `sudo apt install texlive-full`) "
                     "or MiKTeX and restart the backend."
        }), 503

    # ── 3. Flatten + sanitize the resume data ─────────────────────────────
    flat = _flatten_resume_json(resume_json)
    sanitized = _sanitize_resume(flat)

    # ── 4. Render the LaTeX template ──────────────────────────────────────
    try:
        env = _make_jinja_env(TEMPLATE_DIR)
        template = env.get_template("resume.tex")
        rendered_tex = template.render(**sanitized)
    except Exception as exc:
        logger.exception("Jinja2 template rendering failed")
        return jsonify({"error": f"Template rendering failed: {exc}"}), 500

    # ── 5. Compile with pdflatex in a temp directory ──────────────────────
    tmp_dir = tempfile.mkdtemp(prefix="resume_pdf_")
    try:
        # Copy the .cls file so pdflatex can find it
        cls_src = os.path.join(TEMPLATE_DIR, "resume.cls")
        cls_dst = os.path.join(tmp_dir, "resume.cls")
        shutil.copy2(cls_src, cls_dst)

        tex_path = os.path.join(tmp_dir, "resume.tex")
        pdf_path = os.path.join(tmp_dir, "resume.pdf")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(rendered_tex)

        # Run pdflatex twice so cross-references resolve correctly
        compile_cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory", tmp_dir,
            tex_path,
        ]
        for run in range(2):
            result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                # 300s to handle MiKTeX first-run package downloads;
                # subsequent runs will complete in ~2-3 seconds.
                timeout=300,
            )
            if result.returncode != 0:
                log_snippet = (result.stdout or "") + (result.stderr or "")
                # Extract the first LaTeX error line for a helpful message
                error_line = next(
                    (ln for ln in log_snippet.splitlines() if ln.startswith("!")),
                    "pdflatex compilation failed (check server logs)",
                )
                logger.error("pdflatex failed:\n%s", log_snippet[-3000:])
                return jsonify({"error": error_line}), 500

        if not os.path.exists(pdf_path):
            return jsonify({"error": "PDF file was not produced by pdflatex"}), 500

        logger.info("PDF generated successfully (%d bytes)", os.path.getsize(pdf_path))

        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="resume.pdf",
        )

    except subprocess.TimeoutExpired:
        return jsonify({"error": "pdflatex timed out after 5 minutes. MiKTeX may still be downloading packages — please try again in a moment."}), 504
    except Exception as exc:
        logger.exception("Unexpected error during PDF generation")
        return jsonify({"error": str(exc)}), 500
    finally:
        # Always clean up the temp directory
        shutil.rmtree(tmp_dir, ignore_errors=True)
