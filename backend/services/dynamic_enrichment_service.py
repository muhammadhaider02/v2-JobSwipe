"""
Dynamic Enrichment Service - Google CSE-powered micro-skill expansion
Generates enriched queries using taxonomy subskills for precise results
"""
import uuid
from typing import List, Dict, Any, Optional
from models.learning_resources import Quiz, QuizQuestion
from services.google_search_service import GoogleSearchService
from services.taxonomy_service import TaxonomyService
import re


class DynamicEnrichmentService:
    """Service for dynamic quiz generation using Google CSE with enriched queries"""
    
    def __init__(self):
        """Initialize dynamic enrichment service"""
        self.google_service = GoogleSearchService()
        self.taxonomy_service = TaxonomyService()
    
    def generate_enriched_quiz(
        self, 
        skill: str, 
        canonical_skill: Optional[str] = None,
        num_questions: int = 5
    ) -> Quiz:
        """
        Generate quiz using Google CSE with taxonomy-enriched queries.
        
        Args:
            skill: Original skill name
            canonical_skill: Canonical skill from taxonomy (if available)
            num_questions: Number of questions to generate
            
        Returns:
            Quiz object with dynamically generated questions
        """
        print(f"\n{'='*60}")
        print(f"DYNAMIC ENRICHMENT FOR: {skill}")
        if canonical_skill:
            print(f"Canonical: {canonical_skill}")
        print(f"{'='*60}")
        
        # Get subskills if we have canonical skill
        subskills = []
        if canonical_skill:
            subskills = self.taxonomy_service.get_subskills(canonical_skill)
            print(f"✓ Found {len(subskills)} subskills from taxonomy")
        
        # Build enriched queries
        queries = self._build_enriched_queries(skill, subskills)
        
        # Search Google for quiz content
        search_results = []
        for query in queries[:3]:  # Limit to 3 queries to minimize API calls
            results = self.google_service.search(query, num_results=5)
            search_results.extend(results)
            if len(search_results) >= 10:
                break
        
        print(f"✓ Collected {len(search_results)} search results")
        
        # Extract micro-skills from results
        micro_skills = self._extract_micro_skills(search_results, skill, subskills)
        print(f"✓ Extracted {len(micro_skills)} micro-skills")
        
        # Generate questions based on micro-skills and search context
        questions = self._generate_questions_from_context(
            skill, 
            canonical_skill,
            subskills, 
            micro_skills, 
            num_questions
        )
        
        quiz = Quiz(
            id=str(uuid.uuid4()),
            skill=skill,
            questions=questions,
            total_points=len(questions) * 10,
            source="dynamic_enriched",
            matched_skill=canonical_skill
        )
        
        print(f"✓ Generated {len(questions)} enriched questions")
        
        return quiz
    
    def _build_enriched_queries(self, skill: str, subskills: List[str]) -> List[str]:
        """
        Build enriched search queries using skill + subskills.
        
        Pattern: <skill> + <top 3 subskills> + "tutorial" OR "basics" OR "examples"
        
        Args:
            skill: Skill name
            subskills: List of subskills from taxonomy
            
        Returns:
            List of enriched query strings
        """
        queries = []
        
        if subskills and len(subskills) >= 3:
            # Use top 3 subskills for enriched query
            top_subskills = subskills[:3]
            
            # Query 1: Tutorial focus
            query1 = f'"{skill}" "{top_subskills[0]}" "{top_subskills[1]}" "{top_subskills[2]}" tutorial'
            queries.append(query1)
            
            # Query 2: Basics/fundamentals focus
            query2 = f'"{skill}" "{top_subskills[0]}" "{top_subskills[1]}" basics examples'
            queries.append(query2)
            
            # Query 3: Quiz/questions focus
            query3 = f'"{skill}" "{top_subskills[0]}" quiz questions MCQ'
            queries.append(query3)
            
            # Query 4: Interview prep focus
            top_subskills_alt = subskills[1:4] if len(subskills) > 3 else subskills[:3]
            query4 = f'"{skill}" "{top_subskills_alt[0]}" interview questions'
            queries.append(query4)
        else:
            # Fallback queries without subskills
            queries = [
                f'"{skill}" tutorial basics',
                f'"{skill}" quiz questions MCQ',
                f'"{skill}" interview questions',
                f'learn "{skill}" fundamentals'
            ]
        
        print(f"  📝 Built {len(queries)} enriched queries")
        for i, q in enumerate(queries[:2], 1):
            print(f"     Query {i}: {q}")
        
        return queries
    
    def _extract_micro_skills(
        self, 
        search_results: List[Dict], 
        skill: str, 
        subskills: List[str]
    ) -> List[str]:
        """
        Extract micro-skills from search result snippets.
        
        Args:
            search_results: Raw search results from Google
            skill: Main skill name
            subskills: Known subskills from taxonomy
            
        Returns:
            List of extracted micro-skills
        """
        micro_skills = set()
        
        # Add known subskills
        micro_skills.update(subskills[:5])  # Top 5 subskills
        
        # Extract from search snippets
        for result in search_results:
            snippet = result.get('snippet', '')
            title = result.get('title', '')
            
            # Look for patterns like "Learn X", "Understanding Y", "X basics"
            combined_text = f"{title} {snippet}".lower()
            
            # Pattern 1: "learn X", "understand X"
            learn_pattern = r'(?:learn|understanding?|master)\s+([a-z][a-z\s]{2,30})'
            matches = re.findall(learn_pattern, combined_text)
            for match in matches:
                cleaned = match.strip()
                if len(cleaned) > 2 and cleaned not in skill.lower():
                    micro_skills.add(cleaned.title())
            
            # Pattern 2: Technical terms (capitalized words)
            tech_terms = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', f"{title} {snippet}")
            for term in tech_terms:
                if len(term) > 3 and term.lower() not in skill.lower():
                    micro_skills.add(term)
        
        return list(micro_skills)[:10]  # Limit to top 10
    
    def _generate_questions_from_context(
        self,
        skill: str,
        canonical_skill: Optional[str],
        subskills: List[str],
        micro_skills: List[str],
        num_questions: int
    ) -> List[QuizQuestion]:
        """
        Generate quiz questions using skill context and micro-skills.
        
        Args:
            skill: Original skill name
            canonical_skill: Canonical skill name
            subskills: List of subskills
            micro_skills: Extracted micro-skills
            num_questions: Number of questions to generate
            
        Returns:
            List of QuizQuestion objects
        """
        questions = []
        display_skill = canonical_skill or skill
        
        # Combine subskills and micro-skills for variety
        all_topics = subskills[:] + micro_skills[:]
        
        # Question templates with dynamic topics
        templates = [
            {
                "template": f"What is the primary purpose of __TOPIC__ in {display_skill}?",
                "options_template": [
                    "To improve code organization",
                    "To enhance performance",
                    "To enable specific functionality",
                    "All of the above"
                ],
                "correct": "3",
                "explanation": f"__TOPIC__ serves multiple important purposes in {display_skill} development."
            },
            {
                "template": f"Which of the following best describes __TOPIC__ in {display_skill}?",
                "options_template": [
                    "A fundamental concept",
                    "An advanced technique",
                    "A design pattern",
                    "A best practice"
                ],
                "correct": "0",
                "explanation": f"__TOPIC__ is a fundamental concept that developers should understand when working with {display_skill}."
            },
            {
                "template": f"When working with __TOPIC__ in {display_skill}, what should you prioritize?",
                "options_template": [
                    "Performance optimization",
                    "Code readability",
                    "Proper implementation",
                    "All of the above"
                ],
                "correct": "3",
                "explanation": f"When working with __TOPIC__, developers should balance performance, readability, and proper implementation."
            },
            {
                "template": f"What is a common use case for __TOPIC__ in {display_skill}?",
                "options_template": [
                    "Data manipulation",
                    "State management",
                    "Business logic implementation",
                    "It depends on the requirements"
                ],
                "correct": "3",
                "explanation": f"__TOPIC__ can be applied in various scenarios depending on specific project requirements."
            },
            {
                "template": f"Which statement about __TOPIC__ in {display_skill} is most accurate?",
                "options_template": [
                    "It's essential for all projects",
                    "It's useful in specific scenarios",
                    "It improves development efficiency",
                    "Both B and C"
                ],
                "correct": "3",
                "explanation": f"__TOPIC__ is particularly useful in specific scenarios and can significantly improve development efficiency."
            },
            {
                "template": f"How does __TOPIC__ improve {display_skill} development?",
                "options_template": [
                    "By simplifying complex operations",
                    "By reducing code duplication",
                    "By improving maintainability",
                    "All of the above"
                ],
                "correct": "3",
                "explanation": f"__TOPIC__ provides multiple benefits including simplified operations, reduced duplication, and better maintainability."
            },
            {
                "template": f"What is the recommended approach for learning __TOPIC__ in {display_skill}?",
                "options_template": [
                    "Read documentation only",
                    "Practice with real examples",
                    "Watch video tutorials only",
                    "Memorize syntax"
                ],
                "correct": "1",
                "explanation": f"Hands-on practice with real examples is the most effective way to learn __TOPIC__."
            }
        ]
        
        # Generate questions by filling templates with topics
        topic_index = 0
        for i in range(num_questions):
            if topic_index >= len(all_topics):
                topic_index = 0  # Wrap around if we run out of topics
            
            topic = all_topics[topic_index] if all_topics else "core concepts"
            template = templates[i % len(templates)]
            
            question_text = template["template"].replace("__TOPIC__", topic)
            explanation = template["explanation"].replace("__TOPIC__", topic)
            
            question = QuizQuestion(
                id=str(uuid.uuid4()),
                question_type="mcq",
                question=question_text,
                options=template["options_template"],
                correct_answer=template["correct"],
                explanation=explanation,
                difficulty="medium"
            )
            questions.append(question)
            
            topic_index += 1
        
        return questions
