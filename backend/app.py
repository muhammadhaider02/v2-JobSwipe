from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import os
import re
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List
from pdfminer.high_level import extract_text
from docx import Document
from utils.section_splitter import (
    split_resume_into_sections,
    parse_skills_from_text,
)
from src.llama_refiner import refine_resume, refine_projects
from src.updated_query import suggest_roles as get_role_recommendations
from src.skill_gap_analysis import analyze_skill_gap
from src.skill_enrichment import enrich_skills
from services.supabase_service import SupabaseService
from config.settings import get_settings
from src.logging_config import get_logger, redact_uid

logger = get_logger(__name__)

# Import blueprints
from routes.campaign_routes import campaign_bp
from routes.resume_optimization_routes import resume_optimization_bp
from routes.cover_letter_routes import cover_letter_bp
from routes.learning_resources import learning_resources_bp
from routes.quiz_routes import quiz_bp
from routes.resume_pdf_routes import resume_pdf_bp

CORS_ORIGIN = os.environ.get("CORS_ALLOWED_ORIGIN", "http://localhost:3000")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB upload cap
CORS(
    app,
    resources={
        "/upload": {"origins": CORS_ORIGIN},
        "/get-llm-results/*": {"origins": CORS_ORIGIN},
        "/recommend-roles": {"origins": CORS_ORIGIN},
        "/analyze-skill-gap": {"origins": CORS_ORIGIN},
        "/save-profile": {"origins": CORS_ORIGIN},
        "/get-profile/*": {"origins": CORS_ORIGIN},
        "/user-profile": {"origins": CORS_ORIGIN},
        "/user-profile/*": {"origins": CORS_ORIGIN},
        "/api/jobs/*": {"origins": CORS_ORIGIN},
        "/cover-letter-templates": {"origins": CORS_ORIGIN},
        "/generate-cover-letter": {"origins": CORS_ORIGIN},
        "/prepare-application-materials": {"origins": CORS_ORIGIN},
        "/application-materials/save-draft": {"origins": CORS_ORIGIN},
        "/generate-resume-pdf": {"origins": CORS_ORIGIN},
    },
    supports_credentials=False,
)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory storage for LLM processing jobs
llm_jobs = {}  # {job_id: {'status': 'processing'|'completed'|'failed', 'result': {...}, 'error': str}}

# Initialize Supabase service
supabase_service = SupabaseService()

# Register blueprints
app.register_blueprint(campaign_bp)
app.register_blueprint(resume_optimization_bp)
app.register_blueprint(cover_letter_bp)
app.register_blueprint(learning_resources_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(resume_pdf_bp)


_UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)


def _redact_path(path: str) -> str:
    return _UUID_RE.sub(lambda m: m.group()[:8] + "...", path)


@app.after_request
def log_request(response):
    logger.info("%s %s %s", request.method, _redact_path(request.path), response.status_code)
    return response


def _normalize_profile_payload(data):
    """Accept both legacy and frontend-friendly payload shapes."""
    user_id = data.get("user_id")
    profile_data = data.get("profile_data")

    # Allow direct profile payload as a convenience format.
    if user_id and not profile_data:
        profile_data = {k: v for k, v in data.items() if k != "user_id"}

    return user_id, profile_data


def _normalize_job_record_for_vetting(job: Dict[str, Any]) -> Dict[str, Any]:
    """Map DB job record shape to vetting node expected fields."""
    skills = job.get("skills_required") or job.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]

    return {
        "job_id": job.get("job_id", ""),
        "title": job.get("job_title") or job.get("title") or "",
        "company": job.get("company") or "",
        "location": job.get("location") or "",
        "industry": job.get("industry") or "",
        "description": job.get("job_description") or job.get("description") or "",
        "skills": skills if isinstance(skills, list) else [],
        "experience_required": job.get("experience_required"),
        "employment_type": job.get("job_type") or job.get("employment_type") or "",
        # DB jobs are already structured, so set confidence high for vetting stage.
        "enrichment_confidence": 1.0,
    }


