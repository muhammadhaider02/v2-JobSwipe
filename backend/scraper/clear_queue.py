"""
Clear Redis queue and scraped URLs set.
Useful for testing fresh scrapes.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from services.job_scraper_service import get_scraper_service

def main():
    scraper_service = get_scraper_service()
    
    print("Clearing Redis queues...")
    scraper_service.clear_queue()
    scraper_service.clear_scraped_urls()
    print("✓ Done!")

if __name__ == "__main__":
    main()
