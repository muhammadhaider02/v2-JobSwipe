"""
Script to enrich job metadata by scraping job descriptions from job URLs.
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_metadata(metadata_path: str) -> dict:
    """Load the metadata JSON file."""
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_metadata(metadata_path: str, data: dict):
    """Save the updated metadata JSON file."""
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_job_description(page, job_url: str, site: str) -> str:
    """
    Extract job description from the job page.
    
    Args:
        page: Playwright page object
        job_url: URL of the job posting
        site: Job site name (linkedin, indeed, etc.)
    
    Returns:
        Extracted job description text or None if failed
    """
    try:
        logger.info(f"Navigating to: {job_url}")
        
        # Navigate to the job URL with shorter timeout and less strict wait
        try:
            page.goto(job_url, wait_until='domcontentloaded', timeout=15000)
        except PlaywrightTimeoutError:
            # Try one more time with commit wait strategy
            page.goto(job_url, wait_until='commit', timeout=10000)
        
        # Wait a bit for dynamic content to load
        time.sleep(3)
        
        # Site-specific selectors
        selectors = {
            'linkedin': [
                '.description__text',
                '.show-more-less-html__markup',
                '.jobs-description__content',
                '#job-details',
                '.job-view-layout',
            ],
            'indeed': [
                '#jobDescriptionText',
                '.jobsearch-jobDescriptionText',
            ],
            'glassdoor': [
                '.JobDetails_jobDescription__uW_fK',
                '.desc',
                '[class*="jobDescriptionContent"]',
            ],
            'ziprecruiter': [
                '.job_description',
            ],
        }
        
        # Get selectors for the specific site, or use generic ones
        site_selectors = selectors.get(site, [
            '.job-description',
            '.description',
            '[class*="description"]',
            '[id*="description"]',
        ])
        
        description = None
        
        # Try each selector until one works
        for selector in site_selectors:
            try:
                # Wait for the selector with a shorter timeout
                page.wait_for_selector(selector, timeout=5000)
                description = page.inner_text(selector)
                if description and len(description.strip()) > 50:  # Minimum length check
                    logger.info(f"✓ Description extracted using selector: {selector}")
                    break
            except PlaywrightTimeoutError:
                continue
            except Exception as e:
                logger.debug(f"Failed with selector {selector}: {e}")
                continue
        
        if not description:
            # Fallback: try to get any text from the page body
            logger.warning(f"Could not find description with known selectors, trying body text")
            description = page.inner_text('body')
        
        return description.strip() if description else None
        
    except PlaywrightTimeoutError:
        logger.error(f"Timeout loading page: {job_url}")
        return None
    except Exception as e:
        logger.error(f"Error extracting description from {job_url}: {e}")
        return None


def enrich_metadata(metadata_path: str, headless: bool = True):
    """
    Enrich job metadata by scraping job descriptions.
    
    Args:
        metadata_path: Path to the metadata JSON file
        headless: Whether to run browser in headless mode
    """
    logger.info(f"Loading metadata from: {metadata_path}")
    metadata = load_metadata(metadata_path)
    
    total_jobs = len(metadata.get('jobs', []))
    logger.info(f"Found {total_jobs} jobs to enrich")
    
    enriched_count = 0
    failed_count = 0
    
    with sync_playwright() as p:
        # Launch browser
        logger.info("Launching browser...")
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        try:
            # Process each job
            for idx, job in enumerate(metadata.get('jobs', []), 1):
                job_url = job.get('job_url')
                job_title = job.get('title', 'Unknown')
                site = job.get('site', 'unknown')
                
                logger.info(f"\n[{idx}/{total_jobs}] Processing: {job_title}")
                
                if not job_url:
                    logger.warning(f"No job URL found for job: {job_title}")
                    failed_count += 1
                    continue
                
                # Skip if description already exists
                description_value = job.get('description')
                # Check if description is a valid string (not NaN or None)
                if description_value and isinstance(description_value, str) and len(description_value.strip()) > 50:
                    logger.info(f"Description already exists, skipping...")
                    enriched_count += 1
                    continue
                
                # Extract description
                description = extract_job_description(page, job_url, site)
                
                if description:
                    job['description'] = description
                    enriched_count += 1
                    logger.info(f"✓ Successfully extracted description ({len(description)} chars)")
                else:
                    failed_count += 1
                    logger.warning(f"✗ Failed to extract description")
                
                # Save progress after each job (in case of interruption)
                save_metadata(metadata_path, metadata)
                
                # Be nice to servers - add delay between requests
                time.sleep(2)
                
        finally:
            browser.close()
    
    # Final save
    save_metadata(metadata_path, metadata)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Enrichment Complete!")
    logger.info(f"Total jobs: {total_jobs}")
    logger.info(f"Successfully enriched: {enriched_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Updated file: {metadata_path}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    # Path to your metadata file
    metadata_file = r"c:\Users\emaad\Downloads\v2-JobSwipe\backend\scraper\raw_html\demo_user_test\metadata\test_scrape_1770050165_metadata.json"
    
    # Run enrichment (set headless=False to see the browser)
    enrich_metadata(metadata_file, headless=True)
