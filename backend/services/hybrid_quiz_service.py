"""
Hybrid Quiz Service - Enhanced 3-Tier Approach with Taxonomy Integration
Tier 1: Taxonomy-Based Database Lookup (exact/fuzzy match via taxonomy)
Tier 2: Fuzzy Database Matching (legacy fallback)
Tier 3: Dynamic Enrichment (Google CSE with subskill-enriched queries)
"""
import hashlib
import sqlite3
import random
import uuid
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
from models.learning_resources import Quiz, QuizQuestion
from services.taxonomy_service import TaxonomyService
from services.dynamic_enrichment_service import DynamicEnrichmentService
from src.logging_config import get_logger

logger = get_logger(__name__)


class HybridQuizService:
    """Hybrid quiz service with taxonomy-driven skill resolution"""
    
    # Path to the quiz database
    QUIZ_DB_PATH = 'data/quiz.db'
    
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
            logger.info("Cached %d tables from quiz.db", len(self.available_tables))
        except Exception as e:
            logger.warning("Could not cache quiz.db tables: %s", e)
            self.available_tables = []
    
    @staticmethod
    def _question_hash(question_text: str) -> str:
        return hashlib.md5(question_text.strip().lower().encode()).hexdigest()[:8]

    def generate_quiz(self, skill: str, num_questions: int = 10, exclude_hashes: list[str] | None = None) -> Quiz:
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
        logger.info("Hybrid quiz generation (taxonomy-enhanced) for skill=%s", skill)

        # TIER 1: Use taxonomy to resolve skill -> DB table
        logger.debug("TIER 1: Taxonomy-based resolution")
        db_table, canonical_skill, match_type = self.taxonomy_service.resolve_to_db_table(skill)
        
        if db_table and match_type in ["exact", "fuzzy"]:
            logger.debug("Taxonomy %s match: '%s' -> '%s' -> '%s'", match_type, skill, canonical_skill, db_table)
            
            db_questions, pool_reset = self._get_questions_from_table(db_table, num_questions, exclude_hashes)

            if db_questions and len(db_questions) >= num_questions:
                logger.info("TIER 1 SUCCESS: retrieved %d questions from database", len(db_questions))

                quiz_questions = self._convert_db_to_quiz_questions(db_questions)

                return Quiz(
                    id=str(uuid.uuid4()),
                    skill=skill,
                    questions=quiz_questions,
                    total_points=len(quiz_questions) * 10,
                    source="database_taxonomy",
                    matched_skill=canonical_skill,
                    pool_reset=pool_reset,
                )
            else:
                logger.debug("Table '%s' has insufficient questions", db_table)
        else:
            logger.debug("No taxonomy match found")
        
        logger.debug("TIER 2: Legacy fuzzy database matching")
        db_questions, matched_table, pool_reset = self._get_questions_from_db_legacy(skill, num_questions, exclude_hashes)

        if db_questions and len(db_questions) >= num_questions:
            logger.info("TIER 2 SUCCESS: retrieved %d questions from '%s'", len(db_questions), matched_table)

            quiz_questions = self._convert_db_to_quiz_questions(db_questions)

            return Quiz(
                id=str(uuid.uuid4()),
                skill=skill,
                questions=quiz_questions,
                total_points=len(quiz_questions) * 10,
                source="database_legacy",
                matched_skill=matched_table,
                pool_reset=pool_reset,
            )
        
        # TIER 3: Dynamic enrichment with taxonomy subskills
        logger.debug("TIER 3: Dynamic enrichment with Google CSE")
        
        # Use canonical skill if available for enrichment
        quiz = self.dynamic_service.generate_enriched_quiz(
            skill=skill,
            canonical_skill=canonical_skill,
            num_questions=num_questions
        )
        
        logger.info("TIER 3 SUCCESS: generated %d enriched questions", len(quiz.questions))
        
        return quiz
    
    def _get_questions_from_table(
        self, table_name: str, num_questions: int, exclude_hashes: list[str] | None = None
    ) -> tuple[list[dict], bool]:
        """
        Get questions from a database table, excluding previously answered ones.

        Returns:
            Tuple of (questions_list, pool_reset_flag)
        """
        try:
            conn = sqlite3.connect(self.QUIZ_DB_PATH)
            cursor = conn.cursor()

            cursor.execute(f"SELECT question, option_a, option_b, option_c, option_d, answer FROM '{table_name}'")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return [], False

            exclude_set = set(exclude_hashes) if exclude_hashes else set()

            all_questions = []
            for row in rows:
                q = {
                    'question': row[0], 'option_a': row[1], 'option_b': row[2],
                    'option_c': row[3], 'option_d': row[4], 'answer': row[5],
                    'question_hash': self._question_hash(row[0]),
                }
                all_questions.append(q)

            fresh = [q for q in all_questions if q['question_hash'] not in exclude_set]

            pool_reset = False
            if len(fresh) >= num_questions:
                selected = random.sample(fresh, num_questions)
            elif fresh:
                seen = [q for q in all_questions if q['question_hash'] in exclude_set]
                pad = random.sample(seen, min(num_questions - len(fresh), len(seen)))
                selected = fresh + pad
            else:
                pool_reset = True
                logger.info("Question pool exhausted for table '%s', resetting", table_name)
                selected = random.sample(all_questions, min(num_questions, len(all_questions)))

            return selected, pool_reset

        except sqlite3.Error as e:
            logger.error("Database error: %s", e)
            return [], False
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            return [], False
    
    def _get_questions_from_db_legacy(
        self, skill: str, num_questions: int, exclude_hashes: list[str] | None = None
    ) -> tuple[list[dict], str | None, bool]:
        """
        LEGACY: Get questions from quiz.db using direct fuzzy matching.

        Returns:
            Tuple of (questions_list, matched_table_name, pool_reset_flag)
        """
        try:
            table_name = self._find_exact_match(skill)

            if not table_name:
                table_name, similarity = self._find_fuzzy_match(skill)
                if similarity < 0.6:
                    logger.debug("Fuzzy match similarity too low: %.2f", similarity)
                    return [], None, False
                else:
                    logger.debug("Legacy fuzzy match: '%s' -> '%s' (similarity: %.2f)", skill, table_name, similarity)

            if not table_name:
                return [], None, False

            questions, pool_reset = self._get_questions_from_table(table_name, num_questions, exclude_hashes)
            return questions, table_name, pool_reset

        except Exception as e:
            logger.error("Unexpected error: %s", e)
            return [], None, False
    
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
                difficulty="medium",
                question_hash=db_q.get('question_hash'),
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