def _score_query_relevance(job: Dict[str, Any], query_tokens: List[str]) -> int:
    """Simple lexical score to pre-rank DB jobs before vetting."""
    if not query_tokens:
        return 1

    title = str(job.get("title") or "").lower()
    company = str(job.get("company") or "").lower()
    location = str(job.get("location") or "").lower()
    description = str(job.get("description") or "").lower()
    skills = " ".join([str(s).lower() for s in (job.get("skills") or [])])

    score = 0
    for token in query_tokens:
        if token in title:
            score += 4
        if token in skills:
            score += 3
        if token in description:
            score += 2
        if token in company or token in location:
            score += 1
    return score


def _load_db_jobs_for_vetting(search_query: str, max_candidates: int = 250) -> List[Dict[str, Any]]:
    """Load persisted jobs from DB and pre-rank by query relevance."""
    response = supabase_service.client.table("jobs").select("*").limit(max_candidates).execute()
    rows = response.data or []

    normalized = [_normalize_job_record_for_vetting(row) for row in rows]

    tokens = [t.strip().lower() for t in re.split(r"\s+", search_query or "") if t.strip()]
    scored = []
    for job in normalized:
        relevance = _score_query_relevance(job, tokens)
        scored.append((relevance, job))

    # Always include remote jobs regardless of query relevance — they apply to everyone.
    # For non-remote jobs, only keep those that have at least one query token match.
    def is_remote(job: Dict[str, Any]) -> bool:
        loc = str(job.get("location") or "").lower()
        job_type = str(job.get("employment_type") or "").lower()
        return "remote" in loc or "remote" in job_type

    matched = [(r, j) for r, j in scored if r > 0 or is_remote(j)]
    # If no matches at all (very strict query), fall back to all jobs
    if not matched:
        matched = scored

    matched.sort(key=lambda item: item[0], reverse=True)
    return [job for _, job in matched]


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
        logger.error("PDF link extraction failed: %s", e)

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
@app.route("/health")
def index():
    return jsonify({"status": "ok", "service": "JobSwipe API"})


