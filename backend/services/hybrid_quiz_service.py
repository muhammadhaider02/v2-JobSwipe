"""
Hybrid Quiz Service - Enhanced 3-Tier Approach with Taxonomy Integration
Tier 1: Taxonomy-Based Database Lookup (exact/fuzzy match via taxonomy)
Tier 2: Fuzzy Database Matching (legacy fallback)
Tier 3: Dynamic Enrichment (Google CSE with subskill-enriched queries)
"""
import sqlite3
import random
import uuid
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
from models.learning_resources import Quiz, QuizQuestion
from services.taxonomy_service import TaxonomyService
from services.dynamic_enrichment_service import DynamicEnrichmentService


class HybridQuizService:
    """Hybrid quiz service with taxonomy-driven skill resolution"""
    
    # Path to the quiz database
    QUIZ_DB_PATH = 'quiz.db'
    
    def __init__(self):
        """Initialize hybrid quiz service with taxonomy"""
        self.taxonomy_service = TaxonomyService()
        self.dynamic_service = DynamicEnrichmentService()
        self._cache_available_tables()
    
    def _cache_available_tables(self):
        """Cache list of available tables in quiz.db"""
        try:
            conn = sqlite3.connect(self.QUIZ_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            self.available_tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            print(f"Cached {len(self.available_tables)} tables from quiz.db")
        except Exception as e:
            print(f"Warning: Could not cache quiz.db tables: {e}")
            self.available_tables = []
    
    def generate_quiz(self, skill: str, num_questions: int = 10) -> Quiz:
        """
        Generate quiz using enhanced 3-tier hybrid approach with taxonomy.
        
        TIER 1: Taxonomy → Database (taxonomy-based normalization + DB lookup)
        TIER 2: Fuzzy Database Matching (legacy fallback for unmapped skills)
        TIER 3: Dynamic Enrichment (Google CSE with taxonomy subskills)
        
        Args:
            skill: The skill to generate quiz for
            num_questions: Number of MCQ questions to generate (default: 5)
            
        Returns:
            Quiz object with questions
        """
        print(f"\n{'='*60}")
        print(f"HYBRID QUIZ GENERATION (TAXONOMY-ENHANCED) FOR: {skill}")
        print(f"{'='*60}")
        
        # TIER 1: Use taxonomy to resolve skill → DB table
        print(f"\nTIER 1: Taxonomy-based resolution")
        db_table, canonical_skill, match_type = self.taxonomy_service.resolve_to_db_table(skill)
        
        if db_table and match_type in ["exact", "fuzzy"]:
            print(f"Taxonomy {match_type} match: '{skill}' → '{canonical_skill}' → '{db_table}'")
            
            # Try to fetch from database
            db_questions = self._get_questions_from_table(db_table, num_questions)
            
            if db_questions and len(db_questions) >= num_questions:
                print(f"TIER 1 SUCCESS: Retrieved {len(db_questions)} questions from database")
                
                quiz_questions = self._convert_db_to_quiz_questions(db_questions)
                
                return Quiz(
                    id=str(uuid.uuid4()),
                    skill=skill,
                    questions=quiz_questions,
                    total_points=len(quiz_questions) * 10,
                    source="database_taxonomy",
                    matched_skill=canonical_skill
                )
            else:
                print(f"Table '{db_table}' has insufficient questions")
        else:
            print(f"No taxonomy match found")
        
        # TIER 2: Try legacy fuzzy matching (direct table matching)
        print(f"\nTIER 2: Legacy fuzzy database matching")
        db_questions, matched_table = self._get_questions_from_db_legacy(skill, num_questions)
        
        if db_questions and len(db_questions) >= num_questions:
            print(f"TIER 2 SUCCESS: Retrieved {len(db_questions)} questions from '{matched_table}'")
            
            quiz_questions = self._convert_db_to_quiz_questions(db_questions)
            
            return Quiz(
                id=str(uuid.uuid4()),
                skill=skill,
                questions=quiz_questions,
                total_points=len(quiz_questions) * 10,
                source="database_legacy",
                matched_skill=matched_table
            )
        
        # TIER 3: Dynamic enrichment with taxonomy subskills
        print(f"\nTIER 3: Dynamic enrichment with Google CSE")
        
        # Use canonical skill if available for enrichment
        quiz = self.dynamic_service.generate_enriched_quiz(
            skill=skill,
            canonical_skill=canonical_skill,
            num_questions=num_questions
        )
        
        print(f"TIER 3 SUCCESS: Generated {len(quiz.questions)} enriched questions")
        
        return quiz
    
    def _get_questions_from_table(self, table_name: str, num_questions: int) -> List[Dict]:
        """
        Get questions directly from a specific database table.
        
        Args:
            table_name: Name of the table to query
            num_questions: Number of questions to fetch
            
        Returns:
            List of question dicts
        """
        try:
            conn = sqlite3.connect(self.QUIZ_DB_PATH)
            cursor = conn.cursor()
            
            # Verify table exists and has questions
            cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
            count = cursor.fetchone()[0]
            
            if count == 0:
                conn.close()
                return []
            
            # Fetch random questions
            cursor.execute(f"""
                SELECT question, option_a, option_b, option_c, option_d, answer 
                FROM '{table_name}' 
                ORDER BY RANDOM() 
                LIMIT {num_questions}
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to list of dicts
            questions = []
            for row in rows:
                questions.append({
                    'question': row[0],
                    'option_a': row[1],
                    'option_b': row[2],
                    'option_c': row[3],
                    'option_d': row[4],
                    'answer': row[5]
                })
            
            return questions
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []
    
    def _get_questions_from_db_legacy(self, skill: str, num_questions: int) -> Tuple[List[Dict], Optional[str]]:
        """
        LEGACY: Get questions from quiz.db using direct fuzzy matching.
        This is kept as Tier 2 fallback for skills not in taxonomy.
        
        Returns:
            Tuple of (questions_list, matched_table_name)
        """
        try:
            conn = sqlite3.connect(self.QUIZ_DB_PATH)
            cursor = conn.cursor()
            
            # Try exact match
            table_name = self._find_exact_match(skill)
            
            # Try fuzzy matching
            if not table_name:
                table_name, similarity = self._find_fuzzy_match(skill)
                if similarity < 0.6:
                    print(f"Fuzzy match similarity too low: {similarity:.2f}")
                    conn.close()
                    return [], None
                else:
                    print(f"Legacy fuzzy match: '{skill}' → '{table_name}' (similarity: {similarity:.2f})")
            
            if not table_name:
                conn.close()
                return [], None
            
            # Verify table exists and has questions
            cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
            count = cursor.fetchone()[0]
            
            if count == 0:
                conn.close()
                return [], None
            
            # Fetch random questions
            cursor.execute(f"""
                SELECT question, option_a, option_b, option_c, option_d, answer 
                FROM '{table_name}' 
                ORDER BY RANDOM() 
                LIMIT {num_questions}
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to list of dicts
            questions = []
            for row in rows:
                questions.append({
                    'question': row[0],
                    'option_a': row[1],
                    'option_b': row[2],
                    'option_c': row[3],
                    'option_d': row[4],
                    'answer': row[5]
                })
            
            return questions, table_name
            
        except sqlite3.Error as e:
            print(f"  ✗ Database error: {e}")
            return [], None
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            return [], None
    
    def _find_exact_match(self, skill: str) -> Optional[str]:
        """Find exact table name match (case-insensitive)"""
        skill_lower = skill.lower().strip()
        
        for table in self.available_tables:
            if table.lower() == skill_lower:
                return table
            # Handle underscore vs space variations
            if table.lower().replace('_', ' ') == skill_lower:
                return table
        
        return None
    
    def _find_fuzzy_match(self, skill: str) -> Tuple[Optional[str], float]:
        """
        Find best fuzzy match using similarity scoring.
        
        Returns:
            Tuple of (table_name, similarity_score)
        """
        skill_lower = skill.lower().strip()
        best_match = None
        best_similarity = 0.0
        
        for table in self.available_tables:
            table_lower = table.lower().replace('_', ' ')
            
            # Calculate similarity using SequenceMatcher
            similarity = SequenceMatcher(None, skill_lower, table_lower).ratio()
            
            # Check if skill is contained in table name or vice versa
            if skill_lower in table_lower or table_lower in skill_lower:
                similarity = max(similarity, 0.7)  # Boost for substring matches
            
            # Check word overlap
            skill_words = set(skill_lower.split())
            table_words = set(table_lower.split())
            if skill_words and table_words:
                word_overlap = len(skill_words & table_words) / len(skill_words | table_words)
                similarity = max(similarity, word_overlap)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = table
        
        return best_match, best_similarity
    
    def _convert_db_to_quiz_questions(self, db_questions: List[Dict]) -> List[QuizQuestion]:
        """Convert database questions to QuizQuestion objects"""
        quiz_questions = []
        
        for db_q in db_questions:
            # Map answer letter to index
            answer_map = {'a': '0', 'b': '1', 'c': '2', 'd': '3'}
            correct_answer = answer_map.get(db_q['answer'].lower(), '0')
            
            question = QuizQuestion(
                id=str(uuid.uuid4()),
                question_type="mcq",
                question=db_q['question'],
                options=[
                    db_q['option_a'],
                    db_q['option_b'],
                    db_q['option_c'],
                    db_q['option_d']
                ],
                correct_answer=correct_answer,
                explanation="Answer from curated question database.",
                difficulty="medium"
            )
            quiz_questions.append(question)
        
        return quiz_questions
    
    def get_available_skills(self) -> List[Dict[str, Any]]:
        """Get list of all available skills (from both taxonomy and database)"""
        skills = []
        
        # Add skills from taxonomy
        taxonomy_skills = self.taxonomy_service.get_all_skills()
        for skill in taxonomy_skills:
            skills.append({
                'name': skill['name'],
                'key': skill['key'],
                'display_name': skill['name'],
                'subskills': skill['subskills'],
                'source': 'taxonomy',
                'db_table': skill['db_table']
            })
        
        # Add any database tables not in taxonomy
        for table in self.available_tables:
            # Check if already in taxonomy
            in_taxonomy = any(s['db_table'] == table for s in taxonomy_skills)
            if not in_taxonomy:
                try:
                    conn = sqlite3.connect(self.QUIZ_DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT COUNT(*) FROM '{table}'")
                    count = cursor.fetchone()[0]
                    conn.close()
                    
                    skills.append({
                        'name': table,
                        'display_name': table.replace('_', ' '),
                        'question_count': count,
                        'source': 'database_only'
                    })
                except:
                    continue
        
        return sorted(skills, key=lambda x: x.get('display_name', x.get('name', '')))
    
    def evaluate_quiz_submission(self, quiz_data: Dict[str, Any], user_answers: Dict[str, str]) -> Dict[str, Any]:
        """
        Evaluate quiz submission.
        
        Args:
            quiz_data: Quiz data with questions
            user_answers: Dict of question_id -> user_answer
            
        Returns:
            Evaluation results
        """
        questions = quiz_data.get('questions', [])
        total_points = len(questions) * 10
        earned_points = 0
        
        question_results = []
        
        for question in questions:
            question_id = question.get('id')
            correct_answer = question.get('correct_answer')
            user_answer = user_answers.get(question_id, '')
            
            is_correct = str(user_answer) == str(correct_answer)
            points = 10 if is_correct else 0
            earned_points += points
            
            question_results.append({
                'question_id': question_id,
                'question': question.get('question'),
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct,
                'points': points,
                'explanation': question.get('explanation', '')
            })
        
        score_percentage = (earned_points / total_points * 100) if total_points > 0 else 0
        passed = score_percentage >= 70  # 70% passing threshold
        
        # Generate feedback
        if score_percentage >= 90:
            feedback = "Excellent! You have a strong understanding of this skill."
        elif score_percentage >= 70:
            feedback = "Good job! You passed, but there's room for improvement."
        elif score_percentage >= 50:
            feedback = "You're getting there. Review the topics you missed and try again."
        else:
            feedback = "Keep practicing! Review the learning resources and retake the quiz."
        
        return {
            'total_points': total_points,
            'earned_points': earned_points,
            'score_percentage': round(score_percentage, 2),
            'passed': passed,
            'feedback': feedback,
            'question_results': question_results
        }
