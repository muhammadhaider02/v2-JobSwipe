"""
Query builder for constructing optimized search queries.
Generates context-aware queries for Google and YouTube.
"""
from typing import List, Dict
import re


class QueryBuilder:
    """Builds optimized search queries for different platforms"""
    
    # Domain context keywords to add for ambiguous skills
    TECH_DOMAIN_KEYWORDS = [
        "programming",
        "software development",
        "data science",
        "computer science",
        "web development",
    ]
    
    # Skills that are ambiguous and need domain context
    AMBIGUOUS_SKILLS = {
        "statistics": "data science statistics",
        "communication": "technical communication",
        "analysis": "data analysis",
        "design": "software design",
        "testing": "software testing",
        "management": "project management software",
        "documentation": "technical documentation",
        "presentation": "technical presentation",
        "writing": "technical writing",
        "research": "technical research",
        "planning": "project planning",
        "leadership": "technical leadership",
        "strategy": "technical strategy",
    }
    
    # Multiple query templates for Google search
    GOOGLE_QUERY_TEMPLATES = [
        "best {skill} tutorials for programmers",
        "learn {skill} for software developers",
        "{skill} full course programming",
        "{skill} roadmap developer",
        "{skill} concepts for developers",
        "master {skill} guide tech",
        "{skill} documentation programming"
    ]
    
    YOUTUBE_LEARNING_KEYWORDS = [
        "tutorial",
        "course",
        "playlist",
        "complete guide",
        "full course",
        "crash course",
    ]
    
    @staticmethod
    def normalize_skill(skill: str) -> str:
        """Normalize skill name for querying"""
        # Remove special characters, keep alphanumeric and spaces
        normalized = re.sub(r'[^\w\s-]', '', skill)
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip().lower()
    
    @classmethod
    def add_domain_context(cls, skill: str) -> str:
        """
        Add domain context to ambiguous skills to ensure tech/computing relevance.
        
        Args:
            skill: Original skill name
            
        Returns:
            Skill with domain context if needed
        """
        normalized = cls.normalize_skill(skill)
        
        # Check if skill is in ambiguous list
        for ambiguous_term, contextualized_term in cls.AMBIGUOUS_SKILLS.items():
            if ambiguous_term in normalized and normalized == ambiguous_term:
                return contextualized_term
        
        # Check if skill already contains tech context
        tech_indicators = [
            "programming", "software", "web", "data", "computer",
            "api", "database", "cloud", "machine learning", "ai",
            "frontend", "backend", "fullstack", "devops", "mobile"
        ]
        
        has_tech_context = any(indicator in normalized for indicator in tech_indicators)
        
        # If no tech context detected and skill is short/generic, add context
        if not has_tech_context and len(normalized.split()) <= 2:
            # Add "programming" or "software development" context
            return f"{normalized} programming"
        
        return skill
    
    @classmethod
    def build_google_queries(cls, skill: str, num_variants: int = 5) -> List[str]:
        """
        Build multiple Google search query variants for comprehensive results.
        
        Args:
            skill: Skill name to search for
            num_variants: Number of query variants to generate
            
        Returns:
            List of search query strings
        """
        # Add domain context to ambiguous skills
        contextualized_skill = cls.add_domain_context(skill)
        normalized = cls.normalize_skill(contextualized_skill)
        
        # Generate queries from templates
        queries = []
        for template in cls.GOOGLE_QUERY_TEMPLATES[:num_variants]:
            query = template.format(skill=normalized)
            queries.append(query)
        
        return queries
    
    @staticmethod
    def build_youtube_queries(skill: str, num_variants: int = 2) -> List[str]:
        """
        Build YouTube search query variants.
        
        Args:
            skill: Skill name to search for
            num_variants: Number of query variants
            
        Returns:
            List of search query strings
        """
        # Add domain context
        contextualized_skill = QueryBuilder.add_domain_context(skill)
        normalized = QueryBuilder.normalize_skill(contextualized_skill)
        
        queries = [
            f"{normalized} tutorial programming",
            f"{normalized} full course developers",
            f"learn {normalized} complete programming",
            f"{normalized} crash course coding",
        ]
        
        return queries[:num_variants]
    
    @staticmethod
    def extract_keywords(skill: str) -> List[str]:
        """
        Extract key terms from skill for matching.
        
        Args:
            skill: Skill name
            
        Returns:
            List of keywords
        """
        normalized = QueryBuilder.normalize_skill(skill)
        # Split on common separators
        keywords = re.split(r'[\s\-_]+', normalized)
        # Filter out common stop words
        stop_words = {'and', 'or', 'the', 'a', 'an', 'for', 'to', 'of', 'in'}
        keywords = [k for k in keywords if k and k not in stop_words]
        return keywords
