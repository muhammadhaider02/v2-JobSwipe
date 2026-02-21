"""
API routes for skill-specific learning resources and quizzes.
"""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from services.google_search_service import GoogleSearchService
from services.database_service import DatabaseService
from services.hybrid_quiz_service import HybridQuizService
from models.learning_resources import QuizSubmission
import uuid
from datetime import datetime

skill_resources_bp = Blueprint('skill_resources', __name__)
google_service = GoogleSearchService()
db_service = DatabaseService()
quiz_service = HybridQuizService()


@skill_resources_bp.route('/skill-resources/<skill>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_skill_resources(skill: str):
    """
    Fetch and store top 5-8 learning resources for a skill.
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        print(f"\n{'='*60}")
        print(f"FETCHING LEARNING RESOURCES FOR: {skill}")
        print(f"{'='*60}")
        
        # Check if we already have resources in DB (cached)
        existing_resources = db_service.get_learning_resources(skill)
        if existing_resources and len(existing_resources) >= 5:
            print(f"✓ Found {len(existing_resources)} cached resources")
            return jsonify({
                "skill": skill,
                "resources": existing_resources,
                "status": "success",
                "cached": True
            })
        
        # Fetch fresh resources from Google CSE
        queries = [
            f"best {skill} tutorial programming",
            f"learn {skill} complete guide",
            f"{skill} documentation"
        ]
        
        all_results = []
        seen_urls = set()
        
        for query in queries:
            results = google_service.search(query, num_results=10)
            
            for result in results:
                extracted = google_service.extract_result_data(result)
                url = extracted.get('url', '')
                
                # Skip duplicates
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Extract domain as source
                domain = extracted.get('domain', '')
                source = domain.split('.')[0] if domain else 'unknown'
                
                all_results.append({
                    'title': extracted.get('title', ''),
                    'url': url,
                    'snippet': extracted.get('snippet', ''),
                    'source': source
                })
                
                # Stop when we have enough
                if len(all_results) >= 8:
                    break
            
            if len(all_results) >= 8:
                break
        
        # Take top 5-8 results
        top_resources = all_results[:8]
        
        # Save to database
        resource_ids = db_service.save_learning_resources(skill, top_resources)
        
        # Get the saved resources back with IDs
        saved_resources = db_service.get_learning_resources(skill)
        
        print(f"✓ Saved {len(saved_resources)} resources to database")
        
        return jsonify({
            "skill": skill,
            "resources": saved_resources,
            "status": "success",
            "cached": False
        })
        
    except Exception as e:
        print(f"Error fetching skill resources: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@skill_resources_bp.route('/skill-quiz/<skill>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_skill_quiz(skill: str):
    """
    Get or generate a quiz for a skill using taxonomy-enhanced system.
    Cache disabled for testing - always generates fresh quiz.
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        print(f"\n{'='*60}")
        print(f"FETCHING QUIZ FOR: {skill}")
        print(f"{'='*60}")
        
        # CACHE DISABLED FOR TESTING - Always generate fresh quiz
        # This forces the system to use the new taxonomy + Google CSE approach
        
        # Generate new quiz using taxonomy-enhanced HybridQuizService
        quiz = quiz_service.generate_quiz(skill)
        
        # Save to database for submission tracking
        quiz_id = db_service.save_quiz(quiz)
        
        # Return quiz without correct answers
        quiz_dict = quiz.to_dict()
        questions_without_answers = []
        for q in quiz_dict['questions']:
            q_copy = q.copy()
            q_copy.pop('correct_answer', None)
            questions_without_answers.append(q_copy)
        quiz_dict['questions'] = questions_without_answers
        
        print(f"✓ Generated and saved quiz with ID: {quiz_id}")
        
        return jsonify({
            "quiz": quiz_dict,
            "status": "success",
            "cached": False,
            "source": quiz.source if hasattr(quiz, 'source') else "unknown"
        })
        
    except Exception as e:
        print(f"Error generating quiz: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@skill_resources_bp.route('/quiz-submit', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def submit_quiz():
    """
    Submit quiz answers for evaluation.
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "No data provided",
                "status": "error"
            }), 400
        
        quiz_id = data.get('quiz_id')
        user_answers = data.get('answers', {})
        
        if not quiz_id:
            return jsonify({
                "error": "quiz_id is required",
                "status": "error"
            }), 400
        
        print(f"\n{'='*60}")
        print(f"EVALUATING QUIZ SUBMISSION")
        print(f"Quiz ID: {quiz_id}")
        print(f"{'='*60}")
        
        # Get quiz from database
        quiz_data = db_service.get_quiz_by_id(quiz_id)
        
        if not quiz_data:
            return jsonify({
                "error": "Quiz not found",
                "status": "error"
            }), 404
        
        # Evaluate submission
        evaluation = quiz_service.evaluate_quiz_submission(quiz_data, user_answers)
        
        # Create submission record
        submission = QuizSubmission(
            id=str(uuid.uuid4()),
            quiz_id=quiz_id,
            user_answers=user_answers,
            score=evaluation['earned_points'],
            total_points=evaluation['total_points'],
            passed=evaluation['passed'],
            feedback=evaluation['feedback']
        )
        
        # Save submission
        submission_id = db_service.save_quiz_submission(submission)
        
        print(f"✓ Quiz evaluated")
        print(f"  Score: {evaluation['earned_points']}/{evaluation['total_points']}")
        print(f"  Percentage: {evaluation['score_percentage']}%")
        print(f"  Passed: {evaluation['passed']}")
        
        return jsonify({
            "submission_id": submission_id,
            "evaluation": evaluation,
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


@skill_resources_bp.route('/quiz-result/<submission_id>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_quiz_result(submission_id: str):
    """
    Get quiz submission results.
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        submission = db_service.get_submission_by_id(submission_id)
        
        if not submission:
            return jsonify({
                "error": "Submission not found",
                "status": "error"
            }), 404
        
        return jsonify({
            "submission": submission,
            "status": "success"
        })
        
    except Exception as e:
        print(f"Error fetching submission: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500
