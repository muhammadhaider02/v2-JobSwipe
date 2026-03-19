"""
Result normalizer for standardizing output format.
Ensures consistent data structure across different providers.
"""
from typing import List, Dict, Any
from models.learning_resources import GoogleResult, YouTubeResult, SkillResources


class ResultNormalizer:
    """Normalizes and standardizes learning resource results"""
    
    @staticmethod
    def normalize_google_result(raw_result: Dict[str, Any], confidence: float) -> GoogleResult:
        """
        Convert raw Google result to standardized format.
        
        Args:
            raw_result: Raw result from Google Search
            confidence: Calculated confidence score
            
        Returns:
            GoogleResult object
        """
        return GoogleResult(
            title=raw_result.get("title", ""),
            url=raw_result.get("url", ""),
            snippet=raw_result.get("snippet", ""),
            domain=raw_result.get("domain", ""),
            confidence=confidence,
            metadata=raw_result.get("metadata", {})
        )
    
    @staticmethod
    def normalize_youtube_result(raw_result: Dict[str, Any], confidence: float) -> YouTubeResult:
        """
        Convert raw YouTube result to standardized format.
        
        Args:
            raw_result: Raw result from YouTube API
            confidence: Calculated confidence score
            
        Returns:
            YouTubeResult object
        """
        return YouTubeResult(
            title=raw_result.get("title", ""),
            channel=raw_result.get("channel", ""),
            url=raw_result.get("url", ""),
            video_count=raw_result.get("video_count"),
            description=raw_result.get("description", ""),
            confidence=confidence,
            subscriber_count=raw_result.get("subscriber_count"),
            view_count=raw_result.get("view_count"),
            thumbnail_url=raw_result.get("thumbnail_url")
        )
    
    @staticmethod
    def create_skill_resources(
        skill: str,
        google_results: List[GoogleResult],
        youtube_results: List[YouTubeResult]
    ) -> SkillResources:
        """
        Create complete skill resources object.
        
        Args:
            skill: Skill name
            google_results: List of Google results
            youtube_results: List of YouTube results
            
        Returns:
            SkillResources object
        """
        # Calculate total confidence (average of all resource confidences)
        all_confidences = (
            [r.confidence for r in google_results] +
            [r.confidence for r in youtube_results]
        )
        
        total_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        return SkillResources(
            skill=skill,
            google_results=google_results,
            youtube_playlists=youtube_results,
            total_confidence=total_confidence
        )
