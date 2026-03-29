"""
Query builder utility for constructing search queries from skill names.
"""
import re
from typing import List


class QueryBuilder:
    """Utility class for building search queries and extracting keywords."""

    # Common stop words to filter out
    STOP_WORDS = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'shall', 'can',
        'not', 'no', 'nor', 'so', 'yet', 'both', 'either', 'neither',
    }

    @classmethod
    def extract_keywords(cls, skill: str) -> List[str]:
        """
        Extract meaningful keywords from a skill name.

        Args:
            skill: Skill name (e.g. "Machine Learning", "Node.js", "CI/CD")

        Returns:
            List of keywords
        """
        if not skill:
            return []

        # Split on whitespace, slashes, hyphens, dots (but keep acronyms intact)
        tokens = re.split(r'[\s/\-]+', skill)

        keywords = []
        for token in tokens:
            token = token.strip().lower()
            # Keep tokens that are meaningful (len > 1 and not a stop word)
            if len(token) > 1 and token not in cls.STOP_WORDS:
                keywords.append(token)

        # Always include the full skill name as a keyword if multi-word
        if ' ' in skill and skill.lower() not in keywords:
            keywords.insert(0, skill.lower())

        return keywords

    @classmethod
    def build_google_query(cls, skill: str, level: str = None) -> str:
        """Build a single Google search query for a skill."""
        base = f"{skill} tutorial"
        if level and level != "intermediate":
            base = f"{skill} {level} tutorial"
        return base

    @classmethod
    def build_google_queries(cls, skill: str, num_variants: int = 5, level: str = None) -> list:
        """
        Build multiple Google search query variants for a skill.

        Args:
            skill: Skill name
            num_variants: Number of query variants to generate
            level: Optional learning level

        Returns:
            List of query strings
        """
        queries = [
            f"{skill} tutorial",
            f"learn {skill}",
            f"{skill} for beginners",
            f"{skill} guide documentation",
            f"how to use {skill}",
            f"{skill} crash course",
            f"{skill} examples",
        ]
        if level and level != "intermediate":
            queries.insert(0, f"{skill} {level} tutorial")

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique.append(q)

        return unique[:num_variants]

    @classmethod
    def build_youtube_query(cls, skill: str, level: str = None) -> str:
        """Build a single YouTube search query for a skill."""
        base = f"{skill} course"
        if level == "beginner":
            base = f"{skill} beginner course"
        elif level == "advanced":
            base = f"{skill} advanced tutorial"
        return base

    @classmethod
    def build_youtube_queries(cls, skill: str, num_variants: int = 2, level: str = None) -> list:
        """
        Build multiple YouTube search query variants for a skill.

        Args:
            skill: Skill name
            num_variants: Number of query variants to generate
            level: Optional learning level

        Returns:
            List of query strings
        """
        queries = [
            f"{skill} course",
            f"{skill} tutorial playlist",
            f"learn {skill} full course",
            f"{skill} beginner tutorial",
        ]
        if level == "advanced":
            queries.insert(0, f"{skill} advanced tutorial")
        elif level == "beginner":
            queries.insert(0, f"{skill} beginner course")

        seen = set()
        unique = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique.append(q)

        return unique[:num_variants]
