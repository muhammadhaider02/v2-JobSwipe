"""
Resource ranking and scoring system.
Uses weighted heuristics to score and rank learning resources.
"""
from typing import List, Dict, Any
import re
from utils.domain_trust import (
    get_domain_trust_score, 
    get_channel_trust_score, 
    is_blacklisted_domain,
    is_non_tech_domain,
    is_tech_relevant_domain
)
from utils.query_builder import QueryBuilder


class ResourceRanker:
    """Deterministic scoring and ranking for learning resources"""
    
    # Scoring weights for Google results
    GOOGLE_WEIGHTS = {
        "domain_trust": 0.35,
        "keyword_match": 0.30,
        "snippet_richness": 0.20,
        "title_quality": 0.15
    }
    
    # Scoring weights for YouTube results
    YOUTUBE_WEIGHTS = {
        "channel_trust": 0.35,
        "keyword_match": 0.25,
        "engagement": 0.20,
        "playlist_length": 0.20
    }
    
    # Minimum confidence threshold
    MIN_CONFIDENCE_THRESHOLD = 0.50
    
    @classmethod
    def score_google_result(cls, result: Dict[str, Any], skill: str) -> float:
        """
        Calculate confidence score for a Google search result.
        
        Args:
            result: Normalized Google result
            skill: Original skill name being searched
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        
        # Check if domain is blacklisted
        if is_blacklisted_domain(url):
            return 0.0
        
        # NEW: Check if domain is non-tech (medical, beauty, sports, etc.)
        if is_non_tech_domain(url):
            print(f"  ⚠️  Filtering non-tech domain: {url}")
            return 0.0
        
        # NEW: Check if content is tech-relevant
        if not is_tech_relevant_domain(url, title, snippet):
            print(f"  ⚠️  Filtering non-tech content: {title[:50]}...")
            return 0.0
        
        # 1. Domain trust score
        domain_score = get_domain_trust_score(url)
        
        # 2. Keyword matching score
        keywords = QueryBuilder.extract_keywords(skill)
        keyword_score = cls._calculate_keyword_match(
            keywords,
            title,
            snippet
        )
        
        # 3. Snippet richness (length and quality)
        snippet_score = cls._calculate_snippet_richness(snippet)
        
        # 4. Title quality
        title_score = cls._calculate_title_quality(title, skill)
        
        # Weighted sum
        total_score = (
            domain_score * cls.GOOGLE_WEIGHTS["domain_trust"] +
            keyword_score * cls.GOOGLE_WEIGHTS["keyword_match"] +
            snippet_score * cls.GOOGLE_WEIGHTS["snippet_richness"] +
            title_score * cls.GOOGLE_WEIGHTS["title_quality"]
        )
        
        return min(total_score, 1.0)  # Cap at 1.0
    
    @classmethod
    def score_youtube_result(cls, result: Dict[str, Any], skill: str, is_playlist: bool = True) -> float:
        """
        Calculate confidence score for a YouTube result.
        
        Args:
            result: Normalized YouTube result
            skill: Original skill name
            is_playlist: Whether this is a playlist or single video
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        title = result.get("title", "")
        description = result.get("description", "")
        
        # NEW: Check if content is tech-relevant based on title/description
        # We create a pseudo-URL for checking (YouTube is always tech-friendly platform)
        if not is_tech_relevant_domain("youtube.com", title, description):
            print(f"  ⚠️  Filtering non-tech YouTube content: {title[:50]}...")
            return 0.0
        
        # 1. Channel trust score
        channel_score = get_channel_trust_score(result.get("channel", ""))
        
        # 2. Keyword matching
        keywords = QueryBuilder.extract_keywords(skill)
        keyword_score = cls._calculate_keyword_match(
            keywords,
            title,
            description
        )
        
        # 3. Engagement metrics (views, likes)
        engagement_score = cls._calculate_engagement_score(result)
        
        # 4. Playlist length appropriateness (if playlist)
        if is_playlist:
            length_score = cls._calculate_playlist_length_score(result.get("video_count", 0))
        else:
            length_score = 0.8  # Default for videos
        
        # Weighted sum
        total_score = (
            channel_score * cls.YOUTUBE_WEIGHTS["channel_trust"] +
            keyword_score * cls.YOUTUBE_WEIGHTS["keyword_match"] +
            engagement_score * cls.YOUTUBE_WEIGHTS["engagement"] +
            length_score * cls.YOUTUBE_WEIGHTS["playlist_length"]
        )
        
        return min(total_score, 1.0)
    
    @staticmethod
    def _calculate_keyword_match(keywords: List[str], title: str, description: str) -> float:
        """
        Calculate keyword matching score.
        
        Args:
            keywords: List of keywords from skill
            title: Title text
            description: Description/snippet text
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not keywords:
            return 0.5
        
        title_lower = title.lower()
        description_lower = description.lower()
        
        # Count keyword matches
        title_matches = sum(1 for kw in keywords if kw.lower() in title_lower)
        description_matches = sum(1 for kw in keywords if kw.lower() in description_lower)
        
        # Title matches are weighted higher
        total_matches = (title_matches * 2) + description_matches
        max_possible = len(keywords) * 3  # 2 for title + 1 for description
        
        if max_possible == 0:
            return 0.5
        
        return min(total_matches / max_possible, 1.0)
    
    @staticmethod
    def _calculate_snippet_richness(snippet: str) -> float:
        """
        Calculate snippet quality based on length and informativeness.
        
        Args:
            snippet: Snippet text
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not snippet:
            return 0.3
        
        # Length score (prefer 100-300 characters)
        length = len(snippet)
        if 100 <= length <= 300:
            length_score = 1.0
        elif length < 100:
            length_score = length / 100
        else:
            length_score = max(0.5, 1.0 - (length - 300) / 500)
        
        # Check for learning-related keywords
        learning_keywords = ['learn', 'tutorial', 'guide', 'course', 'beginner', 'step', 'example']
        keyword_count = sum(1 for kw in learning_keywords if kw in snippet.lower())
        keyword_score = min(keyword_count / 3, 1.0)
        
        return (length_score * 0.6 + keyword_score * 0.4)
    
    @staticmethod
    def _calculate_title_quality(title: str, skill: str) -> float:
        """
        Evaluate title quality for learning resources.
        
        Args:
            title: Title text
            skill: Skill name
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not title:
            return 0.3
        
        title_lower = title.lower()
        skill_lower = skill.lower()
        
        # Exact skill match in title
        skill_match = 1.0 if skill_lower in title_lower else 0.5
        
        # Positive indicators
        positive_keywords = ['tutorial', 'guide', 'learn', 'course', 'documentation', 'beginner', 'complete']
        positive_count = sum(1 for kw in positive_keywords if kw in title_lower)
        positive_score = min(positive_count / 2, 1.0)
        
        # Negative indicators (clickbait, ads)
        negative_keywords = ['click here', 'buy now', 'discount', 'free download', 'hack', 'secret']
        has_negative = any(kw in title_lower for kw in negative_keywords)
        negative_penalty = 0.5 if has_negative else 0.0
        
        score = (skill_match * 0.5 + positive_score * 0.5) - negative_penalty
        return max(0.0, min(score, 1.0))
    
    @staticmethod
    def _calculate_engagement_score(result: Dict[str, Any]) -> float:
        """
        Calculate engagement score from view/like counts.
        
        Args:
            result: YouTube result with statistics
            
        Returns:
            Score between 0.0 and 1.0
        """
        view_count = result.get("view_count", 0)
        like_count = result.get("like_count", 0)
        
        # If no statistics, use neutral score
        if view_count == 0:
            return 0.6
        
        # View score (logarithmic scale)
        # 1K views = 0.3, 10K = 0.5, 100K = 0.7, 1M+ = 1.0
        if view_count >= 1_000_000:
            view_score = 1.0
        elif view_count >= 100_000:
            view_score = 0.7
        elif view_count >= 10_000:
            view_score = 0.5
        elif view_count >= 1_000:
            view_score = 0.3
        else:
            view_score = 0.2
        
        # Like ratio (likes / views)
        if view_count > 0:
            like_ratio = like_count / view_count
            # Good ratio is 2-5%, excellent is 5%+
            if like_ratio >= 0.05:
                like_score = 1.0
            elif like_ratio >= 0.02:
                like_score = 0.8
            else:
                like_score = 0.5
        else:
            like_score = 0.5
        
        return (view_score * 0.7 + like_score * 0.3)
    
    @staticmethod
    def _calculate_playlist_length_score(video_count: int) -> float:
        """
        Score playlist based on length appropriateness.
        
        Args:
            video_count: Number of videos in playlist
            
        Returns:
            Score between 0.0 and 1.0
        """
        if video_count == 0:
            return 0.5
        
        # Ideal range: 10-50 videos
        # Too short (<5) or too long (>100) get penalized
        if 10 <= video_count <= 50:
            return 1.0
        elif 5 <= video_count < 10 or 50 < video_count <= 80:
            return 0.8
        elif video_count < 5:
            return 0.4
        else:  # > 80
            return 0.3
    
    @classmethod
    def filter_by_threshold(cls, results: List[Dict[str, Any]], threshold: float = None) -> List[Dict[str, Any]]:
        """
        Filter results by confidence threshold.
        
        Args:
            results: List of scored results
            threshold: Minimum confidence threshold
            
        Returns:
            Filtered list
        """
        if threshold is None:
            threshold = cls.MIN_CONFIDENCE_THRESHOLD
        
        return [r for r in results if r.get("confidence", 0) >= threshold]
    
    @staticmethod
    def rank_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort results by confidence score (descending).
        
        Args:
            results: List of scored results
            
        Returns:
            Sorted list
        """
        return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)
