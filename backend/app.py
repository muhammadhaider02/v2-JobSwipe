from flask import Flask, request, jsonify, render_template
from flask_cors import CORS, cross_origin
import os
import re
import uuid
import threading
from pdfminer.high_level import extract_text
from docx import Document
from utils.section_splitter import (
    split_resume_into_sections,
    print_sections,
    parse_projects_from_text,
    parse_skills_from_text,
)
from src.llama_refiner import refine_resume
from src.updated_query import suggest_roles as get_role_recommendations

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB upload cap
CORS(
    app,
    resources={
        "/upload": {"origins": "http://localhost:3000"},
        "/get-llm-results/*": {"origins": "http://localhost:3000"},
        "/recommend-roles": {"origins": "http://localhost:3000"},
    },
    supports_credentials=False,
)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory storage for LLM processing jobs
llm_jobs = {}  # {job_id: {'status': 'processing'|'completed'|'failed', 'result': {...}, 'error': str}}


def extract_text_from_file(path: str) -> str:
    """
    Extract plain text from PDF or DOCX.
    """
    ext = os.path.splitext(path)[-1].lower()
    if ext == ".pdf":
        # Try pdfminer, fallback to PyPDF2
        try:
            return extract_text(path)
        except Exception as e1:
            try:
                import PyPDF2

                text = ""
                with open(path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += (page.extract_text() or "") + "\n"
                if not text.strip():
                    raise ValueError("Empty PDF text after extraction")
                return text.strip()
            except Exception as e2:
                raise RuntimeError(f"PDF extraction failed: {e1} | fallback: {e2}")
    elif ext == ".docx":
        try:
            doc = Document(path)
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            raise RuntimeError(f"DOCX extraction failed: {e}")
    else:
        raise ValueError("Unsupported file type")


def extract_links_from_pdf(path: str):
    """
    Extract URLs from a PDF using BOTH:
    - clickable hyperlink annotations (/URI)
    - plain text on each page via PyPDF2's extract_text()

    This is more robust for resumes where footer links are just text.
    """
    urls = []
    try:
        import PyPDF2

        url_pattern = re.compile(r"https?://[^\s)]+", re.IGNORECASE)

        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                # 1) Clickable annotations (if any)
                annots = page.get("/Annots")
                if annots:
                    for a in annots:
                        obj = a.get_object()
                        action = obj.get("/A")
                        if action and action.get("/URI"):
                            uri = action.get("/URI")
                            if isinstance(uri, str):
                                urls.append(uri)

                # 2) Plain text on the page (footer URLs etc.)
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    page_text = ""
                for u in url_pattern.findall(page_text):
                    urls.append(u)
    except Exception as e:
        print(f"PDF link extraction failed: {e}")

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        deduped.append(u)
    return deduped


def extract_project_links(urls, text: str):
    """
    Extract GitHub *repo* links (not just profile) for projects.
    Sources:
      - URLs from PDF (annotations + PyPDF2 text)
      - Fallback: regex over full extracted text

    Returns in document order: first repo -> first project, etc.
    """
    repo_links = []

    # From URLs list (annotations + page text)
    for u in urls or []:
        lu = u.lower()
        if "github.com" not in lu:
            continue
        # Strip domain, see how many path segments we have
        path = re.sub(r"^https?://[^/]+", "", lu)
        segments = [s for s in path.split("/") if s]
        # Need at least "username/repo"
        if len(segments) >= 2:
            repo_links.append(u)

    # Fallback from full text if none found
    if not repo_links:
        pattern = re.compile(
            r"https?://(?:www\.)?github\.com/[^\s/]+/[^\s/]+",
            re.IGNORECASE,
        )
        repo_links = pattern.findall(text)

    # Clean trailing punctuation and dedupe
    cleaned = []
    seen = set()
    for u in repo_links:
        v = u.rstrip(").,;")
        if v in seen:
            continue
        seen.add(v)
        cleaned.append(v)
    return cleaned


def extract_contact_info(text: str, urls=None):
    """
    Extract name, email, phone, location, LinkedIn, GitHub and portfolio
    from resume text + hyperlink URLs.
    """
    if urls is None:
        urls = []

    contact_info = {
        "name": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin": None,
        "github": None,
        "portfolio": None,
    }

    # Normalize lines
    lines = [l.strip() for l in text.replace("\r\n", "\n").split("\n")]
    lines = [l for l in lines if l.strip()]

    # ---------------- EMAIL ----------------
    # Prefer mailto: links, then fallback to regex in text
    email = None
    for u in urls:
        if u.lower().startswith("mailto:"):
            email = u.split(":", 1)[1]
            break
    if not email:
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, text)
        if emails:
            email = emails[0]
    contact_info["email"] = email

    # ---------------- PHONE ----------------
    phone_pattern = r"\+?\d[\d\s\-()]{7,}\d"
    phones = re.findall(phone_pattern, text)
    valid_phones = [p for p in phones if len(re.sub(r"[^\d]", "", p)) >= 10]
    if valid_phones:
        contact_info["phone"] = valid_phones[0].strip()

    # ---------------- URLS (LinkedIn / GitHub / Portfolio) ----------------
    # First pass: use URLs collected from PDF (annotations + PyPDF2 text)
    for u in urls:
        lu = u.lower()
        if lu.startswith("mailto:"):
            continue

        if "linkedin.com" in lu and contact_info["linkedin"] is None:
            contact_info["linkedin"] = u
            continue

        if "github.com" in lu and contact_info["github"] is None:
            # Normalize to profile-level URL if it's a repo link
            m = re.match(r"https?://(www\.)?github\.com/([^/]+)/?", lu)
            if m:
                contact_info["github"] = f"https://github.com/{m.group(2)}"
            else:
                contact_info["github"] = u
            continue

        # Portfolio: first non-GitHub, non-LinkedIn, non-mailto URL
        if (
            contact_info["portfolio"] is None
            and "linkedin.com" not in lu
            and "github.com" not in lu
        ):
            contact_info["portfolio"] = u

    # Fallback: basic regex over extracted text if needed
    if (
        contact_info["linkedin"] is None
        or contact_info["github"] is None
        or contact_info["portfolio"] is None
    ):
        url_pattern = r"https?://[^\s)]+"
        text_urls = re.findall(url_pattern, text)
        for u in text_urls:
            lu = u.lower()
            if "linkedin.com" in lu and contact_info["linkedin"] is None:
                contact_info["linkedin"] = u
            elif "github.com" in lu and contact_info["github"] is None:
                m = re.match(r"https?://(www\.)?github\.com/([^/]+)/?", lu)
                if m:
                    contact_info["github"] = f"https://github.com/{m.group(2)}"
                else:
                    contact_info["github"] = u
            elif (
                contact_info["portfolio"] is None
                and "linkedin.com" not in lu
                and "github.com" not in lu
            ):
                contact_info["portfolio"] = u

    # ---------------- NAME ----------------
    name = None
    if lines:
        candidate = lines[0]
        if (
            len(candidate) <= 80
            and "@" not in candidate
            and not re.search(r"https?://", candidate, re.IGNORECASE)
        ):
            name = candidate
    contact_info["name"] = name

    # ---------------- LOCATION ----------------
    # Simple heuristic: look at first few lines for "City, Country"
    location = None
    for line in lines[:6]:
        m = re.search(
            r"([A-Za-z][A-Za-z\s]+,\s*[A-Za-z][A-Za-z\s]+)\s*$", line
        )
        if m:
            location = m.group(1).strip()
            break
    contact_info["location"] = location

    return contact_info


