"""
JobScraperSpider: Multi-session job scraper using Scrapling.

Coordinates scraping across LinkedIn, Rozee, Indeed, and Mustakbil with:
- StealthyFetcher for anti-bot bypass
- Checkpoint-based resume
- Concurrent requests with rate limiting
"""

from typing import List, Dict, Optional
from scrapling import StealthyFetcher
from config.settings import get_settings
from agents.state import JobData
from .job_boards import (
    LinkedInParser,
    RozeeParser,
    IndeedParser,
    MustakbilParser,
    BaseJobParser
)
import time


class JobScraperSpider:
    """
    Multi-board job scraper with Scrapling's adaptive parsing.
    
    Features:
    - StealthyFetcher with Cloudflare bypass
    - Session management for cookies/headers
    - Checkpoint-based resume (TODO: implement with Redis)
    - Concurrent requests with configurable delays
    """
    
    def __init__(self):
        """Initialize spider with parsers and settings."""
        self.settings = get_settings()
        
        # Initialize parsers
        self.parsers: Dict[str, BaseJobParser] = {
            "linkedin": LinkedInParser(),
            "rozee": RozeeParser(),
            "indeed": IndeedParser(),
            "mustakbil": MustakbilParser()
        }
        
        # StealthyFetcher options (passed as kwargs)
        self.fetcher_options = {
            "auto_match": True,  # Enable adaptive parsing
            "stealth": True,  # Enable stealth mode
        }
        
        print("✅ JobScraperSpider initialized with 4 parsers")
    
    def scrape_board(
        self,
        board: str,
        query: str,
        location: str = "",
        max_pages: int = 3,
        max_jobs: int = None
    ) -> List[JobData]:
        """
        Scrape single job board.
        
        Args:
            board: Board name ("linkedin", "rozee", "indeed", "mustakbil")
            query: Search query
            location: Location filter
            max_pages: Maximum pages to scrape
            max_jobs: Maximum jobs to scrape (None = unlimited)
            
        Returns:
            List of JobData dictionaries
        """
        if board not in self.parsers:
            print(f"❌ Unknown board: {board}")
            return []
        
        parser = self.parsers[board]
        jobs = []
        
        print(f"\n🔍 Scraping {board.upper()} for '{query}' in '{location}'...")
        
        for page in range(1, max_pages + 1):
            try:
                # Build search URL
                search_url = parser.build_search_url(query, location, page)
                print(f"   Page {page}: {search_url}")
                
                # Fetch search results
                listing_response = StealthyFetcher.fetch(
                    search_url,
                    headless=True,
                    network_idle=True
                )
                
                if not listing_response:
                    print(f"   ⚠️  Failed to fetch page {page}")
                    continue
                    
                # Extract job URLs
                job_urls = parser.parse_listing(listing_response)
                
                if not job_urls:
                    print(f"   ⚠️  No jobs found on page {page}")
                    break  # No more results
                
                # Limit job URLs if max_jobs specified
                if max_jobs:
                    remaining_slots = max_jobs - len(jobs)
                    if remaining_slots <= 0:
                        break
                    job_urls = job_urls[:remaining_slots]
                
                # Scrape each job
                for i, job_url in enumerate(job_urls, 1):
                    try:
                        print(f"   Job {i}/{len(job_urls)}: {job_url}")
                        
                        # Fetch job page
                        job_response = StealthyFetcher.fetch(
                            job_url,
                            headless=True,
                            network_idle=True
                        )
                        
                        if not job_response:
                            print(f"      ⚠️  Failed to fetch job")
                            continue
                        
                        # Parse job
                        job_data = parser.parse_job(job_response)
                        
                        if job_data:
                            jobs.append(job_data)
                            print(f"      ✅ {job_data['title']} at {job_data['company']}")
                        else:
                            print(f"      ⚠️  Failed to parse job")
                        
                        # Rate limiting delay
                        time.sleep(self.settings.job_scraping_download_delay)
                        
                        # Break if we've reached max_jobs
                        if max_jobs and len(jobs) >= max_jobs:
                            print(f"   ℹ️  Reached max_jobs limit ({max_jobs})")
                            break
                    
                    except Exception as e:
                        print(f"      ❌ Job scrape error: {e}")
                        continue
                
                # Break if we've reached max_jobs
                if max_jobs and len(jobs) >= max_jobs:
                    break
                
                # Delay between pages
                time.sleep(self.settings.job_scraping_download_delay * 2)
            
            except Exception as e:
                print(f"   ❌ Page {page} error: {e}")
                continue
        
        print(f"✅ {board.upper()}: Scraped {len(jobs)} jobs\n")
        return jobs
    
    def scrape_all_boards(
        self,
        query: str,
        location: str = "Pakistan",
        boards: Optional[List[str]] = None,
        max_pages_per_board: int = 2,
        max_jobs_per_board: int = None
    ) -> List[JobData]:
        """
        Scrape multiple job boards.
        
        Args:
            query: Search query
            location: Location filter
            boards: List of boards to scrape (None = all)
            max_pages_per_board: Max pages per board
            max_jobs_per_board: Max jobs to scrape per board (None = unlimited)
            
        Returns:
            Combined list of jobs from all boards
        """
        if boards is None:
            boards = ["linkedin", "rozee", "indeed", "mustakbil"]
        
        all_jobs = []
        
        print(f"\n{'='*60}")
        print(f"Starting multi-board scraping:")
        print(f"  Query: {query}")
        print(f"  Location: {location}")
        print(f"  Boards: {', '.join(boards)}")
        print(f"  Max pages per board: {max_pages_per_board}")
        if max_jobs_per_board:
            print(f"  Max jobs per board: {max_jobs_per_board}")
        print(f"{'='*60}\n")
        
        for board in boards:
            try:
                jobs = self.scrape_board(
                    board=board,
                    query=query,
                    location=location,
                    max_pages=max_pages_per_board,
                    max_jobs=max_jobs_per_board
                )
                all_jobs.extend(jobs)
            
            except Exception as e:
                print(f"❌ Board {board} failed: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"✅ Total jobs scraped: {len(all_jobs)}")
        print(f"{'='*60}\n")
        
        return all_jobs
    
    def scrape_specific_url(self, url: str, board: str) -> Optional[JobData]:
        """
        Scrape specific job URL.
        
        Args:
            url: Job posting URL
            board: Board name
            
        Returns:
            JobData or None
        """
        if board not in self.parsers:
            print(f"❌ Unknown board: {board}")
            return None
        
        parser = self.parsers[board]
        
        try:
            response = StealthyFetcher.fetch(
                url,
                headless=True,
                network_idle=True
            )
            
            if not response:
                print(f"❌ Failed to fetch: {url}")
                return None
            
            job_data = parser.parse_job(response)
            
            if job_data:
                print(f"✅ Scraped: {job_data['title']} at {job_data['company']}")
                return job_data
            else:
                print(f"⚠️  Failed to parse: {url}")
                return None
        
        except Exception as e:
            print(f"❌ Scrape error: {e}")
            return None


# Global spider instance
_spider: Optional[JobScraperSpider] = None


def get_spider() -> JobScraperSpider:
    """
    Get or create global spider instance.
    
    Returns:
        JobScraperSpider instance
    """
    global _spider
    if _spider is None:
        _spider = JobScraperSpider()
    return _spider
