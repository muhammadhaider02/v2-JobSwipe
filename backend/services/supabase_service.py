"""
Supabase service for fetching job data from Supabase.
Handles connection and querying of the jobs table.
"""
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env.local")

logger = logging.getLogger(__name__)


class SupabaseService:
    """Service for interacting with Supabase jobs table"""
    
    def __init__(self, use_service_role: bool = False):
        """
        Initialize Supabase client
        
        Args:
            use_service_role: If True, use service role key (bypasses RLS). 
                            If False, use anon key (respects RLS policies)
        """
        supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        
        if use_service_role:
            # Use service role key for admin operations (bypasses RLS)
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not supabase_key:
                raise ValueError(
                    "Missing SUPABASE_SERVICE_ROLE_KEY in .env.local. "
                    "This is required when use_service_role=True"
                )
        else:
            # Use anon key for client operations (respects RLS)
            supabase_key = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_OR_ANON_KEY")
            if not supabase_key:
                raise ValueError(
                    "Missing NEXT_PUBLIC_SUPABASE_PUBLISHABLE_OR_ANON_KEY in .env.local"
                )
        
        if not supabase_url:
            raise ValueError("Missing Supabase URL in .env.local")
        
        self.client: Client = create_client(supabase_url, supabase_key)
        self.table_name = "jobs"
    
    def fetch_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Fetch all jobs from Supabase.
        
        Returns:
            List of job dictionaries
        """
        try:
            response = self.client.table(self.table_name).select("*").execute()
            jobs = response.data if response.data else []
            logger.info(f"Fetched {len(jobs)} jobs from Supabase")
            return jobs
        except Exception as e:
            logger.error(f"Error fetching all jobs from Supabase: {e}")
            raise
    
    def fetch_jobs_by_ids(self, job_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch specific jobs by their IDs.
        
        Args:
            job_ids: List of job IDs to fetch
            
        Returns:
            List of job dictionaries
        """
        if not job_ids:
            return []
        
        try:
            response = (
                self.client.table(self.table_name)
                .select("*")
                .in_("job_id", job_ids)
                .execute()
            )
            jobs = response.data if response.data else []
            logger.info(f"Fetched {len(jobs)} jobs by IDs from Supabase")
            return jobs
        except Exception as e:
            logger.error(f"Error fetching jobs by IDs from Supabase: {e}")
            raise
    
    def fetch_new_jobs(self, existing_job_ids: List[str], last_sync_timestamp: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch new jobs that are not in the existing job_ids list.
        Optionally filter by created_at timestamp.
        
        Args:
            existing_job_ids: List of job IDs that already exist locally
            last_sync_timestamp: Optional timestamp to filter by created_at
            
        Returns:
            List of new job dictionaries
        """
        try:
            query = self.client.table(self.table_name).select("*")
            
            # Filter out existing job IDs
            if existing_job_ids:
                query = query.not_.in_("job_id", existing_job_ids)
            
            # Filter by created_at if provided
            if last_sync_timestamp:
                query = query.gt("created_at", last_sync_timestamp)
            
            response = query.execute()
            jobs = response.data if response.data else []
            logger.info(f"Fetched {len(jobs)} new jobs from Supabase")
            return jobs
        except Exception as e:
            logger.error(f"Error fetching new jobs from Supabase: {e}")
            raise
    
    def fetch_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetch a user profile by user_id.
        Returns a dict with user profile fields or empty dict if not found.
        """
        try:
            response = (
                self.client.table('user_profiles')
                .select('*')
                .eq('user_id', user_id)
                .execute()
            )
            data = response.data if response.data else []
            logger.info(f"Fetched user profile for user_id {user_id}: {bool(data)}")
            return data[0] if data else {}
        except Exception as e:
            logger.error(f"Error fetching user profile for {user_id}: {e}")
            raise

    def fetch_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single job by its ID.
        
        Args:
            job_id: The job ID to fetch
            
        Returns:
            Job dictionary or None if not found
        """
        try:
            response = (
                self.client.table(self.table_name)
                .select("*")
                .eq("job_id", job_id)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching job {job_id} from Supabase: {e}")
            raise

    def fetch_five_user_profiles(self) -> List[Dict[str, Any]]:
        """Fetch up to 5 user profile rows.
        Returns a list of at most 5 user profile dictionaries.
        """
        try:
            response = self.client.table('user_profiles').select('*').limit(5).execute()
            profiles = response.data if response.data else []
            logger.info(f"Fetched {len(profiles)} user profiles (limit 5) from Supabase")
            return profiles
        except Exception as e:
            logger.error(f"Error fetching limited user profiles: {e}")
            raise

    def fetch_five_jobs(self) -> List[Dict[str, Any]]:
        """Fetch up to 5 job rows.
        Returns a list of at most 5 job dictionaries.
        """
        try:
            response = self.client.table(self.table_name).select('*').limit(1).execute()
            jobs = response.data if response.data else []
            logger.info(f"Fetched {len(jobs)} jobs (limit 5) from Supabase")
            return jobs
        except Exception as e:
            logger.error(f"Error fetching limited jobs: {e}")
            raise
