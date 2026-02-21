"""
Worker script - pops jobs from Redis queue and scrapes using python-jobspy.
Implements robust error handling, progress tracking, and raw HTML storage.
"""
import sys
import uuid
import time
import random
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from services.job_scraper_service import get_scraper_service
from services.database_service import DatabaseService
from scraper.scraper_logger import get_scraper_logger

# jobspy will be imported lazily when needed to avoid slow startup
JOBSPY_AVAILABLE = None  # Will be checked on first use


class JobWorker:
    """Worker that processes jobs from Redis queue using python-jobspy"""
    
    def __init__(self):
        self.scraper_service = get_scraper_service()
        self.db_service = DatabaseService()
        self.raw_html_dir = Path(__file__).parent / "raw_html"
        self.raw_html_dir.mkdir(exist_ok=True)
        self.logger = get_scraper_logger()
    
    def save_raw_html(
        self, 
        html_content: str, 
        user_id: str, 
        source: str,
        job_id: str
    ) -> str:
        """
        Save raw HTML to file for later parsing.
        Returns the file path.
        """
        # Create user-specific directory
        user_dir = self.raw_html_dir / user_id
        user_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{source}_{job_id[:8]}.html"
        file_path = user_dir / filename
        
        # Write HTML content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(file_path)
    
    def scrape_with_jobspy(
        self,
        search_term: str,
        location: str = "Pakistan",
        results_wanted: int = 5,
        is_remote: bool = False
    ) -> tuple[List[Dict[str, Any]], int, int]:
        """
        Scrape jobs using python-jobspy library.
        
        Returns: (jobs_list, success_count, error_count)
        """
        global JOBSPY_AVAILABLE
        
        # Lazy import jobspy
        if JOBSPY_AVAILABLE is None:
            try:
                from jobspy import scrape_jobs
                JOBSPY_AVAILABLE = True
            except ImportError:
                print("⚠ Warning: python-jobspy not installed. Install with: pip install python-jobspy")
                JOBSPY_AVAILABLE = False
        
        if not JOBSPY_AVAILABLE:
            raise ImportError("python-jobspy is not installed")
        
        # Import here to avoid loading at module level
        from jobspy import scrape_jobs
        
        success_count = 0
        error_count = 0
        jobs_list = []
        
        try:
            # Strategy: Prioritize jobs in Pakistan, fallback to remote jobs for platforms that don't support Pakistan
            # Indeed and LinkedIn support Pakistan location
            # Glassdoor and ZipRecruiter may not support Pakistan well, so we'll use remote jobs for those
            
            if location == "Pakistan":
                self.logger.logger.info(f"🔍 Scraping for: '{search_term}' in Pakistan")
                actual_location = "Pakistan"
                # Indeed and LinkedIn support Pakistan directly
                site_names = ["indeed", "linkedin"]
                country_indeed = "Pakistan"
                is_remote_filter = False
                
                self.logger.logger.info(f"Sites: {', '.join(site_names)}, Location: Pakistan, Results wanted: {results_wanted}")
                
                # First, scrape jobs IN Pakistan
                jobs_df = scrape_jobs(
                    site_name=site_names,
                    search_term=search_term,
                    location=actual_location,
                    results_wanted=results_wanted,
                    hours_old=168,  # Jobs posted in last week
                    country_indeed=country_indeed,
                    is_remote=is_remote_filter
                )
                
                # If we didn't get enough jobs from Pakistan, also try remote jobs
                jobs_found = len(jobs_df) if jobs_df is not None and not jobs_df.empty else 0
                if jobs_found < results_wanted:
                    self.logger.logger.info(f"Found {jobs_found} jobs in Pakistan, fetching remote jobs to reach target...")
                    
                    # Scrape remote jobs from all platforms
                    remote_jobs_df = scrape_jobs(
                        site_name=["indeed", "linkedin", "zip_recruiter"],
                        search_term=search_term,
                        location="Remote",
                        results_wanted=results_wanted - jobs_found,
                        hours_old=168,
                        country_indeed="USA",  # Remote jobs are usually US-based
                        is_remote=True
                    )
                    
                    # Combine both results
                    if remote_jobs_df is not None and not remote_jobs_df.empty:
                        import pandas as pd
                        if jobs_df is not None and not jobs_df.empty:
                            jobs_df = pd.concat([jobs_df, remote_jobs_df], ignore_index=True)
                        else:
                            jobs_df = remote_jobs_df
                        self.logger.logger.info(f"✓ Combined: {len(jobs_df)} total jobs (Pakistan + Remote)")
                
            else:
                self.logger.logger.info(f"🔍 Scraping for: '{search_term}' in {location}")
                actual_location = location
                site_names = ["indeed", "linkedin", "zip_recruiter", "glassdoor"]
                
                self.logger.logger.info(f"Sites: {', '.join(site_names)}, Results wanted: {results_wanted}")
                
                # Call jobspy scrape_jobs function
                jobs_df = scrape_jobs(
                    site_name=site_names,
                    search_term=search_term,
                    location=actual_location,
                    results_wanted=results_wanted,
                    hours_old=168,
                    country_indeed="USA",
                    is_remote=False
                )
            
            if jobs_df is not None and not jobs_df.empty:
                success_count = len(jobs_df)
                self.logger.logger.info(f"✓ Found {success_count} jobs for '{search_term}'")
                
                # Convert DataFrame to list of dictionaries
                jobs_list = jobs_df.to_dict('records')
                
                # Add metadata to each job
                for job in jobs_list:
                    job['scraped_at'] = datetime.now().isoformat()
                    job['search_term'] = search_term
                    job['location_searched'] = location
            else:
                self.logger.logger.warning(f"⚠ No jobs found for '{search_term}'")
                
        except Exception as e:
            error_count = 1
            self.logger.log_error(f"scrape_with_jobspy for '{search_term}'", e)
        
        return jobs_list, success_count, error_count
    
    def process_jobspy_task(
        self,
        job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a jobspy scraping task from the queue.
        
        Returns processing result with statistics.
        """
        scrape_id = job_data.get('scrape_id')
        user_id = job_data.get('user_id')
        filters = job_data.get('filters', {})
        
        search_term = filters.get('search_term')
        location = filters.get('location', 'Pakistan')
        results_wanted = filters.get('results_wanted', 5)
        is_remote = filters.get('is_remote', False)
        
        self.logger.logger.info(f"\n{'─'*50}")
        self.logger.logger.info(f"Processing Role: {search_term}")
        self.logger.logger.info(f"{'─'*50}")
        
        # Scrape jobs using jobspy
        jobs_list, success_count, error_count = self.scrape_with_jobspy(
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            is_remote=is_remote
        )
        
        # Save raw HTML for each job
        saved_files = []
        for job in jobs_list:
            try:
                # Generate unique job ID
                job_id = str(uuid.uuid4())
                
                # Create HTML representation of job data
                html_content = self._create_html_from_job(job)
                
                # Save to file
                file_path = self.save_raw_html(
                    html_content=html_content,
                    user_id=user_id,
                    source='random_role_scrape',
                    job_id=job_id
                )
                
                saved_files.append(file_path)
                job['raw_html_path'] = file_path
                job['job_id'] = job_id
                
                # Log successful save
                html_size = len(html_content)
                self.logger.log_job_success(
                    url=job.get('job_url', 'N/A'),
                    source='jobspy',
                    html_size=html_size,
                    file_path=file_path,
                    job_id=job_id
                )
                
            except Exception as e:
                self.logger.log_error(f"save_raw_html for job", e)
        
        self.logger.logger.info(f"💾 Saved {len(saved_files)} raw HTML files")
        
        # Store jobs in database (optional, for later parsing)
        try:
            self._store_jobs_metadata(scrape_id, user_id, jobs_list)
        except Exception as e:
            self.logger.log_error("store_jobs_metadata", e)
        
        return {
            "role": search_term,
            "jobs_found": success_count,
            "jobs_saved": len(saved_files),
            "errors": error_count,
            "files": saved_files
        }
    
    def _create_html_from_job(self, job: Dict[str, Any]) -> str:
        """
        Create HTML representation of job data.
        This preserves the raw data for later parsing.
        """
        # Convert date objects to strings for JSON serialization
        job_copy = job.copy()
        for key, value in job_copy.items():
            if hasattr(value, 'isoformat'):  # datetime, date objects
                job_copy[key] = value.isoformat()
        
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{job_copy.get('title', 'Job')} - {job_copy.get('company', 'Company')}</title>
</head>
<body>
    <div class="job-listing" data-job-id="{job_copy.get('id', '')}">
        <h1 class="job-title">{job_copy.get('title', 'N/A')}</h1>
        <h2 class="company-name">{job_copy.get('company', 'N/A')}</h2>
        
        <div class="job-details">
            <p class="location">{job_copy.get('location', 'N/A')}</p>
            <p class="date-posted">{job_copy.get('date_posted', 'N/A')}</p>
            <p class="job-type">{job_copy.get('job_type', 'N/A')}</p>
            <p class="salary">{job_copy.get('min_amount', 'N/A')} - {job_copy.get('max_amount', 'N/A')} {job_copy.get('currency', '')}</p>
        </div>
        
        <div class="job-description">
            <h3>Description</h3>
            <div class="description-text">
{job_copy.get('description', 'No description available')}
            </div>
        </div>
        
        <div class="job-url">
            <a href="{job_copy.get('job_url', '#')}">{job_copy.get('job_url', 'N/A')}</a>
        </div>
        
        <div class="metadata">
            <script type="application/json" id="job-data">
{json.dumps(job_copy, indent=2)}
            </script>
        </div>
    </div>
</body>
</html>
"""
        return html_template
    
    def _store_jobs_metadata(
        self,
        scrape_id: str,
        user_id: str,
        jobs_list: List[Dict[str, Any]]
    ):
        """
        Store job metadata in database for tracking.
        Appends jobs to existing metadata file or creates new one.
        """
        # Create a metadata file for this scrape
        metadata_dir = self.raw_html_dir / user_id / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = metadata_dir / f"{scrape_id}_metadata.json"
        
        # Convert date objects in jobs_list
        jobs_serializable = []
        for job in jobs_list:
            job_copy = job.copy()
            for key, value in job_copy.items():
                if hasattr(value, 'isoformat'):  # datetime, date objects
                    job_copy[key] = value.isoformat()
            jobs_serializable.append(job_copy)
        
        # Load existing metadata if file exists
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    existing_metadata = json.load(f)
                existing_jobs = existing_metadata.get("jobs", [])
                # Append new jobs to existing ones
                all_jobs = existing_jobs + jobs_serializable
                self.logger.logger.info(f"📋 Appending {len(jobs_serializable)} jobs to existing {len(existing_jobs)} jobs")
            except Exception as e:
                self.logger.logger.warning(f"Could not load existing metadata: {e}. Creating new file.")
                all_jobs = jobs_serializable
        else:
            all_jobs = jobs_serializable
        
        metadata = {
            "scrape_id": scrape_id,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "jobs_count": len(all_jobs),
            "jobs": all_jobs
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.logger.info(f"📋 Metadata saved to: {metadata_file} (Total: {len(all_jobs)} jobs)")
    
    def run(
        self,
        scrape_id: str,
        limit: int = 5,
        timeout: int = 300
    ) -> int:
        """
        Run the worker to process jobs from queue.
        
        Args:
            scrape_id: The scrape session ID
            limit: Maximum number of tasks to process
            timeout: Maximum time to wait for each job (seconds)
        
        Returns:
            Number of tasks processed
        """
        # Check if jobspy is available before starting
        global JOBSPY_AVAILABLE
        if JOBSPY_AVAILABLE is None:
            try:
                from jobspy import scrape_jobs
                JOBSPY_AVAILABLE = True
                self.logger.logger.info("✓ python-jobspy is available")
            except ImportError:
                JOBSPY_AVAILABLE = False
        
        if not JOBSPY_AVAILABLE:
            self.logger.logger.error("✗ Cannot run worker: python-jobspy not installed")
            self.logger.logger.error("  Install with: pip install python-jobspy")
            return 0
        
        self.logger.log_worker_start(scrape_id, limit)
        self.logger.logger.info(f"Timeout: {timeout}s")
        
        processed_count = 0
        total_jobs_found = 0
        total_errors = 0
        start_time = time.time()
        
        try:
            while processed_count < limit:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    self.logger.logger.warning(f"⏱ Worker timeout reached ({timeout}s)")
                    break
                
                # Pop job from queue
                self.logger.logger.info(f"[{processed_count + 1}/{limit}] Waiting for job from queue...")
                job_data = self.scraper_service.pop_job_from_queue(timeout=30)
                
                if job_data is None:
                    self.logger.log_worker_idle(scrape_id, 30)
                    continue
                
                # Check if this is a jobspy task
                if job_data.get('url') != 'jobspy':
                    self.logger.log_job_skipped(job_data.get('url'), "non-jobspy task")
                    continue
                
                # Process the task
                try:
                    result = self.process_jobspy_task(job_data)
                    processed_count += 1
                    total_jobs_found += result['jobs_found']
                    total_errors += result['errors']
                    
                    # Publish progress
                    self.scraper_service.publish_progress(scrape_id, {
                        "completed": processed_count,
                        "total": limit,
                        "status": "running",
                        "message": f"Processed role: {result['role']} ({result['jobs_found']} jobs)",
                        "jobs_found": total_jobs_found
                    })
                    
                    # Random delay to avoid rate limiting
                    delay = random.uniform(2, 5)
                    self.logger.log_rate_limit("jobspy", delay)
                    time.sleep(delay)
                    
                except Exception as e:
                    self.logger.log_error("process_jobspy_task", e)
                    total_errors += 1
                    processed_count += 1  # Count as processed even if error
        
        except KeyboardInterrupt:
            self.logger.logger.warning("⚠ Worker interrupted by user")
        
        # Final summary
        elapsed_time = time.time() - start_time
        self.logger.log_scrape_complete(scrape_id, processed_count, limit, elapsed_time)
        self.logger.logger.info(f"✓ Total Jobs Found: {total_jobs_found}")
        self.logger.logger.info(f"✗ Errors: {total_errors}")
        
        # Publish final status
        self.scraper_service.publish_progress(scrape_id, {
            "completed": processed_count,
            "total": limit,
            "status": "completed",
            "message": f"Scraping completed: {total_jobs_found} jobs found",
            "jobs_found": total_jobs_found,
            "errors": total_errors
        })
        
        return processed_count


def main():
    """Test the worker"""
    worker = JobWorker()
    
    # Run worker (will wait for jobs in queue)
    scrape_id = "test_scrape_001"
    processed = worker.run(scrape_id, limit=5, timeout=300)
    
    print(f"\n✓ Worker test complete: {processed} tasks processed")


if __name__ == "__main__":
    main()
