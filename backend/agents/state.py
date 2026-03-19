"""
Agent state definition for LangGraph workflow.

Defines the shared state that flows through all agent nodes with type safety.
"""

from typing import TypedDict, Annotated, Sequence, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Shared state for multi-agent workflow.
    
    State flows through: Scout -> Vetting Officer -> Campaign Manager -> HITL -> Apply
    
    Attributes:
        messages: Chat history with add_messages reducer for appending
        user_id: Supabase user UUID
        user_profile: Complete user profile with skills, preferences, experience
        search_query: Original job search query (e.g., "python developer lahore")
        raw_job_list: Jobs scraped by Digital Scout (unvetted)
        vetted_jobs: Jobs approved by Vetting Officer with scores
        target_job: Single job selected for application
        optimized_materials: Generated resume/cover letter
        human_approval: HITL approval status
        scraping_status: Scraping progress (pending/in_progress/completed/failed)
        current_page: Pagination state for Spider
        error: Last error message (if any)
        retry_count: Number of retries for current operation
    """
    
    # LangGraph message history with reducer
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # User context
    user_id: str
    user_profile: Optional[Dict[str, Any]]
    search_query: str
    
    # Scout outputs
    raw_job_list: List[Dict[str, Any]]
    scraping_status: str  # "pending" | "in_progress" | "completed" | "failed"
    current_page: int
    
    # Vetting Officer outputs
    vetted_jobs: List[Dict[str, Any]]  # Each job has: job_id, match_score, reasoning, confidence
    
    # Campaign Manager outputs
    target_job: Optional[Dict[str, Any]]  # Single job for application
    optimized_materials: Optional[Dict[str, Any]]  # ApplicationMaterials with resume + cover letter
    application_status: Optional[str]  # "pending" | "filled" | "submitted" | "error"
    screenshot_path: Optional[str]  # Screenshot of filled form for review
    fallback_url: Optional[str]  # URL for manual application if automation fails
    
    # HITL state
    human_approval: Optional[str]  # "approved" | "rejected" | "pending"

    # Persistent auth/session gate
    auth_required: Optional[bool]
    auth_status: Optional[str]  # "authenticated" | "waiting_for_login" | "failed"
    auth_message: Optional[str]
    browser_instance_id: Optional[str]
    browser_tab_id: Optional[str]
    login_resume_requested: Optional[bool]
    login_wait_started_at: Optional[str]
    resume_command: Optional[str]  # expected value: "resume"
    
    # Error handling
    error: Optional[str]
    retry_count: int


class JobData(TypedDict):
    """Job data structure returned by parsers."""
    
    job_id: str  # SHA256 hash
    title: str
    company: str
    location: str
    job_url: str
    board: str  # "linkedin" | "rozee" | "indeed" | "mustakbil"
    description: str
    skills: List[str]
    posted_date: Optional[str]
    salary: Optional[str]
    employment_type: Optional[str]  # "full-time" | "part-time" | "contract" | "internship"
    experience_required: Optional[str]
    raw_html: str  # For debugging/re-parsing


class EnrichedJobData(JobData):
    """Job data with enrichment fields (extends JobData)."""
    
    # Enhanced description
    description_sections: Optional[Dict[str, str]]  # responsibilities, requirements, etc.
    
    # Enhanced skills (categorized)
    skills_categorized: Optional[Dict[str, List[str]]]  # technical, soft, tools
    
    # Structured experience (replaces string)
    experience_parsed: Optional[Dict[str, Any]]  # min_years, max_years, level, raw_text
    
    # Normalized salary (replaces string)
    salary_normalized: Optional[Dict[str, Any]]  # currency, min, max, period, raw
    
    # Metadata
    enrichment_confidence: float  # 0-1 score for overall quality
    enrichment_timestamp: str  # ISO timestamp


class VettedJob(TypedDict):
    """Job with vetting analysis from Vetting Officer."""
    
    job_id: str
    job_data: JobData
    match_score: float  # 0-1 similarity score
    reasoning: str  # LLM-generated reasoning
    confidence: str  # "high" | "medium" | "low"
    recommendation: str  # "strong_fit" | "moderate_fit" | "weak_fit"
    skill_gaps: List[str]
    matching_skills: List[str]


class ApplicationMaterials(TypedDict):
    """Generated materials from Campaign Manager."""
    
    resume: Dict[str, Any]  # Optimized resume JSON
    cover_letter: str  # Generated cover letter text
    metadata: Dict[str, Any]  # Optimization metadata (keywords matched, confidence, etc.)
    generated_at: str  # ISO timestamp
    job_id: str  # Associated job ID
    job_title: str  # Job title for reference
    company: str  # Company name for reference
