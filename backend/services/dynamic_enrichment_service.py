"""
Dynamic Enrichment Service - Tier 3 fallback for quiz generation.
Generates quiz questions dynamically when no database match is found.
"""
import uuid
from typing import Optional
from models.learning_resources import Quiz, QuizQuestion


class DynamicEnrichmentService:
    """
    Tier 3 fallback: generates basic quiz questions for skills not in the database.
    """

    def generate_enriched_quiz(
        self,
        skill: str,
        canonical_skill: Optional[str] = None,
        num_questions: int = 5
    ) -> Quiz:
        """
        Generate a quiz dynamically for skills not found in the database.

        Args:
            skill: The skill name requested
            canonical_skill: Optional canonical/normalized name
            num_questions: Number of questions to generate

        Returns:
            Quiz object with generated questions
        """
        display_skill = canonical_skill or skill

        # Generate generic conceptual questions for the skill
        raw_questions = self._generate_generic_questions(display_skill, num_questions)

        quiz_questions = []
        for q in raw_questions:
            quiz_questions.append(QuizQuestion(
                id=str(uuid.uuid4()),
                question_type="mcq",
                question=q["question"],
                options=q["options"],
                correct_answer=q["correct_answer"],
                explanation=q.get("explanation", ""),
                difficulty="medium"
            ))

        return Quiz(
            id=str(uuid.uuid4()),
            skill=skill,
            questions=quiz_questions,
            total_points=len(quiz_questions) * 10,
            source="dynamic",
            matched_skill=canonical_skill
        )

    def _generate_generic_questions(self, skill: str, count: int) -> list:
        """Generate generic questions for any skill."""
        templates = [
            {
                "question": f"Which of the following best describes {skill}?",
                "options": [
                    f"A methodology for managing {skill} projects",
                    f"A core concept or tool used in {skill}",
                    f"A type of database related to {skill}",
                    f"A programming language for {skill}"
                ],
                "correct_answer": "1",
                "explanation": f"{skill} is a core concept/tool in its domain."
            },
            {
                "question": f"What is a primary use case of {skill}?",
                "options": [
                    "Network security monitoring",
                    f"Solving problems and building solutions related to {skill}",
                    "Database administration",
                    "Operating system management"
                ],
                "correct_answer": "1",
                "explanation": f"The primary use case of {skill} is to solve domain-specific problems."
            },
            {
                "question": f"Which statement about {skill} is most accurate?",
                "options": [
                    f"{skill} is only used in enterprise environments",
                    f"{skill} has no practical applications",
                    f"{skill} is widely used across various industries",
                    f"{skill} was discontinued in 2020"
                ],
                "correct_answer": "2",
                "explanation": f"{skill} is widely adopted across many industries and use cases."
            },
            {
                "question": f"When learning {skill}, which approach is recommended?",
                "options": [
                    "Skip fundamentals and start with advanced topics",
                    "Learn theory only without any practice",
                    "Build projects and practice alongside theory",
                    "Memorize all documentation before starting"
                ],
                "correct_answer": "2",
                "explanation": "Hands-on practice alongside theory is the most effective learning approach."
            },
            {
                "question": f"Which resource type is generally best for mastering {skill}?",
                "options": [
                    "Only reading books",
                    "Video tutorials combined with hands-on projects",
                    "Memorizing terminology",
                    "Watching others code without practicing"
                ],
                "correct_answer": "1",
                "explanation": "A combination of video learning and practical application accelerates mastery."
            },
            {
                "question": f"What distinguishes an expert in {skill} from a beginner?",
                "options": [
                    "Experts only know theoretical concepts",
                    "Experts have memorized all the documentation",
                    "Experts can apply concepts to solve real-world problems",
                    "Experts do not need to keep learning"
                ],
                "correct_answer": "2",
                "explanation": "Practical problem-solving ability is the hallmark of expertise."
            },
            {
                "question": f"How does {skill} typically relate to software development?",
                "options": [
                    "It has no connection to software development",
                    "It replaces the need for software development",
                    "It is a tool or concept used within the development ecosystem",
                    "It is only used for testing purposes"
                ],
                "correct_answer": "2",
                "explanation": f"{skill} is commonly integrated within the broader software development ecosystem."
            },
        ]

        # Return as many as requested (cycle if needed)
        result = []
        for i in range(min(count, len(templates))):
            result.append(templates[i])

        return result
