print("=" * 60, flush=True)
print("STARTING APP.PY IMPORTS", flush=True)
print("=" * 60, flush=True)

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS, cross_origin
print("✓ Flask imports complete", flush=True)

import os
import re
import uuid
import threading
print("✓ Standard library imports complete", flush=True)

from pdfminer.high_level import extract_text
from docx import Document
print("✓ Document processing imports complete", flush=True)

from utils.section_splitter import (
    split_resume_into_sections,
    print_sections,
    parse_projects_from_text,
    parse_skills_from_text,
)
print("✓ Utils imports complete", flush=True)

from src.llama_refiner import refine_resume
from src.updated_query import suggest_roles as get_role_recommendations
from src.skill_gap_analysis import analyze_skill_gap
from src.skill_enrichment import enrich_skills
print("✓ Src imports complete", flush=True)

print("✓ Importing learning_resources...", flush=True)
from routes.learning_resources import learning_resources_bp
print("✓ Importing skill_resources...", flush=True)
from routes.skill_resources import skill_resources_bp
print("✓ Importing quiz_routes...", flush=True)
from routes.quiz_routes import quiz_bp
print("✓ Importing job_routes...", flush=True)
try:
    from routes.job_routes import job_bp
    print("✓ job_routes imported successfully!", flush=True)
except Exception as e:
    print(f"❌ ERROR importing job_routes: {e}", flush=True)
    import traceback
    traceback.print_exc()
    raise
print("✓ Basic routes imported", flush=True)

print("✓ Importing job_matching_routes...", flush=True)
from routes.job_matching_routes import job_matching_bp
print("✓ job_matching_routes imported successfully", flush=True)

print("✓ Importing user_profile_routes...", flush=True)
from routes.user_profile_routes import user_profile_bp
print("✓ user_profile_routes imported successfully", flush=True)

print("✓ Importing resume_routes...", flush=True)
from routes.resume_routes import resume_bp
print("✓ resume_routes imported successfully", flush=True)

print("✓ Importing resume_optimization_routes...", flush=True)
from routes.resume_optimization_routes import resume_optimization_bp
print("✓ resume_optimization_routes imported successfully", flush=True)

print("\n" + "="*60, flush=True)
print("CREATING FLASK APP INSTANCE", flush=True)
print("="*60, flush=True)
app = Flask(__name__)
print("✓ Flask app created successfully", flush=True)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB upload cap

# Register blueprints
print("✓ Registering blueprints...", flush=True)
app.register_blueprint(learning_resources_bp)
app.register_blueprint(skill_resources_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(job_bp)
app.register_blueprint(job_matching_bp)
app.register_blueprint(user_profile_bp)
app.register_blueprint(resume_bp)
app.register_blueprint(resume_optimization_bp)
print("✓ All blueprints registered", flush=True)

print("✓ Setting up CORS...", flush=True)

try:
    CORS(
    app,
    resources={
        "/upload": {"origins": "http://localhost:3000"},
        "/get-llm-results/*": {"origins": "http://localhost:3000"},
        "/recommend-roles": {"origins": "http://localhost:3000"},
        "/analyze-skill-gap": {"origins": "http://localhost:3000"},
        "/learning-resources": {"origins": "http://localhost:3000"},
        "/learning-resources/*": {"origins": "http://localhost:3000"},
        "/skill-resources/*": {"origins": "http://localhost:3000"},
        "/skill-quiz/*": {"origins": "http://localhost:3000"},
        "/quiz-submit": {"origins": "http://localhost:3000"},
        "/quiz-result/*": {"origins": "http://localhost:3000"},
        "/jobs": {"origins": "http://localhost:3000"},
        "/jobs/*": {"origins": "http://localhost:3000"},
        "/match-jobs": {"origins": "http://localhost:3000"},
        "/job-details/*": {"origins": "http://localhost:3000"},
        "/sync-jobs": {"origins": "http://localhost:3000"},
        "/check-index": {"origins": "http://localhost:3000"},
        "/user-profile": {"origins": "http://localhost:3000"},
        "/user-profile/*": {"origins": "http://localhost:3000"},
        "/generate-resume": {"origins": "http://localhost:3000"},
        "/optimize-resume": {"origins": "http://localhost:3000"},
        "/save-optimized-resume": {"origins": "http://localhost:3000"},
        "/resume-versions/*": {"origins": "http://localhost:3000"},
        "/resume-version/*": {"origins": "http://localhost:3000"},
        "/compare-resumes": {"origins": "http://localhost:3000"},
        "/detect-job-role": {"origins": "http://localhost:3000"},
        "/knowledge-base-stats": {"origins": "http://localhost:3000"},
    },
    supports_credentials=False,
    )
    print("✓ CORS configured successfully", flush=True)
except Exception as e:
    print(f"❌ CORS setup failed: {e}", flush=True)
    raise

print("✓ Creating upload folder...", flush=True)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print("✓ Upload folder ready", flush=True)

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

    # Immediate JSON response (return parsed_skills, not enriched)
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
        "skills": parsed_skills,  # Return original parsed skills immediately
        "projects": parsed_projects,
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

    # Start both background threads
    skill_thread = threading.Thread(target=process_skill_enrichment_in_background, daemon=True)
    skill_thread.start()
    
    llm_thread = threading.Thread(target=process_llm_in_background, daemon=True)
    llm_thread.start()

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

    # Include LLM results if completed
    if job["status"] == "completed":
        response["result"] = job["result"]
    elif job["status"] == "failed":
        response["error"] = job["error"]
    
    # Include skill enrichment status and results
    skill_enrichment = job.get("skill_enrichment", {})
    response["skill_enrichment"] = {
        "status": skill_enrichment.get("status", "processing"),
    }
    
    if skill_enrichment.get("status") == "completed":
        response["skill_enrichment"]["skills"] = skill_enrichment.get("skills", [])
    elif skill_enrichment.get("status") == "failed":
        response["skill_enrichment"]["error"] = skill_enrichment.get("error", "Unknown error")

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

        # Save recommended roles to user profile if user_id is provided
        user_id = data.get("user_id")
        if user_id and recommendations:
            try:
                from services.supabase_service import SupabaseService
                supabase_service = SupabaseService(use_service_role=True)
                recommended_role_names = [rec["role"] for rec in recommendations]
                supabase_service.supabase.table("user_profiles").update({
                    "recommended_roles": recommended_role_names
                }).eq("user_id", user_id).execute()
                print(f"Saved {len(recommended_role_names)} recommended roles for user {user_id}")
            except Exception as e:
                print(f"Error saving recommended roles: {e}")
                # Don't fail the request if saving fails

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


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Starting Flask application...")
    print("="*60)
    app.run(debug=True, host="0.0.0.0", port=5000)