@app.route("/upload", methods=["GET", "POST", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
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

    # Delete the uploaded file now that text and links have been extracted
    try:
        os.remove(path)
    except Exception as e:
        logger.warning("Failed to delete temporary upload file '%s': %s", path, e)

    # Step 2: Extract contact information + links
    contact_info = extract_contact_info(text, urls=urls)

    logger.info("Contact information extracted, fields present: %s",
                 [k for k, v in contact_info.items() if v])

    # Step 3: Split resume into sections
    sections = split_resume_into_sections(text)

    logger.debug("Parsed %d resume sections: %s", len(sections), list(sections.keys()))

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

    # Parse skills (immediate)
    try:
        parsed_skills = parse_skills_from_text(sections.get("Skills", ""))
    except Exception as e:
        parsed_skills = []
        logger.error("Error parsing skills: %s", e)

    # Immediate JSON response (skills only — no regex projects)
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
        "projects": [],
        "education": [],
        "experience": []
    }

    # Generate job ID for LLM processing
    job_id = str(uuid.uuid4())

    # Initialize job status (includes both LLM and skill enrichment)
    llm_jobs[job_id] = {
        "status": "processing",
        "result": None,
        "error": None,
        "skill_enrichment": {
            "status": "processing",
            "skills": None,
            "error": None,
        },
        "project_llm": {
            "status": "processing",
            "projects": None,
            "error": None,
        },
    }

    # Background skill enrichment
    def process_skill_enrichment_in_background():
        try:
            logger.info("Starting skill enrichment for job=%s", job_id)
            enriched_skills = enrich_skills(text, parsed_skills)
            llm_jobs[job_id]["skill_enrichment"]["status"] = "completed"
            llm_jobs[job_id]["skill_enrichment"]["skills"] = enriched_skills
            logger.info("Skill enrichment completed for job=%s", job_id)
        except Exception as e:
            logger.error("Skill enrichment failed for job=%s: %s", job_id, e)
            llm_jobs[job_id]["skill_enrichment"]["status"] = "failed"
            llm_jobs[job_id]["skill_enrichment"]["error"] = str(e)

    # Background LLM processing (education + experience)
    def process_llm_in_background():
        import time
        # Stagger slightly to avoid all 3 background jobs hammering the API at once
        time.sleep(0.5)
        try:
            logger.info("Starting LLM background processing for job=%s", job_id)

            ordered_for_llm = ["Education", "Experience"]
            resume_text_for_llm = "\n\n".join(
                [
                    f"{name}:\n{sections.get(name, '')}"
                    for name in ordered_for_llm
                    if sections.get(name, "")
                ]
            )

            backend = os.getenv("LLAMA_BACKEND", "openai_compat")
            model_name = get_settings().deepseek_model
            base_url = get_settings().deepseek_base_url

            logger.debug("LLM config: backend=%s model=%s base_url=%s",
                         backend, model_name, base_url)
            logger.debug("Resume text length: %d chars",
                         len(resume_text_for_llm))

            refined = refine_resume(
                resume_text=resume_text_for_llm,
                backend=backend,
                model=model_name,
                base_url=base_url,
                temperature=0.2,
                max_new_tokens=2000,
                request_timeout_s=300.0,
            )

            llm_jobs[job_id]["status"] = "completed"
            llm_jobs[job_id]["result"] = refined

            logger.info("LLM background processing completed for job=%s", job_id)
        except Exception as e:
            logger.error("LLM background processing failed for job=%s: %s", job_id, e)
            llm_jobs[job_id]["status"] = "failed"
            llm_jobs[job_id]["error"] = str(e)

    # Background Projects LLM (parallel)
    def process_projects_llm_in_background():
        import time
        # Stagger more to prevent hitting rate limit with the other two jobs
        time.sleep(1.0)
        try:
            logger.info("Starting projects LLM for job=%s", job_id)
            projects_text = sections.get("Projects", "")
            backend = os.getenv("LLAMA_BACKEND", "openai_compat")
            model_name = get_settings().deepseek_model
            base_url = get_settings().deepseek_base_url

            extracted_projects = refine_projects(
                projects_text=projects_text,
                backend=backend,
                model=model_name,
                base_url=base_url,
                temperature=0.1,
                max_new_tokens=1200,
                request_timeout_s=300.0,
            )

            # Attempt to attach GitHub/portfolio links from PDF annotations
            project_links = extract_project_links(urls, text)
            for idx, proj in enumerate(extracted_projects):
                if not proj.get("link") and idx < len(project_links):
                    proj["link"] = project_links[idx]

            llm_jobs[job_id]["project_llm"]["status"] = "completed"
            llm_jobs[job_id]["project_llm"]["projects"] = extracted_projects
            logger.info("Projects LLM completed for job=%s", job_id)
        except Exception as e:
            logger.error("Projects LLM failed for job=%s: %s", job_id, e)
            llm_jobs[job_id]["project_llm"]["status"] = "failed"
            llm_jobs[job_id]["project_llm"]["error"] = str(e)

    # Start all three background threads in parallel
    skill_thread = threading.Thread(target=process_skill_enrichment_in_background, daemon=True)
    skill_thread.start()

    llm_thread = threading.Thread(target=process_llm_in_background, daemon=True)
    llm_thread.start()

    projects_thread = threading.Thread(target=process_projects_llm_in_background, daemon=True)
    projects_thread.start()

    # Return immediate response with job_id
    return jsonify({"job_id": job_id, **immediate_response})


@app.route("/get-llm-results/<job_id>", methods=["GET", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_llm_results(job_id):
    """
    Poll endpoint to check if LLM processing and skill enrichment are complete.
    Returns both LLM results and enriched skills.
    """
    if request.method == "OPTIONS":
        return ("", 204)

    if job_id not in llm_jobs:
        return jsonify({"status": "not_found", "error": "Job ID not found"}), 404

    job = llm_jobs[job_id]
    response = {"status": job["status"]}

    # Education + Experience LLM result
    if job["status"] == "completed":
        response["result"] = job["result"]
    elif job["status"] == "failed":
        response["error"] = job["error"]

    # Skill enrichment
    skill_enrichment = job.get("skill_enrichment", {})
    response["skill_enrichment"] = {
        "status": skill_enrichment.get("status", "processing"),
    }
    if skill_enrichment.get("status") == "completed":
        response["skill_enrichment"]["skills"] = skill_enrichment.get("skills", [])
    elif skill_enrichment.get("status") == "failed":
        response["skill_enrichment"]["error"] = skill_enrichment.get("error", "Unknown error")

    # Projects LLM
    project_llm = job.get("project_llm", {})
    response["project_llm"] = {
        "status": project_llm.get("status", "processing"),
    }
    if project_llm.get("status") == "completed":
        response["project_llm"]["projects"] = project_llm.get("projects", [])
    elif project_llm.get("status") == "failed":
        response["project_llm"]["error"] = project_llm.get("error", "Unknown error")

    return jsonify(response)


@app.route("/recommend-roles", methods=["POST", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
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

        logger.info("Role recommendation request: %d skills, top_k=%d", len(skills), top_k)

        result = get_role_recommendations(skills, top_k=top_k)

        candidates = result.get("candidates", [])

        max_score = max([c["aggregated_score"] for c in candidates], default=1.0)
        if max_score == 0:
            max_score = 1.0

        from services.embedding_service import get_embedding_service
        model = get_embedding_service()
        user_embeddings = model.encode(skills, convert_to_numpy=True, show_progress_bar=False)

        def process_candidate(candidate):
            role = candidate["role"]
            try:
                gap_data = analyze_skill_gap(role, skills, user_embeddings=user_embeddings)
                completion_percentage = gap_data.get("completion_percentage", 0)

                example_skills = []
                if candidate.get("example_hits"):
                    for hit in candidate["example_hits"]:
                        example_skills.extend(hit.get("skills", []))
                unique_skills = list(dict.fromkeys(example_skills))

                logger.debug("Role: %s, Skill Match: %s%%", role, completion_percentage)
                return {
                    "role": role,
                    "score": completion_percentage,
                    "skills": ", ".join(unique_skills[:9]),
                    "skillGapData": {
                        "existing_skills": gap_data.get("existing_skills", []),
                        "required_skills": gap_data.get("required_skills", []),
                        "completion_percentage": completion_percentage
                    }
                }
            except Exception as e:
                logger.error("Error analyzing skill gap for %s: %s", role, e)
                return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            processed_recommendations = [r for r in executor.map(process_candidate, candidates) if r is not None]

        # Filter: only roles with >= 50% skill match
        recommendations = [r for r in processed_recommendations if r["score"] >= 50.0]
        
        # Sort by score descending (highest match first)
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        
        # Limit to maximum 9 recommendations
        recommendations = recommendations[:9]

        return jsonify(
            {
                "recommendations": recommendations,
                "skills_used": skills,
                "suggest_more_skills": result.get("suggest_more_skills"),
            }
        )

    except Exception as e:
        logger.error("Error in recommend_roles: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/analyze-skill-gap", methods=["POST", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def analyze_skill_gap_endpoint():
    """
    Endpoint to analyze skill gap for a specific role.
    """
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        role = data.get("role")
        skills = data.get("skills")

        if not role:
            return jsonify({"error": "Role is required"}), 400

        if not skills or not isinstance(skills, list):
            return jsonify({"error": "Skills must be a non-empty array"}), 400

        logger.info("Skill gap analysis request: role=%s, %d skills", role, len(skills))

        # Perform skill gap analysis
        result = analyze_skill_gap(role, skills)

        logger.debug("Skill gap result: %d existing, %d required, %s%% completion",
                     len(result['existing_skills']),
                     len(result['required_skills']),
                     result['completion_percentage'])

        return jsonify(result)

    except ValueError as e:
        # Handle role not found or other validation errors
        logger.warning("Validation error in analyze_skill_gap: %s", e)
        return jsonify({"error": str(e)}), 404

    except Exception as e:
        logger.error("Error in analyze_skill_gap: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/save-profile", methods=["POST", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def save_profile_endpoint():
    """
    Endpoint to save or update user profile.
    """
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        user_id, profile_data = _normalize_profile_payload(data)

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        if not profile_data:
            return jsonify({"error": "profile_data is required"}), 400

        logger.info("Saving user profile for user=%s, fields=%s",
                    redact_uid(user_id), list(profile_data.keys()))

        # Save profile to database
        success = supabase_service.upsert_user_profile(user_id, profile_data)

        if success:
            logger.info("Profile saved successfully for user=%s", redact_uid(user_id))
            return jsonify({
                "success": True,
                "message": "Profile saved successfully"
            }), 200
        else:
            logger.error("Failed to save profile for user=%s", redact_uid(user_id))
            return jsonify({
                "success": False,
                "error": "Failed to save profile"
            }), 500

    except Exception as e:
        logger.error("Error in save_profile: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/get-profile/<user_id>", methods=["GET", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_profile_endpoint(user_id):
    """
    Endpoint to retrieve user profile.
    """
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        logger.info("Fetching user profile for user=%s", redact_uid(user_id))

        # Get profile from database
        profile = supabase_service.get_user_profile(user_id)

        if profile:
            logger.info("Profile retrieved successfully for user=%s", redact_uid(user_id))
            return jsonify({
                "success": True,
                "profile": profile
            }), 200
        else:
            logger.warning("No profile found for user=%s", redact_uid(user_id))
            return jsonify({
                "success": False,
                "profile": None,
                "message": "No profile found"
            }), 404

    except Exception as e:
        logger.error("Error in get_profile: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/user-profile", methods=["POST", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def user_profile_save_alias():
    """Compatibility alias for frontend profile writes."""
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        data = request.get_json() or {}
        user_id, profile_data = _normalize_profile_payload(data)

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        if profile_data is None:
            return jsonify({"error": "profile_data is required"}), 400

        success = supabase_service.upsert_user_profile(user_id, profile_data)
        if not success:
            return jsonify({"success": False, "error": "Failed to save profile"}), 500

        return jsonify({"success": True, "message": "Profile saved successfully"}), 200

    except Exception as e:
        logger.error("Error in user_profile alias save: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/user-profile/<user_id>", methods=["GET", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def user_profile_get_alias(user_id):
    """Compatibility alias for frontend profile reads."""
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        profile = supabase_service.get_user_profile(user_id)
        if not profile:
            return jsonify({"success": False, "profile": None, "message": "No profile found"}), 404

        return jsonify({"success": True, "profile": profile}), 200

    except Exception as e:
        logger.error("Error in user_profile alias get: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>", methods=["GET", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_job_detail_endpoint(job_id):
    """Fetch one job from the persisted jobs table."""
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        if not job_id:
            return jsonify({"error": "job_id is required"}), 400

        job = supabase_service.get_job_by_id(job_id)
        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404

        return jsonify({"success": True, "job": job}), 200

    except Exception as e:
        logger.error("Error in get job detail: %s", e)
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Background vetting thread & streaming endpoints
# ──────────────────────────────────────────────────────────────────────────────

VETTING_BATCH_SIZE = 50        # Jobs loaded per DB query
VETTING_BUFFER   = 30          # How many un-consumed approved jobs to keep ahead
VETTING_IDLE_TTL = 60          # Seconds with no poll before the thread stops


# ── In-memory vetting store (no Redis required) ───────────────────────────────
# Structure per user_id:
#   { "jobs": [...], "seen": set(), "status": "processing"|"done"|"idle",
#     "last_poll": float timestamp }
_vetting_sessions: Dict[str, Any] = {}
_vetting_lock = threading.Lock()


def _vs_clear(user_id: str) -> None:
    with _vetting_lock:
        _vetting_sessions[user_id] = {
            "jobs": [],
            "seen": set(),
            "status": "processing",
            "last_poll": 0.0,
            "consumed": 0,
        }


def _vs_push_job(user_id: str, job: Dict[str, Any]) -> None:
    with _vetting_lock:
        _vetting_sessions.setdefault(user_id, {"jobs": [], "seen": set(), "status": "processing", "last_poll": 0.0})
        _vetting_sessions[user_id]["jobs"].append(job)


def _vs_get_jobs(user_id: str, since: int = 0) -> List[Dict[str, Any]]:
    with _vetting_lock:
        return list(_vetting_sessions.get(user_id, {}).get("jobs", [])[since:])


def _vs_job_count(user_id: str) -> int:
    with _vetting_lock:
        return len(_vetting_sessions.get(user_id, {}).get("jobs", []))


def _vs_is_seen(user_id: str, job_id: str) -> bool:
    with _vetting_lock:
        return job_id in _vetting_sessions.get(user_id, {}).get("seen", set())


def _vs_mark_seen(user_id: str, job_id: str) -> None:
    with _vetting_lock:
        _vetting_sessions.setdefault(user_id, {"jobs": [], "seen": set(), "status": "processing", "last_poll": 0.0})
        _vetting_sessions[user_id]["seen"].add(job_id)


def _vs_set_status(user_id: str, status: str) -> None:
    with _vetting_lock:
        _vetting_sessions.setdefault(user_id, {"jobs": [], "seen": set(), "status": "idle", "last_poll": 0.0})
        _vetting_sessions[user_id]["status"] = status


def _vs_get_status(user_id: str) -> str:
    with _vetting_lock:
        return _vetting_sessions.get(user_id, {}).get("status", "idle")


def _vs_update_poll(user_id: str) -> None:
    import time
    with _vetting_lock:
        _vetting_sessions.setdefault(user_id, {"jobs": [], "seen": set(), "status": "idle", "last_poll": 0.0})
        _vetting_sessions[user_id]["last_poll"] = time.time()


def _vs_get_poll(user_id: str) -> float:
    with _vetting_lock:
        return _vetting_sessions.get(user_id, {}).get("last_poll", 0.0)


def _vs_update_consumed(user_id: str, consumed: int) -> None:
    """Record how many cards the user has consumed (skipped or applied)."""
    with _vetting_lock:
        sess = _vetting_sessions.get(user_id)
        if sess is not None:
            sess["consumed"] = max(sess.get("consumed", 0), consumed)


def _vs_get_consumed(user_id: str) -> int:
    with _vetting_lock:
        return _vetting_sessions.get(user_id, {}).get("consumed", 0)


# ── Background vetting thread ─────────────────────────────────────────────────

def _background_vetting_loop(user_id: str, roles: List[str]) -> None:
    """
    Cursor-based vetting loop that runs in a daemon thread.

    Flow:
      1. Load a batch of DB jobs matching any of the provided roles
      2. Skip already-seen jobs (in-memory set)
      3. Vet each job; push approved jobs (score >= 0.70) to in-memory list
      4. Pause when approved_count >= VETTING_TARGET
      5. Resume when frontend polls (last_poll timestamp refreshes)
      6. Stop when DB is exhausted or no poll for VETTING_IDLE_TTL seconds
    """
    import time

    try:
        from services.supabase_service import get_supabase_service
        from agents.nodes.vetting import (
            fetch_user_profile,
            extract_user_titles,
            calculate_query_match,
            calculate_title_similarity,
            calculate_skill_match,
            calculate_experience_alignment,
            calculate_location_fit,
            calculate_final_score,
            _compute_years_from_experience,
            MIN_SCORE_THRESHOLD,
        )

        db = get_supabase_service()

        _vs_set_status(user_id, "processing")
        _vs_update_poll(user_id)

        # Fetch user profile once
        user_profile = fetch_user_profile(user_id)
        if not user_profile:
            logger.warning("Vetting thread: no profile for user=%s, aborting", redact_uid(user_id))
            _vs_set_status(user_id, "done")
            return

        user_titles = extract_user_titles(user_profile)
        user_skills = user_profile.get("skills", [])
        user_years = _compute_years_from_experience(user_profile.get("experience", []))
        user_location = user_profile.get("location", "")

        user_latest_title = ""
        experience = user_profile.get("experience", [])
        if experience and isinstance(experience, list):
            latest = experience[0]
            if isinstance(latest, dict):
                user_latest_title = latest.get("job_title") or latest.get("title", "")

        # Use first role as primary query-match signal
        search_query = roles[0] if roles else ""

        cursor = 0
        approved_count = 0
        db_exhausted = False

        logger.info("Vetting thread started for user=%s, roles=%s", redact_uid(user_id), roles)

        while not db_exhausted:
            # ── TTL watchdog ──────────────────────────────────────────────
            idle_secs = time.time() - _vs_get_poll(user_id)
            if idle_secs > VETTING_IDLE_TTL:
                logger.info("Vetting thread: %.0fs idle, stopping", idle_secs)
                break

            # ── Pause when buffer ahead of consumer is full ────────────────
            approved_count = _vs_job_count(user_id)
            consumed = _vs_get_consumed(user_id)
            if (approved_count - consumed) >= VETTING_BUFFER:
                time.sleep(1)
                continue

            # ── Load next batch from DB ───────────────────────────────────
            batch = db.get_jobs_for_roles(roles, offset=cursor, limit=VETTING_BATCH_SIZE)
            cursor += len(batch)

            if not batch:
                db_exhausted = True
                logger.info("Vetting thread: DB exhausted at cursor=%d", cursor)
                break

            # ── Vet each job in the batch ─────────────────────────────────
            for raw_job in batch:
                # Inner TTL check
                if time.time() - _vs_get_poll(user_id) > VETTING_IDLE_TTL:
                    logger.info("Vetting thread: TTL expired inside batch, stopping")
                    db_exhausted = True
                    break

                job_id_key = raw_job.get("job_id", "")
                if not job_id_key or _vs_is_seen(user_id, job_id_key):
                    continue
                _vs_mark_seen(user_id, job_id_key)

                job = _normalize_job_record_for_vetting(raw_job)

                try:
                    query_score   = calculate_query_match(search_query, job.get("title", ""))
                    title_score   = calculate_title_similarity(user_titles, job.get("title", ""))
                    skill_score, matching_skills, skill_gaps = calculate_skill_match(
                        user_skills, job.get("skills", [])
                    )
                    exp_score = calculate_experience_alignment(
                        user_years, user_latest_title, job.get("experience_required")
                    )
                    loc_score = calculate_location_fit(
                        user_location, job.get("location", ""), job.get("employment_type")
                    )
                    final_score = calculate_final_score({
                        "query_match":          query_score,
                        "title_similarity":     title_score,
                        "skill_match":          skill_score,
                        "experience_alignment": exp_score,
                        "location_fit":         loc_score,
                    })
                except Exception as score_err:
                    logger.error("Vetting thread: scoring error for job=%s: %s", job_id_key, score_err)
                    continue

                if final_score < MIN_SCORE_THRESHOLD:
                    continue

                confidence = "high" if final_score >= 0.80 else "medium" if final_score >= 0.70 else "low"

                vetted = {
                    "job_id":          job_id_key,
                    "job_data":        job,
                    "match_score":     final_score,
                    "confidence":      confidence,
                    "skill_gaps":      skill_gaps,
                    "matching_skills": matching_skills,
                }
                _vs_push_job(user_id, vetted)
                approved_count += 1
                logger.debug("Vetting approved: %s score=%.2f", job.get('title', '?'), final_score)

                if (approved_count - _vs_get_consumed(user_id)) >= VETTING_BUFFER:
                    break

        _vs_set_status(user_id, "done")
        final_count = _vs_job_count(user_id)
        logger.info("Vetting thread done: %d jobs approved", final_count)

    except Exception as e:
        logger.error("Vetting thread fatal error: %s", e, exc_info=True)
        _vs_set_status(user_id, "done")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route("/api/jobs/start-vetting", methods=["POST", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def start_vetting_endpoint():
    """
    Start a background vetting session for the given user and roles.

    Body: { "user_id": "...", "roles": ["Backend Developer", "Python Engineer"] }
    Returns immediately. Client polls GET /api/jobs/results.
    """
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        data = request.get_json() or {}
        user_id = data.get("user_id")
        roles   = data.get("roles", [])

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        if not roles or not isinstance(roles, list):
            return jsonify({"error": "roles must be a non-empty array"}), 400

        # Reset session state
        _vs_clear(user_id)
        _vs_update_poll(user_id)

        # Kick off daemon thread
        t = threading.Thread(
            target=_background_vetting_loop,
            args=(user_id, roles),
            daemon=True,
        )
        t.start()

        logger.info("Start-vetting thread started for user=%s, roles=%s", redact_uid(user_id), roles)
        return jsonify({"success": True, "status": "processing"}), 200

    except Exception as e:
        logger.error("Start-vetting error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/results", methods=["GET", "OPTIONS"])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def vetting_results_endpoint():
    """
    Poll endpoint — returns vetted jobs discovered since index `since`.

    Query params:
        user_id (str): required
        since   (int): index to start from (default 0)

    Response:
        { "jobs": [...], "total": N, "status": "processing" | "done" | "idle" }
    """
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        user_id  = request.args.get("user_id")
        since    = int(request.args.get("since", 0))
        consumed = int(request.args.get("consumed", 0))

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        # Refresh TTL + consumer position so background thread resumes when needed
        _vs_update_poll(user_id)
        _vs_update_consumed(user_id, consumed)

        jobs   = _vs_get_jobs(user_id, since=since)
        total  = _vs_job_count(user_id)
        status = _vs_get_status(user_id)

        # Only signal "buffered" when the buffer genuinely has jobs but none
        # are new (thread paused because buffer is full).  If total==0 the
        # thread is still warming up (e.g. loading the embedding model) and we
        # must keep the client polling, so leave status as "processing".
        if not jobs and status == "processing" and total > 0:
            status = "buffered"

        return jsonify({"jobs": jobs, "total": total, "status": status}), 200

    except Exception as e:
        logger.error("Vetting-results error: %s", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)