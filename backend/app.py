from flask import Flask, request, jsonify, render_template
from flask_cors import CORS, cross_origin
import os
import re
import json
import uuid
import threading
from pdfminer.high_level import extract_text
from docx import Document
from utils.section_splitter import (
    split_resume_into_sections, 
    print_sections,
    parse_projects_from_text, 
    parse_skills_from_text
)
from models.llama_refiner import refine_resume
from models.updated_query import suggest_roles as get_role_recommendations

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB upload cap
CORS(app, resources={
    "/upload": {"origins": "http://localhost:3000"},
    "/get-llm-results/*": {"origins": "http://localhost:3000"},
    "/recommend-roles": {"origins": "http://localhost:3000"}
}, supports_credentials=False)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory storage for LLM processing jobs
llm_jobs = {}  # {job_id: {'status': 'processing'|'completed'|'failed', 'result': {...}, 'error': str}}

def extract_text_from_file(path):
    ext = os.path.splitext(path)[-1].lower()
    if ext == '.pdf':
        # Try pdfminer, fallback to PyPDF2
        try:
            return extract_text(path)
        except Exception as e1:
            try:
                import PyPDF2
                text = ""
                with open(path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += (page.extract_text() or "") + "\n"
                if not text.strip():
                    raise ValueError("Empty PDF text after extraction")
                return text.strip()
            except Exception as e2:
                raise RuntimeError(f"PDF extraction failed: {e1} | fallback: {e2}")
    elif ext == '.docx':
        try:
            doc = Document(path)
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            raise RuntimeError(f"DOCX extraction failed: {e}")
    else:
        raise ValueError("Unsupported file type")

def extract_contact_info(text):
    """
    Extract contact information (email, phone, LinkedIn, GitHub) from resume text
    """
    contact_info = {
        'email': None,
        'phone': None,
        'linkedin': None,
        'github': None
    }
    
    # Extract email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    if emails:
        contact_info['email'] = emails[0]
    
    # Extract phone number (various formats)
    phone_pattern = r'\+?\d[\d\s\-()]{7,}\d'
    phones = re.findall(phone_pattern, text)
    # Filter out years and other numbers
    valid_phones = [p for p in phones if len(re.sub(r'[^\d]', '', p)) >= 10]
    if valid_phones:
        contact_info['phone'] = valid_phones[0].strip()
    
    # Extract LinkedIn URL (various formats)
    # Handles: linkedin.com/in/username, www.linkedin.com/in/username, http(s)://linkedin.com/in/username
    linkedin_patterns = [
        r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+/?',
        r'(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w\-]+/?',
        r'linkedin\.com/in/[\w\-]+/?'
    ]
    
    for pattern in linkedin_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            url = matches[0].rstrip('/')
            # Ensure it starts with https://
            if not url.startswith('http'):
                url = 'https://' + url
            contact_info['linkedin'] = url
            break
    
    # Extract GitHub URL (various formats)
    # Handles: github.com/username, www.github.com/username, http(s)://github.com/username
    github_patterns = [
        r'(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?',
        r'github\.com/[\w\-]+/?'
    ]
    
    for pattern in github_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            url = matches[0].rstrip('/')
            # Ensure it starts with https://
            if not url.startswith('http'):
                url = 'https://' + url
            # Filter out common false positives (like github.com/repos, github.com/issues)
            if not re.search(r'github\.com/(repos|issues|pulls|stars|notifications|settings)', url, re.IGNORECASE):
                contact_info['github'] = url
                break
    
    return contact_info

@app.route('/')
def index():
    """Serve the upload page"""
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000", methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"], max_age=86400)
def upload_resume():
    # Short-circuit preflight and readiness checks
    if request.method == 'OPTIONS':
        return ('', 204)
    if request.method == 'GET':
        return jsonify({'status': 'ready'}), 200

    # POST: handle upload
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'error': 'Empty file'}), 400
        path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(path)

        # Step 1: Extract text
        try:
            text = extract_text_from_file(path)
        except Exception as ex:
            return jsonify({'error': f'Failed to extract text from file: {ex}'}), 400
    except Exception as ex:
        return jsonify({'error': f'Upload handling failed: {ex}'}), 400

    # Step 2: Extract contact information (including LinkedIn and GitHub)
    contact_info = extract_contact_info(text)
    
    print("\n==== Contact Information ====")
    print(f"Email: {contact_info['email']}")
    print(f"Phone: {contact_info['phone']}")
    print(f"LinkedIn: {contact_info['linkedin']}")
    print(f"GitHub: {contact_info['github']}")

    # Step 3: Split resume into sections
    sections = split_resume_into_sections(text)
    
    # Print sections to terminal for debugging
    print_sections(sections)

    # Parse projects/skills via regex helpers
    try:
        parsed_projects = parse_projects_from_text(sections.get('Projects', ''))
        parsed_skills = parse_skills_from_text(sections.get('Skills', ''))
    except Exception as e:
        parsed_projects = []
        parsed_skills = []
        print(f"Error parsing projects/skills: {e}")

    # Build immediate response with extracted data (contact, skills, projects)
    immediate_response = {
        'contact_info': {
            'name': '',  # Can be extracted from first line of resume
            'email': contact_info.get('email', ''),
            'phone': contact_info.get('phone', '')
        },
        'profile': {
            'github': contact_info.get('github', ''),
            'linkedin': contact_info.get('linkedin', '')
        },
        'skills': parsed_skills,
        'projects': parsed_projects
    }

    # Generate job ID for LLM processing
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    llm_jobs[job_id] = {
        'status': 'processing',
        'result': None,
        'error': None
    }

    # Start LLM processing in background thread
    def process_llm_in_background():
        try:
            print(f"\n==== Starting LLM Background Processing for job {job_id} ====", flush=True)
            
            # Process Education and Experience sections (slow sections)
            ordered_for_llm = ['Education', 'Experience']
            resume_text_for_llm = "\n\n".join([
                f"{name}:\n{sections.get(name, '')}" for name in ordered_for_llm if sections.get(name, '')
            ])

            backend = os.getenv('LLAMA_BACKEND', 'ollama')
            model_name = os.getenv('LLAMA_MODEL', 'llama3:latest')
            base_url = os.getenv('LLAMA_BASE_URL', 'http://localhost:11434')

            print("\n==== LLM CONFIG ====", flush=True)
            print(f"backend={backend}", flush=True)
            print(f"model={model_name}", flush=True)
            print(f"base_url={base_url}", flush=True)
            print("\n==== LLM INPUT: Resume text (Education/Experience ONLY) ====", flush=True)
            print(resume_text_for_llm or "(empty)", flush=True)

            # Call LLM
            refined = refine_resume(
                resume_text=resume_text_for_llm,
                backend=backend,
                model=model_name,
                base_url=base_url,
                temperature=0.1,
                max_new_tokens=1200,
                request_timeout_s=300.0,
            )
            
            # Update job status
            llm_jobs[job_id]['status'] = 'completed'
            llm_jobs[job_id]['result'] = refined
            
            print(f"\n==== LLM Background Processing COMPLETED for job {job_id} ====", flush=True)
            
        except Exception as e:
            print(f"\n==== LLM Background Processing FAILED for job {job_id}: {e} ====", flush=True)
            llm_jobs[job_id]['status'] = 'failed'
            llm_jobs[job_id]['error'] = str(e)

    # Start background thread
    thread = threading.Thread(target=process_llm_in_background, daemon=True)
    thread.start()

    # Return immediate response with job_id
    return jsonify({
        'job_id': job_id,
        **immediate_response
    })

