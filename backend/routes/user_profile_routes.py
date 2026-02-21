"""
User Profile Routes: Handle user profile and quiz score persistence.
Used to store onboarding data and quiz results for job matching.
"""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from services.supabase_service import SupabaseService
from typing import Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

user_profile_bp = Blueprint('user_profile', __name__)

# Lazy-load Supabase service to avoid blocking during import
_supabase_service = None

def get_supabase_service():
    """Get or create the Supabase service instance (lazy initialization)"""
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseService(use_service_role=True)
    return _supabase_service


@user_profile_bp.route('/user-profile', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def save_user_profile():
    """
    Save user profile from onboarding to Supabase.
    
    Request body:
    {
        "user_id": "uuid",
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "location": "New York",
        "summary": "Software engineer with...",
        "github": "github.com/johndoe",
        "linkedin": "linkedin.com/in/johndoe",
        "portfolio": "johndoe.com",
        "profile_picture_url": "https://...",
        "skills": ["Python", "JavaScript", "React"],
        "previous_roles": ["Software Engineer", "Junior Developer"],
        "years_of_experience": 3,
        "recommended_roles": ["AI Engineer", "ML Engineer"],
        "projects": [
            {
                "name": "Project Name",
                "description": "Description...",
                "link": "github.com/..."
            }
        ],
        "certificates": [
            {
                "name": "AWS Certified",
                "issuer": "Amazon",
                "issue_date": "2024-01-01",
                "expiry_date": "2027-01-01"
            }
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "MIT",
                "start_year": 2018,
                "end_year": 2022,
                "gpa": "3.8"
            }
        ],
        "experience": [
            {
                "company": "Google",
                "role": "Software Engineer",
                "duration": "2022-2024",
                "description": "Built..."
            }
        ]
    }
    
    Response:
    {
        "success": true,
        "user_id": "uuid",
        "message": "Profile saved successfully"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        # Prepare profile data
        profile_data = {
            "user_id": user_id,
            "name": data.get('name'),
            "email": data.get('email'),
            "phone": data.get('phone'),
            "location": data.get('location'),
            "summary": data.get('summary'),
            "github": data.get('github'),
            "linkedin": data.get('linkedin'),
            "portfolio": data.get('portfolio'),
            "profile_picture_url": data.get('profile_picture_url'),
            "skills": data.get('skills', []),
            "previous_roles": data.get('previous_roles', []),
            "years_of_experience": data.get('years_of_experience', 0),
            "recommended_roles": data.get('recommended_roles', []),
            "projects": data.get('projects', []),
            "certificates": data.get('certificates', []),
            "education": data.get('education', []),
            "experience": data.get('experience', []),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Insert or update profile
        response = get_supabase_service().client.table('user_profiles').upsert(
            profile_data,
            on_conflict='user_id'
        ).execute()
        
        if response.data:
            logger.info(f"Saved profile for user {user_id}")
            return jsonify({
                "success": True,
                "user_id": user_id,
                "message": "Profile saved successfully"
            }), 200
        else:
            logger.error(f"Failed to save profile for user {user_id}")
            return jsonify({
                "error": "Failed to save profile"
            }), 500
            
    except Exception as e:
        logger.error(f"Error saving user profile: {e}")
        return jsonify({"error": str(e)}), 500


@user_profile_bp.route('/user-profile/<user_id>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_user_profile(user_id: str):
    """
    Fetch user profile and quiz scores for job matching.
    
    Response:
    {
        "profile": {
            "user_id": "uuid",
            "skills": ["Python", "JavaScript"],
            "previous_roles": ["Software Engineer"],
            "years_of_experience": 3,
            "location": "New York",
            ...
        },
        "quiz_scores": {
            "Python": 85.0,
            "JavaScript": 90.0
        }
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        # Fetch profile
        profile_response = get_supabase_service().client.table('user_profiles').select('*').eq(
            'user_id', user_id
        ).execute()
        
        if not profile_response.data or len(profile_response.data) == 0:
            return jsonify({
                "error": f"Profile not found for user {user_id}"
            }), 404
        
        profile = profile_response.data[0]
        
        # Fetch quiz scores
        quiz_response = get_supabase_service().client.table('user_quiz_scores').select('*').eq(
            'user_id', user_id
        ).execute()
        
        # Aggregate quiz scores by skill (take highest score per skill)
        quiz_scores = {}
        if quiz_response.data:
            for record in quiz_response.data:
                skill = record.get('skill')
                score = record.get('score_percentage', 0)
                
                if skill:
                    # Keep highest score for each skill
                    if skill not in quiz_scores or score > quiz_scores[skill]:
                        quiz_scores[skill] = score
        
        logger.info(f"Fetched profile for user {user_id} with {len(quiz_scores)} quiz scores")
        
        return jsonify({
            "profile": profile,
            "quiz_scores": quiz_scores
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        return jsonify({"error": str(e)}), 500


@user_profile_bp.route('/user-quiz-score', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def save_quiz_score():
    """
    Save quiz score for a user.
    
    Request body:
    {
        "user_id": "uuid",
        "skill": "Python",
        "score_percentage": 85.0,
        "quiz_id": "quiz_uuid",
        "passed": true
    }
    
    Response:
    {
        "success": true,
        "message": "Quiz score saved"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        user_id = data.get('user_id')
        skill = data.get('skill')
        score_percentage = data.get('score_percentage')
        
        if not user_id or not skill or score_percentage is None:
            return jsonify({
                "error": "user_id, skill, and score_percentage are required"
            }), 400
        
        # Prepare quiz score data
        quiz_score_data = {
            "user_id": user_id,
            "skill": skill,
            "score_percentage": float(score_percentage),
            "quiz_id": data.get('quiz_id'),
            "passed": data.get('passed', False),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Insert quiz score
        response = get_supabase_service().client.table('user_quiz_scores').insert(
            quiz_score_data
        ).execute()
        
        if response.data:
            logger.info(f"Saved quiz score for user {user_id}, skill {skill}: {score_percentage}%")
            return jsonify({
                "success": True,
                "message": "Quiz score saved"
            }), 200
        else:
            logger.error(f"Failed to save quiz score for user {user_id}")
            return jsonify({
                "error": "Failed to save quiz score"
            }), 500
            
    except Exception as e:
        logger.error(f"Error saving quiz score: {e}")
        return jsonify({"error": str(e)}), 500
