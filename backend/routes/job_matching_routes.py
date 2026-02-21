"""
API routes for job matching.
Provides endpoints for syncing jobs and matching user profiles to jobs.
"""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from services.job_matching_service import JobMatchingService
from services.supabase_service import SupabaseService
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

job_matching_bp = Blueprint('job_matching', __name__)

matching_service = JobMatchingService()
supabase_service = SupabaseService()


@job_matching_bp.route('/sync-jobs', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def sync_jobs():
    """
    Inform user to run the standalone script to build embeddings.
    
    Response:
    {
        "status": "info",
        "message": "Please run: python src/build_job_embeddings.py --force"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    return jsonify({
        "status": "info",
        "message": "To build job embeddings, run the standalone script: python src/build_job_embeddings.py --force"
    }), 200


@job_matching_bp.route('/match-jobs', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def match_jobs():
    """
    Match user profile to jobs using 4-component scoring.
    Quiz scores are ignored. Jobs are filtered by recommended roles from user profile.
    
    Request body:
    {
        "user_id": "uuid",  // Required to fetch recommended roles
        "skills": ["Python", "SQL", "Machine Learning"],
        "previous_roles": ["Junior Data Scientist", "ML Intern"],
        "years_of_experience": 2,
        "preferred_location": "Remote",  // Optional, not used in scoring
        "quiz_scores": {  // Optional, ignored in scoring
            "Python": 85.0,
            "SQL": 90.0,
            "Machine Learning": 75.0
        },
        "top_k": 10  // optional, default 10
    }
    
    Response:
    {
        "matches": [
            {
                "job_id": "J1001",
                "job_title": "Data Scientist",
                "job_description": "...",
                "final_score": 0.823,
                "fit_percentage": "82%",
                "component_scores": {
                    "title_similarity": 0.92,
                    "skill_match": 0.75,
                    "green_skills_count": 0.85,
                    "experience_alignment": 1.0
                },
                "skills_required": ["Python", "SQL", "Machine Learning"],
                "matched_skills": ["python", "sql", "machine learning"],
                "missing_skills": [],
                "experience_required": 2,
                "location": "Remote"
            }
        ],
        "total_matches": 10
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Extract user profile
        user_id = data.get("user_id")
        skills = data.get("skills", [])
        previous_roles = data.get("previous_roles", [])
        years_of_experience = data.get("years_of_experience", 0)
        preferred_location = data.get("preferred_location")
        quiz_scores = data.get("quiz_scores")
        top_k = data.get("top_k", 10)
        
        # Fetch recommended roles from user profile if user_id is provided
        recommended_roles = []
        if user_id:
            try:
                profile_response = supabase_service.client.table("user_profiles").select("recommended_roles").eq("user_id", user_id).execute()
                if profile_response.data and len(profile_response.data) > 0:
                    recommended_roles = profile_response.data[0].get("recommended_roles", [])
                    logger.info(f"Found {len(recommended_roles)} recommended roles for user {user_id}")
            except Exception as e:
                logger.error(f"Error fetching recommended roles: {e}")
                # Continue without filtering if fetching fails
        
        # Validate inputs
        if not isinstance(skills, list):
            return jsonify({"error": "skills must be a list"}), 400
        
        if not isinstance(previous_roles, list):
            return jsonify({"error": "previous_roles must be a list"}), 400
        
        try:
            years_of_experience = int(years_of_experience)
        except (ValueError, TypeError):
            return jsonify({"error": "years_of_experience must be a number"}), 400
        
        # Validate quiz_scores format if provided
        if quiz_scores is not None:
            if not isinstance(quiz_scores, dict):
                return jsonify({"error": "quiz_scores must be a dictionary"}), 400
            
            # Validate that all values are numbers between 0-100
            for skill, score in quiz_scores.items():
                try:
                    score_float = float(score)
                    if score_float < 0 or score_float > 100:
                        return jsonify({
                            "error": f"Quiz score for '{skill}' must be between 0-100"
                        }), 400
                    quiz_scores[skill] = score_float
                except (ValueError, TypeError):
                    return jsonify({
                        "error": f"Quiz score for '{skill}' must be a number"
                    }), 400
        
        logger.info(
            f"Job matching request: skills={len(skills)}, previous_roles={len(previous_roles)}, "
            f"experience={years_of_experience}, location={preferred_location}, "
            f"quiz_scores={len(quiz_scores) if quiz_scores else 0} skills"
        )
        
        # Build user profile
        user_profile = {
            "skills": skills,
            "previous_roles": previous_roles,
            "years_of_experience": years_of_experience,
            "preferred_location": preferred_location,
            "recommended_roles": recommended_roles
        }
        
        # Perform matching
        matches = matching_service.match_jobs(user_profile, quiz_scores, top_k)
        
        # Add fit percentage for display
        for match in matches:
            match["fit_percentage"] = f"{int(match['final_score'] * 100)}%"
        
        return jsonify({
            "matches": matches,
            "total_matches": len(matches)
        }), 200
    
    except FileNotFoundError as e:
        logger.error(f"Index not found: {e}")
        return jsonify({
            "error": "Job index not found. Please run /sync-jobs first."
        }), 404
    
    except Exception as e:
        logger.error(f"Error matching jobs: {e}", exc_info=True)
        return jsonify({
            "error": str(e)
        }), 500


@job_matching_bp.route('/job-details/<job_id>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_job_details(job_id):
    """
    Fetch full job details from Supabase by job_id.
    
    Response:
    {
        "job_id": "uuid",
        "job_title": "Software Engineer",
        "job_description": "...",
        "skills_required": ["Python", "SQL"],
        ...
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        job = supabase_service.fetch_job_by_id(job_id)
        
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        return jsonify(job), 200
    
    except Exception as e:
        logger.error(f"Error fetching job details: {e}", exc_info=True)
        return jsonify({
            "error": str(e)
        }), 500


@job_matching_bp.route('/index-info', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_index_info():
    """
    Get information about the current job index state.
    
    Response:
    {
        "has_embeddings": true,
        "has_metadata": true,
        "job_count": 100
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        from pathlib import Path
        import numpy as np
        import json
        
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        models_dir = BASE_DIR / "models"
        embeddings_path = models_dir / "job_embeddings.npy"
        metadata_path = models_dir / "job_metadata.json"
        
        has_embeddings = embeddings_path.exists()
        has_metadata = metadata_path.exists()
        job_count = 0
        
        if has_metadata:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                job_count = len(metadata)
        
        return jsonify({
            "has_embeddings": has_embeddings,
            "has_metadata": has_metadata,
            "job_count": job_count
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting index info: {e}", exc_info=True)
        return jsonify({
            "error": str(e)
        }), 500
