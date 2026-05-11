"""
API routes for learning resources.
Provides endpoints for fetching learning resources for skills.
"""
import os
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from services.learning_resources_service import LearningResourcesService
from typing import List

learning_resources_bp = Blueprint('learning_resources', __name__)
service = LearningResourcesService()
CORS_ORIGIN = os.environ.get("CORS_ALLOWED_ORIGIN", "http://localhost:3000")


@learning_resources_bp.route('/learning-resources', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_learning_resources():
    """
    Generate learning resources for given skills.
    
    Request body:
    {
        "skills": ["python", "sql", "communication skills"],
        "num_google_results": 7,  // optional, default 7
        "num_youtube_results": 3   // optional, default 3
    }
    
    Response:
    {
        "resources": [
            {
                "skill": "python",
                "google_results": [...],
                "youtube_playlists": [...],
                "total_confidence": 0.85
            }
        ],
        "total_skills": 3,
        "status": "success"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        
        if not data or "skills" not in data:
            return jsonify({
                "error": "Missing 'skills' in request body",
                "status": "error"
            }), 400
        
        skills = data.get("skills", [])
        
        if not isinstance(skills, list) or len(skills) == 0:
            return jsonify({
                "error": "Skills must be a non-empty array",
                "status": "error"
            }), 400
        
        # Optional parameters
        num_google = data.get("num_google_results", 7)
        num_youtube = data.get("num_youtube_results", 3)
        
        print(f"\n{'='*60}")
        print(f"LEARNING RESOURCES REQUEST")
        print(f"{'='*60}")
        print(f"Skills: {skills}")
        print(f"Google results per skill: {num_google}")
        print(f"YouTube results per skill: {num_youtube}")
        
        # Generate resources (parallel processing)
        skill_resources = service.generate_resources_for_skills(
            skills=skills,
            num_google_results=num_google,
            num_youtube_results=num_youtube,
            parallel=True
        )
        
        # Convert to JSON
        resources_json = [sr.to_dict() for sr in skill_resources]
        
        print(f"\n{'='*60}")
        print(f"LEARNING RESOURCES GENERATED")
        print(f"Total skills processed: {len(skill_resources)}")
        print(f"{'='*60}\n")
        
        return jsonify({
            "resources": resources_json,
            "total_skills": len(skills),
            "status": "success"
        })
        
    except Exception as e:
        print(f"Error generating learning resources: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


