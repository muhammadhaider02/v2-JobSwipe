"""
Script to insert scraped jobs into Supabase jobs table.
Maps scraped job metadata to the existing table schema.
Uses Supabase REST API directly (no heavy dependencies).
"""
import json
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests
from dotenv import load_dotenv

# Load environment variables from backend/.env.local
env_path = Path(__file__).parent.parent / ".env.local"
load_dotenv(dotenv_path=env_path)

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables")

# Supabase REST API endpoint
API_URL = f"{SUPABASE_URL}/rest/v1/jobs"
HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}


def safe_str(value: Any) -> str:
    """Safely convert value to string, handling NaN and None."""
    if value is None or (isinstance(value, float) and (value != value)):  # NaN check
        return ""
    return str(value)


def extract_experience_years(job_data: dict) -> Optional[int]:
    """Extract experience years from job data."""
    # Check experience_range field
    exp_range = job_data.get("experience_range")
    if exp_range:
        # Try to extract numbers like "2-5 years" or "3+ years"
        numbers = re.findall(r'\d+', str(exp_range))
        if numbers:
            return int(numbers[0])  # Return first number found
    
    # Check job_level field
    job_level = safe_str(job_data.get("job_level")).lower()
    if "intern" in job_level or "entry" in job_level:
        return 0
    elif "junior" in job_level:
        return 1
    elif "mid" in job_level or "ii" in job_level:
        return 3
    elif "senior" in job_level or "sr" in job_level or "iii" in job_level:
        return 5
    elif "lead" in job_level or "principal" in job_level:
        return 7
    elif "staff" in job_level or "architect" in job_level:
        return 8
    
    # Check title for hints
    title = safe_str(job_data.get("title")).lower()
    if any(word in title for word in ["intern", "internship", "trainee"]):
        return 0
    elif "junior" in title or "jr" in title:
        return 1
    elif "senior" in title or "sr" in title:
        return 5
    elif "lead" in title or "principal" in title:
        return 7
    
    return 2  # Default to 2 years if unknown


def extract_education_level(job_data: dict) -> str:
    """Extract education requirement from job data."""
    description = safe_str(job_data.get("description")).lower()
    title = safe_str(job_data.get("title")).lower()
    job_level = safe_str(job_data.get("job_level")).lower()
    
    # Check for PhD/Doctorate
    if any(keyword in description or keyword in title 
           for keyword in ["phd", "ph.d", "doctorate", "doctoral"]):
        return "PhD"
    
    # Check for Masters
    if any(keyword in description or keyword in title 
           for keyword in ["master", "masters", "msc", "m.sc", "mba"]):
        return "Masters"
    
    # Check for Bachelors
    if any(keyword in description or keyword in title 
           for keyword in ["bachelor", "bachelors", "bsc", "b.sc", "be", "b.e", "btech", "b.tech"]):
        return "Bachelors"
    
    # Infer from job level
    if "intern" in title or "intern" in job_level:
        return "Undergraduate"
    elif "senior" in title or "lead" in title or "principal" in title:
        return "Masters"
    
    return "Bachelors"  # Default


def extract_job_type(job_data: dict) -> str:
    """Extract job type (Full-time, Part-time, Contract, Internship)."""
    job_type = safe_str(job_data.get("job_type")).lower()
    title = safe_str(job_data.get("title")).lower()
    
    # Check explicit job_type field
    if "full" in job_type or "full-time" in job_type:
        return "Full-time"
    elif "part" in job_type or "part-time" in job_type:
        return "Part-time"
    elif "contract" in job_type or "contractor" in job_type:
        return "Contract"
    elif "intern" in job_type:
        return "Internship"
    
    # Infer from title
    if "intern" in title or "internship" in title:
        return "Internship"
    elif "contract" in title or "contractor" in title:
        return "Contract"
    elif "part-time" in title or "part time" in title:
        return "Part-time"
    
    return "Full-time"  # Default


