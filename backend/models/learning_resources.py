"""
Data models for learning resources and skill validation.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class ResourceType(Enum):
    """Types of learning resources"""
    GOOGLE = "google"
    YOUTUBE_PLAYLIST = "youtube_playlist"
    YOUTUBE_VIDEO = "youtube_video"


@dataclass
class GoogleResult:
    """Normalized Google search result"""
    title: str
    url: str
    snippet: str
    domain: str
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "confidence": round(self.confidence, 2),
            "metadata": self.metadata or {}
        }


@dataclass
class YouTubeResult:
    """Normalized YouTube result (playlist or video)"""
    title: str
    channel: str
    url: str
    video_count: Optional[int]
    description: str
    confidence: float
    subscriber_count: Optional[int] = None
    view_count: Optional[int] = None
    thumbnail_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "title": self.title,
            "channel": self.channel,
            "url": self.url,
            "description": self.description,
            "confidence": round(self.confidence, 2),
            "thumbnail_url": self.thumbnail_url
        }
        if self.video_count:
            result["video_count"] = self.video_count
        if self.subscriber_count:
            result["subscriber_count"] = self.subscriber_count
        if self.view_count:
            result["view_count"] = self.view_count
        return result


@dataclass
class SkillResources:
    """Complete learning resources for a single skill"""
    skill: str
    google_results: List[GoogleResult]
    youtube_playlists: List[YouTubeResult]
    total_confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "google_results": [r.to_dict() for r in self.google_results],
            "youtube_playlists": [r.to_dict() for r in self.youtube_playlists],
            "total_confidence": round(self.total_confidence, 2)
        }


@dataclass
class LearningResource:
    """Model for a single learning resource"""
    id: str
    skill: str
    title: str
    url: str
    snippet: str
    source: str  # e.g., w3schools, mdn, geeksforgeeks
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class QuizQuestion:
    """Model for a quiz question"""
    id: str
    question_type: str  # 'mcq', 'short_answer', 'coding'
    question: str
    options: Optional[List[str]] = None  # For MCQs
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: str = "medium"  # easy, medium, hard
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class Quiz:
    """Model for a complete skill quiz"""
    id: str
    skill: str
    questions: List[QuizQuestion]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    total_points: int = 0
    source: str = "dynamic"  # "database" or "dynamic"
    matched_skill: Optional[str] = None  # For fuzzy matches
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "skill": self.skill,
            "questions": [q.to_dict() for q in self.questions],
            "created_at": self.created_at,
            "total_points": self.total_points,
            "source": self.source,
            "matched_skill": self.matched_skill
        }


@dataclass
class QuizSubmission:
    """Model for a user's quiz submission"""
    id: str
    quiz_id: str
    user_answers: Dict[str, str]  # question_id -> answer
    score: float
    total_points: int
    passed: bool
    feedback: Dict[str, Any]
    submitted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