@app.route("/")
def index():
    """Serve the upload page"""
    return render_template("index.html")


@app.route("/upload", methods=["GET", "POST", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def upload_resume():
    # Short-circuit preflight and readiness checks
    if request.method == "OPTIONS":
        return ("", 204)
    if request.method == "GET":
        return jsonify({"status": "ready"}), 200

    # POST: handle upload
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        if not file or not file.filename:
            return jsonify({"error": "Empty file"}), 400
        path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(path)

        # Step 1: Extract text
        try:
            text = extract_text_from_file(path)
        except Exception as ex:
            return jsonify({"error": f"Failed to extract text from file: {ex}"}), 400
    except Exception as ex:
        return jsonify({"error": f"Upload handling failed: {ex}"}), 400

    # If PDF, also extract URLs using PyPDF2 (annotations + page text)
    urls = []
    ext = os.path.splitext(path)[-1].lower()
    if ext == ".pdf":
        urls = extract_links_from_pdf(path)

    # Step 2: Extract contact information + links
    contact_info = extract_contact_info(text, urls=urls)

    print("\n==== Contact Information ====")
    print(f"Name: {contact_info['name']}")
    print(f"Email: {contact_info['email']}")
    print(f"Phone: {contact_info['phone']}")
    print(f"Location: {contact_info['location']}")
    print(f"LinkedIn: {contact_info['linkedin']}")
    print(f"GitHub: {contact_info['github']}")
    print(f"Portfolio: {contact_info['portfolio']}")

    # Step 3: Split resume into sections
    sections = split_resume_into_sections(text)

    # Print sections to terminal for debugging
    print_sections(sections)

    # Summary from Profile (Objective) section
    summary_text = sections.get("Profile", "").strip()
    # Remove heading like OBJECTIVE / PROFILE / SUMMARY
    summary_text = re.sub(
        r"^(OBJECTIVE|PROFILE|SUMMARY|PROFESSIONAL SUMMARY)\s*\n+",
        "",
        summary_text,
        flags=re.IGNORECASE,
    ).strip()
    # Replace newlines with spaces so it's a single line
    summary_text = summary_text.replace("\r\n", "\n").replace("\r", "\n")
    summary_text = re.sub(r"\s*\n+\s*", " ", summary_text).strip()

    # Parse projects and skills
    try:
        parsed_projects = parse_projects_from_text(sections.get("Projects", ""))
        parsed_skills = parse_skills_from_text(sections.get("Skills", ""))
    except Exception as e:
        parsed_projects = []
        parsed_skills = []
        print(f"Error parsing projects/skills: {e}")

    # --- NEW: attach GitHub repo links to projects ---
    project_links = extract_project_links(urls, text)
    for idx, proj in enumerate(parsed_projects):
        link = project_links[idx] if idx < len(project_links) else ""
        proj["link"] = link

    # Immediate JSON response
    immediate_response = {
        "contact_info": {
            "name": contact_info.get("name") or "",
            "email": contact_info.get("email") or "",
            "phone": contact_info.get("phone") or "",
            "location": contact_info.get("location") or "",
        },
        "profile": {
            "summary": summary_text,
            "github": contact_info.get("github") or "",
            "linkedin": contact_info.get("linkedin") or "",
            "portfolio": contact_info.get("portfolio") or "",
        },
        "skills": parsed_skills,
        "projects": parsed_projects,
    }

    # Generate job ID for LLM processing
    job_id = str(uuid.uuid4())

    # Initialize job status
    llm_jobs[job_id] = {
        "status": "processing",
        "result": None,
        "error": None,
    }

    # Background LLM processing (education + experience)
    def process_llm_in_background():
        try:
            print(
                f"\n==== Starting LLM Background Processing for job {job_id} ====",
                flush=True,
            )

            ordered_for_llm = ["Education", "Experience"]
            resume_text_for_llm = "\n\n".join(
                [
                    f"{name}:\n{sections.get(name, '')}"
                    for name in ordered_for_llm
                    if sections.get(name, "")
                ]
            )

            backend = os.getenv("LLAMA_BACKEND", "ollama")
            model_name = os.getenv("LLAMA_MODEL", "llama3:8b-instruct-q4_K_M")
            base_url = os.getenv("LLAMA_BASE_URL", "http://localhost:11434")

            print("\n==== LLM CONFIG ====", flush=True)
            print(f"backend={backend}", flush=True)
            print(f"model={model_name}", flush=True)
            print(f"base_url={base_url}", flush=True)
            print(
                "\n==== LLM INPUT: Resume text (Education/Experience ONLY) ====",
                flush=True,
            )
            print(resume_text_for_llm or "(empty)", flush=True)

            refined = refine_resume(
                resume_text=resume_text_for_llm,
                backend=backend,
                model=model_name,
                base_url=base_url,
                temperature=0.1,
                max_new_tokens=1200,
                request_timeout_s=300.0,
            )

            llm_jobs[job_id]["status"] = "completed"
            llm_jobs[job_id]["result"] = refined

            print(
                f"\n==== LLM Background Processing COMPLETED for job {job_id} ====",
                flush=True,
            )
        except Exception as e:
            print(
                f"\n==== LLM Background Processing FAILED for job {job_id}: {e} ====",
                flush=True,
            )
            llm_jobs[job_id]["status"] = "failed"
            llm_jobs[job_id]["error"] = str(e)

    thread = threading.Thread(target=process_llm_in_background, daemon=True)
    thread.start()

    # Return immediate response with job_id
    return jsonify({"job_id": job_id, **immediate_response})


@app.route("/get-llm-results/<job_id>", methods=["GET", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_llm_results(job_id):
    """
    Poll endpoint to check if LLM processing is complete.
    """
    if request.method == "OPTIONS":
        return ("", 204)

    if job_id not in llm_jobs:
        return jsonify({"status": "not_found", "error": "Job ID not found"}), 404

    job = llm_jobs[job_id]
    response = {"status": job["status"]}

    if job["status"] == "completed":
        response["result"] = job["result"]
    elif job["status"] == "failed":
        response["error"] = job["error"]

    return jsonify(response)


@app.route("/recommend-roles", methods=["POST", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def recommend_roles():
    """
    Endpoint to get role recommendations based on user skills.
    """
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        data = request.get_json()
        if not data or "skills" not in data:
            return jsonify({"error": "No skills provided"}), 400

        skills = data["skills"]
        if not isinstance(skills, list) or len(skills) == 0:
            return jsonify({"error": "Skills must be a non-empty array"}), 400

        top_k = data.get("top_k", 10)

        print(f"\n==== ROLE RECOMMENDATION REQUEST ====")
        print(f"Skills: {skills}")
        print(f"Top K: {top_k}")

        result = get_role_recommendations(skills, top_k=top_k)

        candidates = result.get("candidates", [])

        max_score = max([c["aggregated_score"] for c in candidates], default=1.0)
        if max_score == 0:
            max_score = 1.0

        recommendations = []
        for candidate in candidates:
            example_skills = []
            if candidate.get("example_hits"):
                for hit in candidate["example_hits"]:
                    example_skills.extend(hit.get("skills", []))

            unique_skills = list(dict.fromkeys(example_skills))

            raw_score = candidate["aggregated_score"]
            percentage_score = (raw_score / max_score) * 100

            print(
                f"Role: {candidate['role']}, Raw Score: {raw_score:.4f}, Percentage: {percentage_score:.1f}%"
            )

            recommendations.append(
                {
                    "role": candidate["role"],
                    "score": round(percentage_score, 1),
                    "skills": ", ".join(unique_skills[:10]),
                }
            )

        return jsonify(
            {
                "recommendations": recommendations,
                "skills_used": skills,
                "suggest_more_skills": result.get("suggest_more_skills"),
            }
        )

    except Exception as e:
        print(f"Error in recommend_roles: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