def determine_location(job_data: dict) -> str:
    """Determine job location."""
    location = safe_str(job_data.get("location")).strip()
    is_remote = job_data.get("is_remote", False)
    work_from_home = safe_str(job_data.get("work_from_home_type"))
    
    if is_remote or "remote" in location.lower() or work_from_home:
        return "Remote"
    
    if not location:
        return "Remote"  # Default if empty
    
    # Extract city name if available
    # Format: "London, England, UK" -> "London"
    if "," in location:
        city = location.split(",")[0].strip()
        return city
    
    return location


def infer_industry(job_data: dict) -> str:
    """Infer industry from job data."""
    title = safe_str(job_data.get("title")).lower()
    company_industry = safe_str(job_data.get("company_industry")).lower()
    description = safe_str(job_data.get("description")).lower()
    
    # Use explicit company industry if available
    if company_industry:
        # Map to simplified categories
        if any(keyword in company_industry for keyword in ["tech", "software", "saas", "cloud"]):
            return "SaaS"
        elif any(keyword in company_industry for keyword in ["finance", "banking", "fintech"]):
            return "FinTech"
        elif any(keyword in company_industry for keyword in ["security", "cyber"]):
            return "Cybersecurity"
        elif any(keyword in company_industry for keyword in ["ai", "machine learning", "data"]):
            return "AI"
        return company_industry.title()
    
    # Infer from title and description
    combined_text = f"{title} {description}"
    
    if any(keyword in combined_text for keyword in ["cyber", "security", "infosec", "penetration"]):
        return "Cybersecurity"
    elif any(keyword in combined_text for keyword in ["data scientist", "machine learning", "ai", "deep learning", "ml engineer"]):
        return "AI"
    elif any(keyword in combined_text for keyword in ["fintech", "finance", "banking", "payment"]):
        return "FinTech"
    elif any(keyword in combined_text for keyword in ["saas", "software", "backend", "frontend", "full stack"]):
        return "SaaS"
    elif any(keyword in combined_text for keyword in ["healthcare", "health", "medical"]):
        return "Healthcare"
    elif any(keyword in combined_text for keyword in ["e-commerce", "ecommerce", "retail"]):
        return "E-Commerce"
    
    return "Technology"  # Default


def extract_skills(job_data: dict) -> List[str]:
    """Extract skills from job data."""
    # Check if skills are explicitly provided
    skills = job_data.get("skills")
    if skills and isinstance(skills, list):
        return skills
    
    # Try to infer from title and description
    title = safe_str(job_data.get("title")).lower()
    description = safe_str(job_data.get("description")).lower()
    combined_text = f"{title} {description}"
    
    # Common skill keywords
    skill_keywords = {
        # Programming Languages
        "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "ruby", "php",
        # Frameworks
        "react", "angular", "vue", "django", "flask", "fastapi", "spring", "node.js", "express",
        # Databases
        "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "dynamodb",
        # Cloud
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
        # Data Science
        "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "spark",
        # DevOps
        "ci/cd", "jenkins", "gitlab", "github actions", "ansible",
        # Security
        "penetration testing", "siem", "ids", "ips", "vulnerability", "firewall",
        # Other
        "git", "linux", "windows", "api", "rest", "graphql", "microservices", "agile"
    }
    
    found_skills = []
    for skill in skill_keywords:
        if skill in combined_text:
            found_skills.append(skill.title())
    
    return found_skills if found_skills else ["General Skills"]  # Default if none found


def map_scraped_job_to_schema(job_data: dict) -> Dict[str, Any]:
    """Map scraped job data to Supabase table schema."""
    return {
        "job_id": job_data.get("job_id") or job_data.get("id"),
        "job_title": job_data.get("title"),
        "job_description": job_data.get("description") or f"Position at {job_data.get('company')}. Visit the job URL for full details.",
        "skills_required": extract_skills(job_data),
        "experience_required": extract_experience_years(job_data),
        "education_required": extract_education_level(job_data),
        "job_type": extract_job_type(job_data),
        "location": determine_location(job_data),
        "industry": infer_industry(job_data),
    }


def check_job_exists(job_id: str) -> bool:
    """Check if a job already exists in Supabase."""
    try:
        response = requests.get(
            API_URL,
            headers=HEADERS,
            params={"job_id": f"eq.{job_id}", "select": "job_id"}
        )
        response.raise_for_status()
        return len(response.json()) > 0
    except Exception as e:
        print(f"  ⚠ Warning: Could not check if job exists: {e}")
        return False


