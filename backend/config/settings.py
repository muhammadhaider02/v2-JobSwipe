"""
Configuration settings for JobSwipe Multi-Agent System.

Loads environment variables and provides centralized configuration access.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    redis_job_queue_prefix: str = Field(default="jobswipe:jobs", description="Redis key prefix for job queues")
    redis_max_retries: int = Field(default=3, description="Maximum Redis connection retries")
    redis_processed_ttl: int = Field(default=604800, description="TTL for processed job IDs (7 days)")
    
    # Supabase Configuration
    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_service_role_key: str = Field(default="", description="Supabase service role key")
    supabase_anon_key: str = Field(default="", description="Supabase anonymous key")
    
    # SambaNova LLM Configuration
    sambanova_api_key: str = Field(default="", description="SambaNova API key")
    sambanova_base_url: str = Field(default="https://api.sambanova.ai/v1", description="SambaNova API base URL")
    sambanova_model: str = Field(default="meta-llama/Meta-Llama-3.1-8B-Instruct", description="LLM model name")
    
    # Rate Limiting
    rate_limit_calls_per_minute: int = Field(default=10, description="Max LLM calls per minute")
    rate_limit_cooldown_seconds: float = Field(default=6.0, description="Cooldown between LLM calls")
    
    # Scrapling Configuration
    scrapling_cache_dir: str = Field(default="./scrapling_cache", description="Scrapling checkpoint directory")
    scrapling_max_pages: int = Field(default=3, description="Browser tab pool size for StealthySession")
    
    # Job Scraping Configuration
    job_scraping_concurrent_requests: int = Field(default=5, description="Concurrent HTTP requests")
    job_scraping_download_delay: float = Field(default=2.0, description="Delay between requests (seconds)")
    job_scraping_max_results: int = Field(default=50, description="Maximum jobs to scrape per search")
    
    # Agent Configuration
    agent_db_path: str = Field(default="jobswipe_agent.db", description="SQLite checkpoint database path")
    agent_match_threshold: float = Field(default=0.5, description="Minimum skill match score for vetting")
    campaign_ats_score_threshold: float = Field(default=0.90, description="Minimum ATS score to stop campaign retry loop")
    campaign_max_tailoring_retries: int = Field(default=1, description="Max retry attempts for campaign material tailoring")
    pinchtab_base_url: str = Field(default="http://127.0.0.1:9867", description="PinchTab server base URL")
    pinchtab_token: str = Field(default="", description="PinchTab bearer token")
    pinchtab_mode: str = Field(default="headed", description="Default PinchTab instance mode: headed or headless")
    pinchtab_profile_prefix: str = Field(default="jobswipe", description="Profile name prefix for PinchTab sessions")
    pinchtab_request_timeout_sec: int = Field(default=60, description="Timeout for PinchTab HTTP requests")
    pinchtab_profile_data_dir: str = Field(default="agent_data", description="Persistent profile data directory for PinchTab")
    pinchtab_first_run_headed: bool = Field(default=True, description="Force first auth bootstrap run in headed mode")
    pinchtab_auth_wait_timeout_sec: int = Field(default=600, description="Max seconds to wait for manual login resume")
    pinchtab_auth_poll_interval_sec: float = Field(default=4.0, description="Auth status poll interval in seconds")
    pinchtab_proxy_rotation_enabled: bool = Field(default=True, description="Enable rotating proxy/IP for each apply session")
    pinchtab_rotate_ip_per_apply: bool = Field(default=True, description="When proxy rotation is enabled, rotate to next IP on each apply")
    pinchtab_auth_session_priority: bool = Field(default=True, description="Prefer reusing existing authenticated session over forcing rotation")
    pinchtab_proxy_list_file: str = Field(default="valid_ips.txt", description="Path to proxy list file relative to backend dir")
    pinchtab_proxy_scheme: str = Field(default="http", description="Proxy scheme used when not present in proxy list")
    
    # Existing settings (from original .env.local)
    faiss_index_path: str = Field(default="models/skills_faiss.index", description="FAISS index path")
    metadata_path: str = Field(default="models/metadata.pkl", description="Metadata pickle path")
    excel_skill_gap: str = Field(default="models/excel/skill_gap.xlsx", description="Skill gap Excel path")
    sheet_skill_gap: str = Field(default="Sheet1", description="Skill gap sheet name")
    embedding_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model")
    sentence_transformers_home: str = Field(default="models/sentence_transformers", description="ST cache dir")
    
    @property
    def backend_dir(self) -> Path:
        """Get backend directory path."""
        return Path(__file__).resolve().parent.parent
    
    @property
    def scrapling_cache_path(self) -> Path:
        """Get absolute path to Scrapling cache directory."""
        return self.backend_dir / self.scrapling_cache_dir
    
    @property
    def agent_db_full_path(self) -> Path:
        """Get absolute path to agent database."""
        return self.backend_dir / self.agent_db_path

    @property
    def pinchtab_profile_data_path(self) -> Path:
        """Get absolute path to persistent PinchTab profile directory."""
        return self.backend_dir / self.pinchtab_profile_data_dir

    @property
    def pinchtab_proxy_list_path(self) -> Path:
        """Get absolute path to proxy list used for IP rotation."""
        return self.backend_dir / self.pinchtab_proxy_list_file
    
    def validate_required_fields(self) -> list[str]:
        """
        Check if required fields are set.
        
        Returns:
            List of missing required field names
        """
        missing = []
        
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not self.sambanova_api_key:
            missing.append("SAMBANOVA_API_KEY")
            
        return missing


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create global settings instance.
    
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        
        # Validate required fields
        missing = _settings.validate_required_fields()
        if missing:
            print(f"⚠️  Warning: Missing required environment variables: {', '.join(missing)}")
            print("   Some features may not work correctly.")
    
    return _settings


def reload_settings() -> Settings:
    """
    Force reload settings from environment.
    
    Returns:
        New Settings instance
    """
    global _settings
    _settings = None
    return get_settings()