@app.route('/get-llm-results/<job_id>', methods=['GET', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000", methods=["GET", "OPTIONS"], allow_headers=["Content-Type"], max_age=86400)
def get_llm_results(job_id):
    """
    Poll endpoint to check if LLM processing is complete
    Returns: { 'status': 'processing'|'completed'|'failed', 'result': {...} or 'error': '...' }
    """
    if request.method == 'OPTIONS':
        return ('', 204)
    
    if job_id not in llm_jobs:
        return jsonify({'status': 'not_found', 'error': 'Job ID not found'}), 404
    
    job = llm_jobs[job_id]
    
    response = {
        'status': job['status']
    }
    
    if job['status'] == 'completed':
        response['result'] = job['result']
    elif job['status'] == 'failed':
        response['error'] = job['error']
    
    return jsonify(response)

@app.route('/recommend-roles', methods=['POST', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000", methods=["POST", "OPTIONS"], allow_headers=["Content-Type"], max_age=86400)
def recommend_roles():
    """
    Endpoint to get role recommendations based on user skills
    Expects JSON: { "skills": ["Python", "React", ...] }
    Returns: { "recommendations": [{"role": "...", "score": ..., "skills": "..."}, ...] }
    """
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        data = request.get_json()
        if not data or 'skills' not in data:
            return jsonify({'error': 'No skills provided'}), 400
        
        skills = data['skills']
        if not isinstance(skills, list) or len(skills) == 0:
            return jsonify({'error': 'Skills must be a non-empty array'}), 400
        
        # Get top 10 role recommendations
        top_k = data.get('top_k', 10)
        
        print(f"\n==== ROLE RECOMMENDATION REQUEST ====")
        print(f"Skills: {skills}")
        print(f"Top K: {top_k}")
        
        # Query the roles using the existing function
        result = get_role_recommendations(skills, top_k=top_k)
        
        # Transform the result to match frontend expectations
        # The function returns: { "candidates": [...], "choices": [...], ... }
        # Frontend expects: { "recommendations": [{"role": "...", "score": ..., "skills": "..."}, ...] }
        
        candidates = result.get('candidates', [])
        
        # Find the maximum score for normalization
        max_score = max([c['aggregated_score'] for c in candidates], default=1.0)
        # Prevent division by zero
        if max_score == 0:
            max_score = 1.0
        
        recommendations = []
        for candidate in candidates:
            # Get example skills from the first hit
            example_skills = []
            if candidate.get('example_hits'):
                for hit in candidate['example_hits']:
                    example_skills.extend(hit.get('skills', []))
            
            # Remove duplicates while preserving order
            unique_skills = list(dict.fromkeys(example_skills))
            
            # Normalize score to percentage (0-100%)
            raw_score = candidate['aggregated_score']
            percentage_score = (raw_score / max_score) * 100
            
            print(f"Role: {candidate['role']}, Raw Score: {raw_score:.4f}, Percentage: {percentage_score:.1f}%")
            
            recommendations.append({
                'role': candidate['role'],
                'score': round(percentage_score, 1),  # Return as percentage
                'skills': ', '.join(unique_skills[:10])  # Limit to 10 skills for display
            })
        
        return jsonify({
            'recommendations': recommendations,
            'skills_used': skills,
            'suggest_more_skills': result.get('suggest_more_skills')
        })
    
    except Exception as e:
        print(f"Error in recommend_roles: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
