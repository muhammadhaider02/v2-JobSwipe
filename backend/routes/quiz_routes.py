"""
API routes for quiz generation and evaluation.
Provides endpoints for generating skill quizzes and evaluating submissions.
"""
import os
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from services.hybrid_quiz_service import HybridQuizService
from services.supabase_service import SupabaseService
from typing import Dict, Any
from datetime import datetime
import uuid
from src.logging_config import get_logger, redact_uid

logger = get_logger(__name__)

CORS_ORIGIN = os.environ.get("CORS_ALLOWED_ORIGIN", "http://localhost:3000")

quiz_bp = Blueprint('quiz', __name__)
hybrid_service = HybridQuizService()
supabase_service = SupabaseService()

# In-memory storage for active quizzes
active_quizzes: Dict[str, Any] = {}


@quiz_bp.route('/skill-quiz/<skill>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def generate_skill_quiz(skill: str):
    """
    Generate a quiz for a specific skill using 3-tier hybrid approach.
    
    URL: /skill-quiz/{skill}
    Query params:
    - num_questions: int (default 5, max 10)
    
    Response:
    {
        "quiz": {
            "id": "uuid",
            "skill": "python",
            "questions": [...],
            "total_points": 50,
            "source": "database" | "dynamic",
            "matched_skill": "Backend Developer"  // if fuzzy matched
        },
        "status": "success"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        num_questions = int(request.args.get('num_questions', 5))
        num_questions = min(max(num_questions, 1), 10)

        exclude_param = request.args.get('exclude', '')
        exclude_hashes = [h.strip() for h in exclude_param.split(',') if h.strip() and len(h.strip()) == 8]
        exclude_hashes = exclude_hashes[:200]

        logger.info("Quiz generation requested for skill=%s, num_questions=%s, exclude=%d", skill, num_questions, len(exclude_hashes))

        quiz = hybrid_service.generate_quiz(skill, num_questions=num_questions, exclude_hashes=exclude_hashes or None)
        
        # Store quiz in memory for later evaluation
        active_quizzes[quiz.id] = quiz.to_dict()
        
        logger.info(
            "Quiz generated: id=%s, source=%s, questions=%d, points=%d, matched_skill=%s",
            quiz.id, quiz.source, len(quiz.questions), quiz.total_points, quiz.matched_skill,
        )
        
        return jsonify({
            "quiz": quiz.to_dict(),
            "status": "success"
        })
        
    except Exception as e:
        logger.error("Error generating quiz for skill '%s': %s", skill, e, exc_info=True)
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@quiz_bp.route('/quiz-submit', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins=CORS_ORIGIN,
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def submit_quiz():
    """
    Submit quiz answers for evaluation.
    
    Request body:
    {
        "quiz_id": "uuid",
        "answers": {
            "question_id_1": "0",  // MCQ answer (option index)
            "question_id_2": "user's short answer",
            "question_id_3": "user's code"
        }
    }
    
    Response:
    {
        "submission_id": "uuid",
        "earned_points": 35,
        "total_points": 50,
        "score_percentage": 70.0,
        "passed": true,
        "feedback": {
            "question_id_1": {
                "correct": true,
                "user_answer": "0",
                "correct_answer": "0",
                "explanation": "...",
                "points_earned": 10,
                "points_possible": 10
            },
            ...
        },
        "status": "success"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        
        if not data or "quiz_id" not in data or "answers" not in data:
            return jsonify({
                "error": "Missing 'quiz_id' or 'answers' in request body",
                "status": "error"
            }), 400
        
        quiz_id = data.get("quiz_id")
        user_answers = data.get("answers", {})
        
        # Retrieve quiz from memory
        if quiz_id not in active_quizzes:
            return jsonify({
                "error": "Quiz not found. It may have expired.",
                "status": "error"
            }), 404
        
        quiz_data = active_quizzes[quiz_id]
        
        logger.info("Quiz submission: quiz_id=%s, skill=%s, answers=%d", quiz_id, quiz_data['skill'], len(user_answers))
        
        # Evaluate submission
        evaluation = hybrid_service.evaluate_quiz_submission(quiz_data, user_answers)
        
        # Create submission record
        submission_id = str(uuid.uuid4())
        submission = {
            "submission_id": submission_id,
            "quiz_id": quiz_id,
            "skill": quiz_data['skill'],
            **evaluation
        }
        
        # Save quiz score to Supabase if user_id is provided
        user_id = data.get("user_id")
        if user_id:
            try:
                quiz_score_data = {
                    "user_id": user_id,
                    "skill": quiz_data['skill'],
                    "score_percentage": float(evaluation['score_percentage']),
                    "quiz_id": quiz_id,
                    "passed": evaluation['passed'],
                    "timestamp": datetime.utcnow().isoformat(),
                    "question_hashes": [q.get('question_hash') for q in quiz_data.get('questions', []) if q.get('question_hash')],
                }
                
                supabase_service.client.table('user_quiz_scores').insert(
                    quiz_score_data
                ).execute()
                
                logger.info("Saved quiz score to Supabase for user %s", redact_uid(user_id))
            except Exception as e:
                # Log error but don't fail the request
                logger.error("Failed to save quiz score to Supabase: %s", e)
        
        logger.info(
            "Quiz evaluated: score=%s/%s (%.1f%%), passed=%s",
            evaluation['earned_points'], evaluation['total_points'],
            evaluation['score_percentage'], evaluation['passed'],
        )
        
        return jsonify({
            **submission,
            "status": "success"
        })
        
    except Exception as e:
        logger.error("Error submitting quiz: %s", e, exc_info=True)
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


