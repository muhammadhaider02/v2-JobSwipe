# routes/cover_letter_routes.py
"""Cover Letter Generation Routes"""

from flask import Blueprint, request, jsonify
from services.cover_letter_service import CoverLetterService

cover_letter_bp = Blueprint('cover_letter', __name__)

@cover_letter_bp.route('/generate-cover-letter', methods=['POST'])
def generate_cover_letter():
    """Generate a personalized cover letter.
    Expected JSON payload:
    {
        "user_id": "<user_id>",
        "job_id": "<job_id>",
        "template_name": "template1.txt"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400
    user_id = data.get('user_id')
    job_id = data.get('job_id')
    template_name = data.get('template_name')
    if not user_id or not job_id or not template_name:
        return jsonify({"error": "user_id, job_id and template_name are required"}), 400
    try:
        service = CoverLetterService()
        cover_letter = service.generate_cover_letter(user_id, job_id, template_name)
        return jsonify({"cover_letter": cover_letter})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
