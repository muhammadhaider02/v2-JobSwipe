from flask import Flask, request, jsonify, render_template
from flask_cors import CORS, cross_origin
import os
import re
import json
import uuid
import threading
from pdfminer.high_level import extract_text
from docx import Document
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from utils.section_splitter import (
    split_resume_into_sections, 
    print_sections,
    preprocess_text_for_ner,
    merge_subword_entities,
    normalize_entity_labels,
    extract_with_regex_fallback,
    deduplicate_entities,
    filter_low_confidence_entities,
    postprocess_education_entities,
    split_experience_into_jobs,
    postprocess_experience_entities
)
from models.llama_refiner import refine_resume
from models.query_roles import query_roles as get_role_recommendations

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

# Load model once at startup
tokenizer = AutoTokenizer.from_pretrained("yashpwr/resume-ner-bert-v2")
model = AutoModelForTokenClassification.from_pretrained("yashpwr/resume-ner-bert-v2")
nlp = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

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

def process_section_with_ner(section_text, section_name, confidence_threshold=0.5):
    """
    Process a section with NER model and apply all preprocessing/postprocessing
    """
    if not section_text or not section_text.strip():
        return []
    
    # Optional: For Experience, split into job chunks and process per chunk
    if section_name == 'Experience':
        jobs = split_experience_into_jobs(section_text)
        print(f"\n[DEBUG] Split Experience into {len(jobs)} job block(s)")
        entities = []
        for idx, job_text in enumerate(jobs, 1):
            preprocessed_text = preprocess_text_for_ner(job_text, section_name)
            if not preprocessed_text:
                continue
            print(f"\n[DEBUG] Preprocessed Experience job #{idx}:")
            print(f"{preprocessed_text[:200]}..." if len(preprocessed_text) > 200 else preprocessed_text)
            try:
                # Token-length safeguard: truncate inputs >512 tokens (approx by chars)
                safe_input = preprocessed_text
                if len(preprocessed_text) > 4000:  # rough proxy; avoids tokenizer call here
                    safe_input = preprocessed_text[:4000]
                results = nlp(safe_input)
                entities.extend([
                    {"entity": r["entity_group"], "text": r["word"], "score": float(r["score"])}
                    for r in results
                ])
            except Exception as e:
                print(f"[ERROR] NER model failed for Experience job #{idx}: {e}")
    else:
        # Step 1: Preprocess text for NER
        preprocessed_text = preprocess_text_for_ner(section_text, section_name)
        if not preprocessed_text:
            return []
        print(f"\n[DEBUG] Preprocessed {section_name}:")
        print(f"{preprocessed_text[:200]}..." if len(preprocessed_text) > 200 else preprocessed_text)
        # Step 2: Run NER model
        try:
            results = nlp(preprocessed_text)
            # Convert to our format
            entities = [
                {"entity": r["entity_group"], "text": r["word"], "score": float(r["score"])}
                for r in results
            ]
        except Exception as e:
            print(f"[ERROR] NER model failed for {section_name}: {e}")
            entities = []
    
    # Step 3: Merge subword tokens
    entities = merge_subword_entities(entities)
    
    # Step 4: Normalize entity labels based on context
    entities = normalize_entity_labels(entities, section_name)
    
    # Step 5: Filter low confidence entities (use higher threshold for Experience)
    threshold = confidence_threshold if section_name != 'Experience' else max(0.6, confidence_threshold)
    entities = filter_low_confidence_entities(entities, threshold)
    
    # Step 6: Add regex-based fallback entities
    fallback_entities = extract_with_regex_fallback(section_text, section_name)
    entities.extend(fallback_entities)
    
    # Step 7: Deduplicate
    entities = deduplicate_entities(entities)
    
    # Step 8: Section-specific postprocessing (e.g., split composite Education entities)
    if section_name == 'Education':
        # Use the preprocessed text (headers stripped, bullets normalized)
        entities = postprocess_education_entities(entities, preprocessed_text)

    # Step 9: Experience-specific postprocessing
    if section_name == 'Experience':
        entities = postprocess_experience_entities(entities, section_text)

    # Step 10: Sort by score (highest first)
    entities.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return entities

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

    # Step 4: Process Profile and Skills sections with NER (fast sections only)
    sections_to_process_now = ['Profile', 'Skills']
    
    section_entities = {}
    
    print("\n==== Processing Fast Sections with Enhanced NER Pipeline ====")
    
    for section_name in sections_to_process_now:
        section_text = sections.get(section_name, '')
        
        print(f"\n{'='*60}")
        print(f"Processing: {section_name}")
        print(f"{'='*60}")
        
        if section_text:
            entities = process_section_with_ner(
                section_text, 
                section_name, 
                confidence_threshold=0.5
            )
            section_entities[section_name] = entities
            
            # Print results
            print(f"\nExtracted {len(entities)} entities:")
            for e in entities:
                source = f" [{e['source']}]" if 'source' in e else ""
                print(f"  {e['entity']}: {e['text']} (confidence: {e['score']:.3f}){source}")
        else:
            section_entities[section_name] = []
            print("  (Empty section)")

    # Parse projects/skills via regex helpers
    try:
        from utils.section_splitter import parse_projects_from_text, parse_skills_from_text
        parsed_projects = parse_projects_from_text(sections.get('Projects', ''))
        parsed_skills = parse_skills_from_text(sections.get('Skills', ''))
    except Exception as e:
        parsed_projects = []
        parsed_skills = []
        print(f"Error parsing projects/skills: {e}")

    # Extract profile/summary from NLP
    profile_entities = section_entities.get('Profile', [])
    summary_text = ''
    for entity in profile_entities:
        if entity['entity'] in ['Profile', 'Summary', 'PROFILE']:
            summary_text = entity.get('text', '')
            break
    
    # If no summary from entities, try to extract first few sentences from Profile section
    if not summary_text and sections.get('Profile'):
        profile_text = sections['Profile'].strip()
        sentences = re.split(r'[.!?]\s+', profile_text)
        summary_text = '. '.join(sentences[:2]) + '.' if sentences else profile_text[:200]

    # Build immediate response with NLP-extracted data (contact, profile, skills, projects)
    immediate_response = {
        'contact_info': {
            'name': '',  # Can be extracted from first line of resume
            'email': contact_info.get('email', ''),
            'phone': contact_info.get('phone', '')
        },
        'profile': {
            'summary': summary_text,
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
                ner_output=None,
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
    Returns: { "recommendations": [{"role": "...", "score": ...}, ...] }
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
        recommendations = get_role_recommendations(skills, top_k=top_k)
        
        return jsonify({
            'recommendations': recommendations,
            'skills_used': skills
        })
    
    except Exception as e:
        print(f"Error in recommend_roles: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
