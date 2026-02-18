"""
Resume Optimization Routes
API endpoints for job-specific resume optimization using RAG and LLM
"""
from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
from services.resume_optimization_service import get_resume_optimization_service
from services.supabase_service import SupabaseService

resume_optimization_bp = Blueprint('resume_optimization', __name__)
logger = logging.getLogger(__name__)


@resume_optimization_bp.route('/optimize-resume', methods=['POST'])
def optimize_resume():
    """
    Optimize resume for a specific job description
    
    Request JSON:
    {
        "resume_json": {...},  # User's resume data
        "job_description": "...",  # Target job posting
        "sections_to_optimize": ["experience", "skills", "summary"],  # Optional
        "user_id": "uuid",  # Optional, for saving version
        "job_id": "J1234"  # Optional, for tracking
    }
    
    Response:
    {
        "success": true,
        "original": {...},
        "optimized": {...},
        "metadata": {
            "detected_roles": [...],
            "jd_keywords": [...],
            "optimization_details": {...}
        }
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        resume_json = data.get('resume_json')
        job_description = data.get('job_description')
        
        if not resume_json:
            return jsonify({"error": "resume_json is required"}), 400
        
        if not job_description:
            return jsonify({"error": "job_description is required"}), 400
        
        # Optional parameters
        sections_to_optimize = data.get('sections_to_optimize', ["experience", "skills", "summary"])
        user_id = data.get('user_id')
        job_id = data.get('job_id')
        
        logger.info(f"Optimizing resume for user {user_id or 'anonymous'}, job {job_id or 'N/A'}")
        
        # Get optimization service
        optimization_service = get_resume_optimization_service()
        
        # Perform optimization
        result = optimization_service.optimize_resume(
            resume_json=resume_json,
            job_description=job_description,
            sections_to_optimize=sections_to_optimize
        )
        
        # Prepare response
        response = {
            "success": True,
            "original": result['original'],
            "optimized": result['optimized'],
            "metadata": result['metadata']
        }
        
        logger.info("Resume optimization successful")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error optimizing resume: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500


@resume_optimization_bp.route('/save-optimized-resume', methods=['POST'])
def save_optimized_resume():
    """
    Save an optimized resume version to database
    
    Request JSON:
    {
        "user_id": "uuid",
        "original_json": {...},
        "optimized_json": {...},
        "job_id": "J1234",  # Optional
        "job_title": "Software Engineer",  # Optional
        "optimization_metadata": {...},  # From optimize-resume response
        "sections_optimized": ["experience", "skills"]
    }
    
    Response:
    {
        "success": true,
        "version_id": 123,
        "version": 1
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        user_id = data.get('user_id')
        original_json = data.get('original_json')
        optimized_json = data.get('optimized_json')
        
        if not user_id or not original_json or not optimized_json:
            return jsonify({"error": "user_id, original_json, and optimized_json are required"}), 400
        
        # Initialize Supabase service
        supabase_service = SupabaseService()
        
        # Get next version number for this user
        existing_resumes = supabase_service.supabase.table('resumes')\
            .select('version')\
            .eq('user_id', user_id)\
            .order('version', desc=True)\
            .limit(1)\
            .execute()
        
        next_version = 1
        if existing_resumes.data:
            next_version = existing_resumes.data[0]['version'] + 1
        
        # Prepare resume record
        resume_record = {
            "user_id": user_id,
            "original_json": original_json,
            "optimized_json": optimized_json,
            "job_id": data.get('job_id'),
            "job_title": data.get('job_title'),
            "optimization_metadata": data.get('optimization_metadata', {}),
            "version": next_version,
            "is_base_version": data.get('is_base_version', False),
            "sections_optimized": data.get('sections_optimized', []),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Insert into database
        result = supabase_service.supabase.table('resumes').insert(resume_record).execute()
        
        if result.data:
            logger.info(f"Saved resume version {next_version} for user {user_id}")
            return jsonify({
                "success": True,
                "version_id": result.data[0]['id'],
                "version": next_version
            }), 201
        else:
            return jsonify({"error": "Failed to save resume"}), 500
            
    except Exception as e:
        logger.error(f"Error saving resume: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500


@resume_optimization_bp.route('/resume-versions/<user_id>', methods=['GET'])
def get_resume_versions(user_id):
    """
    Get all resume versions for a user
    
    Response:
    {
        "success": true,
        "versions": [
            {
                "id": 1,
                "version": 1,
                "job_title": "...",
                "sections_optimized": [...],
                "created_at": "...",
                "is_base_version": false
            }
        ]
    }
    """
    try:
        supabase_service = SupabaseService()
        
        # Fetch all versions for user
        result = supabase_service.supabase.table('resumes')\
            .select('id, version, job_id, job_title, sections_optimized, created_at, is_base_version')\
            .eq('user_id', user_id)\
            .order('version', desc=True)\
            .execute()
        
        return jsonify({
            "success": True,
            "versions": result.data
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching resume versions: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500


@resume_optimization_bp.route('/resume-version/<int:version_id>', methods=['GET'])
def get_resume_version(version_id):
    """
    Get a specific resume version by ID
    
    Response:
    {
        "success": true,
        "resume": {
            "id": 1,
            "original_json": {...},
            "optimized_json": {...},
            "optimization_metadata": {...},
            ...
        }
    }
    """
    try:
        supabase_service = SupabaseService()
        
        result = supabase_service.supabase.table('resumes')\
            .select('*')\
            .eq('id', version_id)\
            .execute()
        
        if not result.data:
            return jsonify({"error": "Resume version not found"}), 404
        
        return jsonify({
            "success": True,
            "resume": result.data[0]
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching resume version: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500


@resume_optimization_bp.route('/compare-resumes', methods=['POST'])
def compare_resumes():
    """
    Compare two resume versions
    
    Request JSON:
    {
        "version_id_1": 1,
        "version_id_2": 2
    }
    
    Response:
    {
        "success": true,
        "version_1": {...},
        "version_2": {...},
        "differences": {
            "experience": [...],
            "skills": [...],
            "summary": "..."
        }
    }
    """
    try:
        data = request.get_json()
        version_id_1 = data.get('version_id_1')
        version_id_2 = data.get('version_id_2')
        
        if not version_id_1 or not version_id_2:
            return jsonify({"error": "Both version_id_1 and version_id_2 are required"}), 400
        
        supabase_service = SupabaseService()
        
        # Fetch both versions
        result1 = supabase_service.supabase.table('resumes')\
            .select('*')\
            .eq('id', version_id_1)\
            .execute()
        
        result2 = supabase_service.supabase.table('resumes')\
            .select('*')\
            .eq('id', version_id_2)\
            .execute()
        
        if not result1.data or not result2.data:
            return jsonify({"error": "One or both resume versions not found"}), 404
        
        version_1 = result1.data[0]
        version_2 = result2.data[0]
        
        # Compare optimized versions
        differences = _compute_differences(
            version_1.get('optimized_json', version_1.get('original_json')),
            version_2.get('optimized_json', version_2.get('original_json'))
        )
        
        return jsonify({
            "success": True,
            "version_1": {
                "id": version_1['id'],
                "version": version_1['version'],
                "job_title": version_1.get('job_title'),
                "created_at": version_1['created_at']
            },
            "version_2": {
                "id": version_2['id'],
                "version": version_2['version'],
                "job_title": version_2.get('job_title'),
                "created_at": version_2['created_at']
            },
            "differences": differences
        }), 200
        
    except Exception as e:
        logger.error(f"Error comparing resumes: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500


@resume_optimization_bp.route('/detect-job-role', methods=['POST'])
def detect_job_role():
    """
    Detect job role from job description (utility endpoint for testing)
    
    Request JSON:
    {
        "job_description": "..."
    }
    
    Response:
    {
        "success": true,
        "detected_roles": ["Data Science", "AI/ML"],
        "keywords": [...]
    }
    """
    try:
        data = request.get_json()
        job_description = data.get('job_description')
        
        if not job_description:
            return jsonify({"error": "job_description is required"}), 400
        
        optimization_service = get_resume_optimization_service()
        
        detected_roles = optimization_service.detect_job_role(job_description)
        jd_keywords = optimization_service.extract_jd_keywords(job_description)
        
        return jsonify({
            "success": True,
            "detected_roles": detected_roles,
            "keywords": jd_keywords
        }), 200
        
    except Exception as e:
        logger.error(f"Error detecting job role: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500


def _compute_differences(resume1: dict, resume2: dict) -> dict:
    """
    Compute high-level differences between two resume JSONs
    """
    differences = {}
    
    # Compare experience
    exp1 = resume1.get('experience', [])
    exp2 = resume2.get('experience', [])
    if exp1 != exp2:
        differences['experience'] = {
            "changed": True,
            "num_entries_v1": len(exp1),
            "num_entries_v2": len(exp2)
        }
    
    # Compare skills
    skills1 = set(resume1.get('skills', []))
    skills2 = set(resume2.get('skills', []))
    if skills1 != skills2:
        differences['skills'] = {
            "changed": True,
            "added": list(skills2 - skills1),
            "removed": list(skills1 - skills2)
        }
    
    # Compare summary
    summary1 = resume1.get('summary', '')
    summary2 = resume2.get('summary', '')
    if summary1 != summary2:
        differences['summary'] = {
            "changed": True,
            "length_v1": len(summary1),
            "length_v2": len(summary2)
        }
    
    return differences


@resume_optimization_bp.route('/knowledge-base-stats', methods=['GET'])
def get_knowledge_base_stats():
    """
    Get statistics about the resume optimization knowledge base
    
    Response:
    {
        "success": true,
        "stats": {
            "total_chunks": 75,
            "chunk_types": {...},
            "role_coverage": [...]
        }
    }
    """
    try:
        optimization_service = get_resume_optimization_service()
        
        if not optimization_service.knowledge_metadata:
            return jsonify({
                "success": False,
                "error": "Knowledge base not loaded"
            }), 503
        
        # Compute statistics
        chunk_types = {}
        role_tags = {}
        
        for chunk in optimization_service.knowledge_metadata:
            ct = chunk.get('chunk_type', 'unknown')
            chunk_types[ct] = chunk_types.get(ct, 0) + 1
            
            for tag in chunk.get('role_tags', []):
                role_tags[tag] = role_tags.get(tag, 0) + 1
        
        return jsonify({
            "success": True,
            "stats": {
                "total_chunks": len(optimization_service.knowledge_metadata),
                "embedding_dimension": optimization_service.faiss_index.d if optimization_service.faiss_index else 0,
                "chunk_types": chunk_types,
                "role_coverage": role_tags
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting KB stats: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500
