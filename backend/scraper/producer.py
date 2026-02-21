"""
Producer script - loads seed URLs from sources.json and pushes to Redis queue.
Implements deduplication using Redis Set to avoid re-scraping URLs.
"""
import json
import sys
import pandas as pd
import random
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import urlencode, urlparse, parse_qs

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from services.job_scraper_service import get_scraper_service


class JobProducer:
    """Produces job URLs and pushes them to Redis queue"""
    
    def __init__(self):
        self.scraper_service = get_scraper_service()
        self.sources_path = Path(__file__).parent / "sources.json"
        self.roles_excel_path = Path(__file__).parent.parent / "models" / "excel" / "skill_gap.xlsx"
        self.computing_roles = self._load_computing_roles()
    
    def _load_computing_roles(self) -> List[str]:
        """Load computing roles from Excel file"""
        try:
            df = pd.read_excel(self.roles_excel_path)
            roles = df['Role'].tolist()
            print(f"✓ Loaded {len(roles)} computing roles from Excel")
            return roles
        except Exception as e:
            print(f"⚠ Error loading roles from Excel: {e}")
            # Fallback to hardcoded roles
            return [
                'AI Engineer', 'Backend Developer', 'Data Scientist', 
                'DevOps Engineer', 'Frontend Developer', 'Full Stack Developer',
                'Software Engineer', 'ML Engineer', 'Mobile App Developer'
            ]
    
    def load_sources(self) -> Dict[str, List[str]]:
        """Load sources from JSON config file"""
        if not self.sources_path.exists():
            raise FileNotFoundError(f"Sources file not found: {self.sources_path}")
        
        with open(self.sources_path, 'r') as f:
            return json.load(f)
    
    def build_filtered_url(self, base_url: str, filters: Dict[str, Any]) -> str:
        """
        Build URL with filter parameters.
        Works for Rozee.pk and similar sites that accept query params.
        """
        parsed = urlparse(base_url)
        query_params = parse_qs(parsed.query)
        
        # Add filter parameters
        if filters.get('city'):
            query_params['loc'] = [filters['city']]
        
        if filters.get('experience_level'):
            # Map to Rozee.pk experience parameter
            exp_map = {
                'entry': '0-1',
                'mid': '2-5',
                'senior': '5-10',
                'lead': '10+',
                'executive': '10+'
            }
            exp_value = exp_map.get(filters['experience_level'], '')
            if exp_value:
                query_params['experience'] = [exp_value]
        
        if filters.get('job_type'):
            # Rozee.pk uses 'job_type' parameter
            job_type_map = {
                'remote': 'remote',
                'onsite': 'full-time',
                'hybrid': 'hybrid'
            }
            job_type_value = job_type_map.get(filters['job_type'], '')
            if job_type_value:
                query_params['job_type'] = [job_type_value]
        
        # Rebuild query string
        new_query = urlencode(query_params, doseq=True)
        new_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if new_query:
            new_url += f"?{new_query}"
        
        return new_url
    
    def filter_greenhouse_lever_by_location(self, url: str, city: str = None, country: str = None) -> bool:
        """
        Check if Greenhouse/Lever URL should be included based on location.
        For now, we include all (location filtering will happen at parse time).
        """
        return True
    
    def produce_jobs(
        self,
        scrape_id: str,
        user_id: str,
        filters: Dict[str, Any],
        limit: int = 5
    ) -> int:
        """
        Load computing roles from Excel and queue them for jobspy scraping.
        Uses python-jobspy library to scrape Glassdoor.
        
        Logic:
        - Shuffle computing roles and select first `limit` roles
        - For each role, queue a jobspy scraping task
        - Scrape 5 jobs per role from Glassdoor
        - Location: Pakistan (onsite) or Remote (if other countries)
        
        Returns number of roles queued.
        """
        print(f"\n{'='*60}")
        print(f"PRODUCER STARTING - JOBSPY SCRAPING")
        print(f"Scrape ID: {scrape_id}")
        print(f"User ID: {user_id}")
        print(f"Computing Roles Available: {len(self.computing_roles)}")
        print(f"Roles to Scrape: {limit}")
        print(f"Jobs per Role: 5")
        print(f"Location Strategy:")
        print(f"  1. Primary: Jobs IN Pakistan (Indeed, LinkedIn)")
        print(f"  2. Fallback: Remote jobs (if needed to meet quota)")
        print(f"{'='*60}\n")
        
        queued_count = 0
        
        # Shuffle roles for variety and limit to requested amount
        shuffled_roles = self.computing_roles.copy()
        random.shuffle(shuffled_roles)
        roles_to_scrape = shuffled_roles[:limit]
        
        print(f"Selected {len(roles_to_scrape)} random roles:")
        for i, role in enumerate(roles_to_scrape, 1):
            print(f"  {i}. {role}")
        print()
        
        # Queue each role for jobspy scraping
        print("📍 Queuing roles for jobspy scraping (Pakistan + Remote fallback)...")
        for role in roles_to_scrape:
            # Build job data for jobspy worker
            job_data = {
                "url": "jobspy",  # Special marker for jobspy scraping
                "source": "glassdoor",
                "scrape_id": scrape_id,
                "user_id": user_id,
                "filters": {
                    "search_term": role,
                    "location": "Pakistan",  # Always search Pakistan first
                    "results_wanted": 10,  # Get 10 jobs per role (change this to control jobs per role)
                    "country_indeed": "Pakistan",
                    "is_remote": False  # Will auto-fallback to remote if Pakistan jobs insufficient
                },
                "type": "jobspy_search"
            }
            
            if self.scraper_service.push_job_to_queue(job_data):
                queued_count += 1
                print(f"  ✓ Queued: {role} (5 jobs from Glassdoor)")
        
        print(f"\n{'='*60}")
        print(f"✓ Producer finished: {queued_count} roles queued")
        print(f"  Each role will fetch 5 jobs = {queued_count * 5} total jobs")
        print(f"{'='*60}\n")
        
        return queued_count


def main():
    """Test the producer"""
    producer = JobProducer()
    
    # Test with role-based scraping (filters are now ignored)
    test_filters = {}
    
    scrape_id = "test_scrape_001"
    user_id = "test_user"
    
    queued = producer.produce_jobs(scrape_id, user_id, test_filters, limit=5)
    print(f"\n✓ Test complete: {queued} jobs queued")


if __name__ == "__main__":
    main()
