from flask import Flask, request, jsonify, render_template
from flask_cors import CORS, cross_origin
import os
import re
import uuid
import threading
from typing import Any, Dict, List
from pdfminer.high_level import extract_text
from docx import Document
from utils.section_splitter import (
    split_resume_into_sections,
    print_sections,
    parse_skills_from_text,
)
from src.llama_refiner import refine_resume, refine_projects
from src.updated_query import suggest_roles as get_role_recommendations
from src.skill_gap_analysis import analyze_skill_gap
from src.skill_enrichment import enrich_skills
from services.supabase_service import SupabaseService

# Import blueprints
from routes.campaign_routes import campaign_bp
from routes.resume_optimization_routes import resume_optimization_bp
from routes.cover_letter_routes import cover_letter_bp

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB upload cap
CORS(
    app,
    resources={
        "/upload": {"origins": "http://localhost:3000"},
        "/get-llm-results/*": {"origins": "http://localhost:3000"},
        "/recommend-roles": {"origins": "http://localhost:3000"},
        "/analyze-skill-gap": {"origins": "http://localhost:3000"},
        "/save-profile": {"origins": "http://localhost:3000"},
        "/get-profile/*": {"origins": "http://localhost:3000"},
        "/user-profile": {"origins": "http://localhost:3000"},
        "/user-profile/*": {"origins": "http://localhost:3000"},
        "/api/jobs/*": {"origins": "http://localhost:3000"},
        "/cover-letter-templates": {"origins": "http://localhost:3000"},
        "/generate-cover-letter": {"origins": "http://localhost:3000"},
        "/prepare-application-materials": {"origins": "http://localhost:3000"},
        "/application-materials/save-draft": {"origins": "http://localhost:3000"},
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

    # Parse skills (immediate)
    try:
        parsed_skills = parse_skills_from_text(sections.get("Skills", ""))
    except Exception as e:
        parsed_skills = []
        print(f"Error parsing skills: {e}")

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
            print(
                f"\n==== Starting Skill Enrichment for job {job_id} ====",
                flush=True,
            )
            enriched_skills = enrich_skills(text, parsed_skills)
            llm_jobs[job_id]["skill_enrichment"]["status"] = "completed"
            llm_jobs[job_id]["skill_enrichment"]["skills"] = enriched_skills
            print(
                f"\n==== Skill Enrichment COMPLETED for job {job_id} ====",
                flush=True,
            )
        except Exception as e:
            print(
                f"\n==== Skill Enrichment FAILED for job {job_id}: {e} ====",
                flush=True,
            )
            llm_jobs[job_id]["skill_enrichment"]["status"] = "failed"
            llm_jobs[job_id]["skill_enrichment"]["error"] = str(e)

    # Background LLM processing (education + experience)
    def process_llm_in_background():
        import time
        # Stagger slightly to avoid all 3 background jobs hammering the API at once
        time.sleep(0.5)
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

            backend = os.getenv("LLAMA_BACKEND", "openai_compat")
            model_name = os.getenv("LLAMA_MODEL", "Meta-Llama-3.1-8B-Instruct")
            base_url = os.getenv("LLAMA_BASE_URL", "https://api.sambanova.ai/v1")

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
                temperature=0.2,
                max_new_tokens=2000,
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

    # Background Projects LLM (parallel)
    def process_projects_llm_in_background():
        import time
        # Stagger more to prevent hitting rate limit with the other two jobs
        time.sleep(1.0)
        try:
            print(
                f"\n==== Starting Projects LLM for job {job_id} ====",
                flush=True,
            )
            projects_text = sections.get("Projects", "")
            backend = os.getenv("LLAMA_BACKEND", "openai_compat")
            model_name = os.getenv("LLAMA_MODEL", "Meta-Llama-3.1-8B-Instruct")
            base_url = os.getenv("LLAMA_BASE_URL", "https://api.sambanova.ai/v1")

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
            print(
                f"\n==== Projects LLM COMPLETED for job {job_id} ====",
                flush=True,
            )
        except Exception as e:
            print(
                f"\n==== Projects LLM FAILED for job {job_id}: {e} ====",
                flush=True,
            )
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
    origins="http://localhost:3000",
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

        # Process candidates to get actual skill gap percentage
        processed_recommendations = []
        
        # We take the top 20 candidates (from updated_query.py) and analyze their skill gap
        # This ensures we filter/sort based on the ACTUAL skill match percentage, not just semantic relevance
        for candidate in candidates:
            role = candidate["role"]
            
            # Run skill gap analysis for this role
            try:
                gap_data = analyze_skill_gap(role, skills)
                completion_percentage = gap_data.get("completion_percentage", 0)
                
                # Get unique skills from the candidate data
                example_skills = []
                if candidate.get("example_hits"):
                    for hit in candidate["example_hits"]:
                        example_skills.extend(hit.get("skills", []))
                unique_skills = list(dict.fromkeys(example_skills))
                
                processed_recommendations.append({
                    "role": role,
                    "score": completion_percentage,  # Use actual skill match percentage
                    "skills": ", ".join(unique_skills[:9]),
                    "skillGapData": {
                        "existing_skills": gap_data.get("existing_skills", []),
                        "required_skills": gap_data.get("required_skills", []),
                        "completion_percentage": completion_percentage
                    }
                })
                
                print(f"Role: {role}, Skill Match: {completion_percentage}%")
                
            except Exception as e:
                print(f"Error analyzing skill gap for {role}: {e}")
                continue

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
        print(f"Error in recommend_roles: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/analyze-skill-gap", methods=["POST", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
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

        print(f"\n==== SKILL GAP ANALYSIS REQUEST ====")
        print(f"Role: {role}")
        print(f"User Skills: {skills}")

        # Perform skill gap analysis
        result = analyze_skill_gap(role, skills)

        print(f"\n==== SKILL GAP ANALYSIS RESPONSE ====")
        print(f"Existing Skills: {result['existing_skills']}")
        print(f"Required Skills: {result['required_skills']}")
        print(f"Completion: {result['completion_percentage']}%")

        return jsonify(result)

    except ValueError as e:
        # Handle role not found or other validation errors
        print(f"Validation error in analyze_skill_gap: {e}")
        return jsonify({"error": str(e)}), 404

    except Exception as e:
        print(f"Error in analyze_skill_gap: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/save-profile", methods=["POST", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
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

        print(f"\n==== SAVING USER PROFILE ====")
        print(f"User ID: {user_id}")
        print(f"Profile fields: {list(profile_data.keys())}")

        # Save profile to database
        success = supabase_service.upsert_user_profile(user_id, profile_data)

        if success:
            print(f"✅ Profile saved successfully for user {user_id}")
            return jsonify({
                "success": True,
                "message": "Profile saved successfully"
            }), 200
        else:
            print(f"❌ Failed to save profile for user {user_id}")
            return jsonify({
                "success": False,
                "error": "Failed to save profile"
            }), 500

    except Exception as e:
        print(f"Error in save_profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/get-profile/<user_id>", methods=["GET", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
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

        print(f"\n==== FETCHING USER PROFILE ====")
        print(f"User ID: {user_id}")

        # Get profile from database
        profile = supabase_service.get_user_profile(user_id)

        if profile:
            print(f"✅ Profile retrieved successfully for user {user_id}")
            return jsonify({
                "success": True,
                "profile": profile
            }), 200
        else:
            print(f"⚠️  No profile found for user {user_id}")
            return jsonify({
                "success": False,
                "profile": None,
                "message": "No profile found"
            }), 404

    except Exception as e:
        print(f"Error in get_profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/user-profile", methods=["POST", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
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
        print(f"Error in user_profile alias save: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/user-profile/<user_id>", methods=["GET", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
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
        print(f"Error in user_profile alias get: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/vetted", methods=["POST", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def vet_jobs_endpoint():
    """
    Endpoint to vet jobs for a user.

    Default mode uses persisted DB jobs only (no scraping). Set mode="scrape"
    explicitly if you want the original Scout → Enricher → Vetting pipeline.
    
    Request body:
    {
        "user_id": "uuid-string",
        "search_query": "python developer in lahore"
    }
    
    Response:
    {
        "success": true,
        "vetted_jobs": [...],
        "stats": {
            "total_jobs_found": 10,
            "jobs_passed_vetting": 7,
            "top_match_score": 0.85
        }
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        user_id = data.get("user_id")
        search_query = data.get("search_query")
        
        if not user_id or not search_query:
            return jsonify({"error": "user_id and search_query are required"}), 400
        
        mode = str(data.get("mode", "db")).lower()
        result_limit = int(data.get("limit", 10) or 10)
        result_limit = max(1, min(result_limit, 50))

        print(f"\n==== JOB VETTING PIPELINE STARTED ====")
        print(f"User ID: {user_id}")
        print(f"Query: {search_query}\n")
        print(f"Mode: {mode}\n")
        
        # Import agent nodes
        from agents.nodes import digital_scout_node, job_enricher_node, vetting_officer_node
        from agents.state import AgentState
        from langchain_core.messages import HumanMessage
        
        # Initialize state
        state: AgentState = {
            "messages": [HumanMessage(content=search_query)],
            "user_id": user_id,
            "user_profile": None,
            "search_query": search_query,
            "raw_job_list": [],
            "scraping_status": "pending",
            "current_page": 1,
            "vetted_jobs": [],
            "target_job": None,
            "optimized_materials": None,
            "human_approval": None,
            "error": None,
            "retry_count": 0
        }
        
        if mode == "scrape":
            # Optional legacy mode: scrape fresh jobs first.
            print("\n=== STEP 1: DIGITAL SCOUT ===")
            scout_result = digital_scout_node(state)
            state.update(scout_result)

            raw_jobs = state.get("raw_job_list", [])
            if not raw_jobs:
                return jsonify({
                    "success": True,
                    "vetted_jobs": [],
                    "stats": {
                        "total_jobs_found": 0,
                        "jobs_passed_vetting": 0,
                        "top_match_score": 0
                    },
                    "message": "No jobs found matching your query",
                    "source": "scrape"
                }), 200

            print("\n=== STEP 2: JOB ENRICHER ===")
            enricher_result = job_enricher_node(state)
            state.update(enricher_result)
            raw_jobs = state.get("raw_job_list", [])
        else:
            # Default mode: use already persisted jobs from DB.
            print("\n=== STEP 1: LOAD JOBS FROM DATABASE ===")
            raw_jobs = _load_db_jobs_for_vetting(search_query=search_query)
            state["raw_job_list"] = raw_jobs

            if not raw_jobs:
                return jsonify({
                    "success": True,
                    "vetted_jobs": [],
                    "stats": {
                        "total_jobs_found": 0,
                        "jobs_passed_vetting": 0,
                        "top_match_score": 0
                    },
                    "message": "No stored jobs found in database",
                    "source": "db"
                }), 200
        
        # Step 3: Vetting Officer - Score and filter
        print("\n=== STEP 3: VETTING OFFICER ===")
        vetting_result = vetting_officer_node(state)
        state.update(vetting_result)
        
        vetted_jobs = state.get("vetted_jobs", [])[:result_limit]
        
        # Build stats
        stats = {
            "total_jobs_found": len(raw_jobs),
            "jobs_passed_vetting": len(state.get("vetted_jobs", [])),
            "returned_jobs": len(vetted_jobs),
            "top_match_score": vetted_jobs[0]["match_score"] if vetted_jobs else 0,
            "average_match_score": sum(j["match_score"] for j in vetted_jobs) / len(vetted_jobs) if vetted_jobs else 0,
            "high_confidence_matches": sum(1 for j in vetted_jobs if j["match_score"] >= 0.75),
            "medium_confidence_matches": sum(1 for j in vetted_jobs if 0.60 <= j["match_score"] < 0.75)
        }
        
        print(f"\n==== PIPELINE COMPLETE ====")
        print(f"✅ {stats['total_jobs_found']} candidate jobs loaded")
        print(f"✅ {stats['jobs_passed_vetting']} jobs passed vetting")
        print(f"✅ {stats['returned_jobs']} jobs returned")
        print(f"✅ Top match score: {stats['top_match_score']:.2f}\n")
        
        return jsonify({
            "success": True,
            "vetted_jobs": vetted_jobs,
            "stats": stats,
            "source": mode,
        }), 200
    
    except Exception as e:
        print(f"❌ Error in vet_jobs endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>", methods=["GET", "OPTIONS"])
@cross_origin(
    origins="http://localhost:3000",
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
        print(f"Error in get job detail: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
