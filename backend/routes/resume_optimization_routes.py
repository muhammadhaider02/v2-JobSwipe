"""
Resume Optimization Routes
API endpoints for job-specific resume optimization using RAG and LLM
"""
from flask import Blueprint, request, jsonify
import logging
import uuid
from datetime import datetime
from services.resume_optimization_service import get_resume_optimization_service
from services.supabase_service import SupabaseService

resume_optimization_bp = Blueprint('resume_optimization', __name__)
logger = logging.getLogger(__name__)


def _is_valid_uuid(val):
    """Check if string is a valid UUID format"""
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False


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
        
        # Optionally persist optimized version when user_id is provided
        saved_version = None
        if user_id:
            if not _is_valid_uuid(user_id):
                return jsonify({"error": "Invalid user_id format - must be a valid UUID"}), 400

            supabase_service = SupabaseService()
            saved_version = supabase_service.save_resume_version(
                user_id=user_id,
                original_json=result['original'],
                optimized_json=result['optimized'],
                job_id=job_id,
                job_title=data.get('job_title'),
                optimization_metadata=result['metadata'],
                is_base_version=data.get('is_base_version', False),
                sections_optimized=sections_to_optimize,
            )

        # Prepare response
        response = {
            "success": True,
            "original": result['original'],
            "optimized": result['optimized'],
            "metadata": result['metadata'],
            "saved_version": saved_version,
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
        
        # Validate UUID format
        if not _is_valid_uuid(user_id):
            return jsonify({"error": "Invalid user_id format - must be a valid UUID"}), 400
        
        supabase_service = SupabaseService()
        saved = supabase_service.save_resume_version(
            user_id=user_id,
            original_json=original_json,
            optimized_json=optimized_json,
            job_id=data.get('job_id'),
            job_title=data.get('job_title'),
            optimization_metadata=data.get('optimization_metadata', {}),
            is_base_version=data.get('is_base_version', False),
            sections_optimized=data.get('sections_optimized', []),
        )

        if saved:
            logger.info(f"Saved resume version {saved.get('version')} for user {user_id}")
            return jsonify({
                "success": True,
                "version_id": saved.get('id'),
                "version": saved.get('version')
            }), 201

        return jsonify({"error": "Failed to save resume"}), 500
            
    except Exception as e:
        logger.error(f"Error saving resume: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500


