# routes/cover_letter_routes.py
"""Cover Letter Generation Routes"""

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from services.cover_letter_service import CoverLetterService
import logging
import os

logger = logging.getLogger(__name__)

cover_letter_bp = Blueprint('cover_letter', __name__)


@cover_letter_bp.route('/cover-letter-templates', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def list_cover_letter_templates():
    """List available generic cover letter templates."""
    if request.method == "OPTIONS":
        return ("", 204)

    templates_dir = os.path.join("uploads", "cover-letter-templates")
    os.makedirs(templates_dir, exist_ok=True)

    template_names = sorted(
        [
            name
            for name in os.listdir(templates_dir)
            if os.path.isfile(os.path.join(templates_dir, name)) and name.lower().endswith(".txt")
        ]
    )

    FRIENDLY_NAMES = {
        "template1.txt": "Professional",
        "template2.txt": "Early Career",
        "template3.txt": "Portfolio-Led",
        "template4.txt": "No Nonsense",
        "template5.txt": "Straight to It"
    }

    templates = [
        {
            "name": name,
            "display_name": FRIENDLY_NAMES.get(name, name.replace("_", " ").replace(".txt", "").title()),
        }
        for name in template_names
    ]

    return jsonify({"success": True, "templates": templates}), 200

@cover_letter_bp.route('/generate-cover-letter', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def generate_cover_letter():
    """Generate a personalized cover letter.
    Expected JSON payload:
    {
        "user_id": "<user_id>",
        "job_id": "<job_id>",
        "template_name": "template1.txt"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        if not data:
            logger.error("Missing JSON payload")
            return jsonify({"error": "Missing JSON payload"}), 400
        
        user_id = data.get('user_id')
        job_id = data.get('job_id')
        template_name = data.get('template_name')
        
        logger.info(f"Generate cover letter request - user_id: {user_id}, job_id: {job_id}, template: {template_name}")
        
        if not user_id or not job_id or not template_name:
            error_msg = "user_id, job_id and template_name are required"
            logger.error(error_msg)
            return jsonify({"error": error_msg}), 400
        
        service = CoverLetterService()
        cover_letter = service.generate_cover_letter(user_id, job_id, template_name)
        
        logger.info(f"Successfully generated cover letter for user {user_id}, job {job_id}")
        return jsonify({"cover_letter": cover_letter})
        
    except FileNotFoundError as e:
        error_msg = str(e)
        logger.error(f"Template not found: {error_msg}")
        return jsonify({"error": error_msg}), 404
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error generating cover letter: {error_msg}", exc_info=True)
        return jsonify({"error": error_msg}), 500
