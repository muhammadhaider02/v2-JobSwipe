# debug_fetch.py
"""Fetch user profile and job data for debugging placeholder mapping."""
import os, sys
from pathlib import Path

# Ensure backend is on sys.path
backend_path = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_path))

from services.supabase_service import SupabaseService

USER_ID = "962ac783-6d5f-4efe-ab44-10079f889b24"
JOB_ID = "00655b8b-8dc4-4da5-acc8-0aecc7523efa"

svc = SupabaseService(use_service_role=True)

# Fetch specific user and job (as before)
print("User profile:")
print(svc.fetch_user_profile(USER_ID))
print("Job data:")
print(svc.fetch_job_by_id(JOB_ID))

# Fetch all rows from user_profiles table
print("\nAll user profiles:")
all_profiles = svc.client.table('user_profiles').select('*').execute()
print(all_profiles.data)

# Fetch all jobs (using existing method)
print("\nAll jobs:")
all_jobs = svc.fetch_all_jobs()
print(all_jobs)