def insert_job(job_data: Dict[str, Any]) -> bool:
    """Insert a job into Supabase. Returns True on success."""
    try:
        response = requests.post(
            API_URL,
            headers=HEADERS,
            json=job_data
        )
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409:
            # Duplicate key - job already exists
            return False
        raise


def insert_jobs_from_metadata(metadata_file: str, dry_run: bool = False):
    """
    Read metadata JSON and insert jobs into Supabase.
    
    Args:
        metadata_file: Path to the metadata JSON file
        dry_run: If True, only print what would be inserted without actually inserting
    """
    print(f"\n{'='*60}")
    print(f"📄 Processing: {Path(metadata_file).name}")
    print(f"{'='*60}\n")
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    jobs = data.get("jobs", [])
    print(f"📥 Found {len(jobs)} jobs\n")
    
    inserted_count = 0
    skipped_count = 0
    error_count = 0
    
    for idx, job in enumerate(jobs, 1):
        try:
            mapped_job = map_scraped_job_to_schema(job)
            
            print(f"\n[{idx}/{len(jobs)}] {mapped_job['job_title']} at {job.get('company')}")
            print(f"  └─ ID: {mapped_job['job_id']}")
            print(f"  └─ Location: {mapped_job['location']}")
            print(f"  └─ Type: {mapped_job['job_type']}")
            print(f"  └─ Industry: {mapped_job['industry']}")
            print(f"  └─ Experience: {mapped_job['experience_required']} years")
            print(f"  └─ Education: {mapped_job['education_required']}")
            print(f"  └─ Skills: {', '.join(mapped_job['skills_required'][:5])}{' ...' if len(mapped_job['skills_required']) > 5 else ''}")
            
            if dry_run:
                print(f"  ✓ [DRY RUN] Would insert this job")
                inserted_count += 1
            else:
                # Check if job already exists
                if check_job_exists(mapped_job["job_id"]):
                    print(f"  ⊘ Skipped (already exists)")
                    skipped_count += 1
                else:
                    success = insert_job(mapped_job)
                    if success:
                        print(f"  ✓ Inserted successfully")
                        inserted_count += 1
                    else:
                        print(f"  ⊘ Skipped (duplicate)")
                        skipped_count += 1
                    
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            error_count += 1
    
    print(f"\n{'='*60}")
    print(f"📊 Summary")
    print(f"{'='*60}")
    print(f"✓ Inserted: {inserted_count}")
    print(f"⊘ Skipped:  {skipped_count}")
    print(f"✗ Errors:   {error_count}")
    print(f"━━ Total:   {len(jobs)}")
    print(f"{'='*60}\n")


def process_all_metadata_files(base_dir: str, dry_run: bool = False):
    """Process all metadata JSON files in the raw_html directory."""
    metadata_dir = Path(base_dir)
    metadata_files = list(metadata_dir.glob("**/metadata/*.json"))
    
    if not metadata_files:
        print(f"❌ No metadata files found in {base_dir}")
        return
    
    print(f"\n🔍 Found {len(metadata_files)} metadata file(s)")
    print(f"{'='*60}\n")
    
    for metadata_file in metadata_files:
        try:
            insert_jobs_from_metadata(str(metadata_file), dry_run=dry_run)
        except Exception as e:
            print(f"❌ Failed to process {metadata_file.name}: {e}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Insert scraped jobs into Supabase")
    parser.add_argument(
        "--file",
        type=str,
        help="Path to a specific metadata JSON file"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=r"c:\Users\emaad\Downloads\v2-JobSwipe\backend\scraper\raw_html",
        help="Base directory containing metadata files (default: raw_html directory)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be inserted without actually inserting"
    )
    
    args = parser.parse_args()
    
    if args.file:
        # Process single file
        insert_jobs_from_metadata(args.file, dry_run=args.dry_run)
    else:
        # Process all metadata files in directory
        process_all_metadata_files(args.dir, dry_run=args.dry_run)
