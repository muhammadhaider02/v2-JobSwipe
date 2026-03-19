"""
API routes for quiz generation and evaluation.
Provides endpoints for generating skill quizzes and evaluating submissions.
"""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from services.hybrid_quiz_service import HybridQuizService
from services.supabase_service import SupabaseService
from typing import Dict, Any
from datetime import datetime
import uuid

quiz_bp = Blueprint('quiz', __name__)
hybrid_service = HybridQuizService()
supabase_service = SupabaseService(use_service_role=True)

# In-memory storage for active quizzes
active_quizzes: Dict[str, Any] = {}


@quiz_bp.route('/skill-quiz/<skill>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
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
        # Get number of questions
        num_questions = int(request.args.get('num_questions', 5))
        num_questions = min(max(num_questions, 1), 10)  # Clamp between 1-10
        
        print(f"\n{'='*60}")
        print(f"QUIZ GENERATION REQUEST")
        print(f"{'='*60}")
        print(f"Skill: {skill}")
        print(f"Number of questions: {num_questions}")
        
        # Generate quiz using hybrid service
        quiz = hybrid_service.generate_quiz(skill, num_questions=num_questions)
        
        # Store quiz in memory for later evaluation
        active_quizzes[quiz.id] = quiz.to_dict()
        
        print(f"\n✓ Quiz generated successfully")
        print(f"  Quiz ID: {quiz.id}")
        print(f"  Source: {quiz.source}")
        print(f"  Questions: {len(quiz.questions)}")
        print(f"  Total points: {quiz.total_points}")
        if quiz.matched_skill:
            print(f"  Matched skill: {quiz.matched_skill}")
        print(f"{'='*60}\n")
        
        return jsonify({
            "quiz": quiz.to_dict(),
            "status": "success"
        })
        
    except Exception as e:
        print(f"Error generating quiz for skill '{skill}': {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@quiz_bp.route('/quiz-submit', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
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
        
        print(f"\n{'='*60}")
        print(f"QUIZ SUBMISSION")
        print(f"{'='*60}")
        print(f"Quiz ID: {quiz_id}")
        print(f"Skill: {quiz_data['skill']}")
        print(f"Number of answers: {len(user_answers)}")
        
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
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                supabase_service.client.table('user_quiz_scores').insert(
                    quiz_score_data
                ).execute()
                
                print(f"  ✓ Saved quiz score to Supabase for user {user_id}")
            except Exception as e:
                # Log error but don't fail the request
                print(f"  ✗ Failed to save quiz score to Supabase: {e}")
        
        print(f"\n✓ Quiz evaluated successfully")
        print(f"  Score: {evaluation['earned_points']}/{evaluation['total_points']} ({evaluation['score_percentage']}%)")
        print(f"  Passed: {evaluation['passed']}")
        print(f"{'='*60}\n")
        
        return jsonify({
            **submission,
            "status": "success"
        })
        
    except Exception as e:
        print(f"Error submitting quiz: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@quiz_bp.route('/quiz-result/<submission_id>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_quiz_result(submission_id: str):
    """
    Get detailed results for a quiz submission.
    
    URL: /quiz-result/{submission_id}
    
    Response: Same as submit_quiz response
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        # In a real app, you'd retrieve this from a database
        # For now, return a not implemented message
        return jsonify({
            "error": "Quiz result retrieval not yet implemented. Results are returned immediately upon submission.",
            "status": "error"
        }), 501
        
    except Exception as e:
        print(f"Error retrieving quiz result: {e}")
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@quiz_bp.route('/available-skills', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_available_skills():
    """
    Get list of all skills available in the quiz database.
    
    Response:
    {
        "skills": [
            {
                "name": "Software Engineer",
                "display_name": "Software Engineer",
                "question_count": 50,
                "source": "database"
            },
            ...
        ],
        "total_skills": 20,
        "status": "success"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        skills = hybrid_service.get_available_skills()
        
        return jsonify({
            "skills": skills,
            "total_skills": len(skills),
            "status": "success"
        })
        
    except Exception as e:
        print(f"Error retrieving available skills: {e}")
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500
