"""
Campaign Manager Integration Test

Tests the complete application preparation workflow:
1. Fetch test job from database
2. Prepare tailored materials (resume + cover letter)
3. (Optional) Test form filling with Indeed job

Usage:
    python test_campaign.py --mode materials  # Test material preparation only
    python test_campaign.py --mode fill --url <job_url>  # Test form filling
    python test_campaign.py --mode experience  # Test highlights-array experience optimization path
    python test_campaign.py --full  # Test complete workflow
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging for detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Load environment variables from .env.local
load_dotenv('.env.local')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.tools.material_prep import MaterialPreparationTool
from agents.tools.browser_tool import BrowserTool
from services.supabase_service import get_supabase_service
from utils.job_analyzer import JobAnalyzer
from services.resume_optimization_service import ResumeOptimizationService


# Test configuration
TEST_USER_ID = "d28190b3-e0b4-4af9-97a6-dc2a686d26e2" 
TEST_JOB_ID = None  # Will be fetched from database


def print_header(text: str):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def test_material_preparation():
    """Test material preparation workflow."""
    print_header("TEST: Material Preparation")
    
    supabase = get_supabase_service()
    
    # Step 1: Fetch test user profile
    print("\n📋 Step 1: Fetching test user profile...")
    user_profile = supabase.get_user_profile(TEST_USER_ID)
    
    if not user_profile:
        print(f"❌ Test user not found: {TEST_USER_ID}")
        print("💡 Please update TEST_USER_ID in test_campaign.py")
        return False
    
    print(f"✅ Found user: {user_profile.get('name', 'Unknown')}")
    
    # Step 2: Fetch a test job (any job from database)
    print("\n📋 Step 2: Fetching test job...")
    response = supabase.client.table("jobs").select("*").limit(1).execute()
    
    if not response.data or len(response.data) == 0:
        print("❌ No jobs found in database")
        print("💡 Run test_pipeline.py first to scrape jobs")
        return False
    
    test_job = response.data[0]
    job_id = test_job.get('job_id', 'N/A')
    print(f"✅ Found test job: {test_job['job_title']} at {test_job.get('company', 'Unknown Company')}")
    print(f"   Job ID: {job_id}")
    
    # Step 3: Analyze job
    print("\n📋 Step 3: Analyzing job context...")
    analyzer = JobAnalyzer()
    job_analysis = analyzer.analyze_job(test_job)
    
    print(f"   Company: {job_analysis['company_name']}")
    print(f"   Seniority: {job_analysis['seniority_level']}")
    print(f"   Critical Skills: {', '.join(job_analysis['critical_skills'][:5])}")
    print(f"   Culture: {list(job_analysis['culture_signals'].keys())}")
    
    # Step 4: Prepare materials
    print("\n📋 Step 4: Preparing application materials...")
    prep_tool = MaterialPreparationTool()
    
    result = prep_tool.prepare_materials(
        user_id=TEST_USER_ID,
        job_data=test_job,
        user_profile=user_profile
    )
    
    if result.get("error"):
        print(f"❌ Material preparation failed: {result['error']}")
        return False
    
    # Display results
    metadata = result['metadata']
    print(f"\n✅ MATERIALS PREPARED SUCCESSFULLY")
    print(f"\n📊 Optimization Metrics:")
    print(f"   Keywords Matched: {metadata['keywords_matched']}/{metadata['keywords_total']}")
    print(f"   Overall Confidence: {metadata['overall_confidence']:.1%}")
    print(f"   Template Used: {metadata['template_used']}")
    
    optimized_resume = result['optimized_resume']
    print(f"\n📄 Resume Summary:")
    print(f"   Summary: {optimized_resume.get('summary', 'N/A')[:100]}...")
    print(f"   Skills: {len(optimized_resume.get('skills', []))} skills")
    print(f"   Experience: {len(optimized_resume.get('experience', []))} positions")
    
    cover_letter = result['cover_letter']
    print(f"\n✉️  Cover Letter Preview:")
    print(f"   Length: {len(cover_letter)} characters")
    print(f"   First 200 chars: {cover_letter[:200]}...")
    
    return test_job


def test_form_filling(job_url: str = None, test_job: dict = None):
    """Test browser automation form filling."""
    print_header("TEST: Form Filling (Indeed)")
    
    if not job_url and not test_job:
        print("❌ No job URL or test_job provided")
        return False
    
    supabase = get_supabase_service()
    
    # Fetch user profile
    print("\n📋 Step 1: Fetching user profile...")
    user_profile = supabase.get_user_profile(TEST_USER_ID)
    
    if not user_profile:
        print(f"❌ Test user not found: {TEST_USER_ID}")
        return False
    
    print(f"✅ User: {user_profile.get('name', 'Unknown')}")
    
    # Prepare materials (reuse from previous test or prepare new)
    print("\n📋 Step 2: Preparing materials...")
    if test_job:
        prep_tool = MaterialPreparationTool()
        materials_result = prep_tool.prepare_materials(
            user_id=TEST_USER_ID,
            job_data=test_job,
            user_profile=user_profile
        )
        
        if materials_result.get("error"):
            print(f"❌ Material preparation failed: {materials_result['error']}")
            return False
        
        materials = {
            "optimized_resume": materials_result["optimized_resume"],
            "cover_letter": materials_result["cover_letter"]
        }
        job_url = test_job.get("job_url")
    else:
        # Use dummy materials for URL-only testing
        materials = {
            "optimized_resume": user_profile.get("resume_json", {}),
            "cover_letter": "Test cover letter"
        }
    
    print(f"✅ Materials ready")
    
    # Initialize browser tool
    print("\n📋 Step 3: Initializing browser automation...")
    print("⚠️  Browser will open in visible mode for debugging")
    browser = BrowserTool(headless=False)
    
    # Fill application
    print(f"\n📋 Step 4: Filling application form...")
    print(f"   URL: {job_url}")
    
    result = browser.fill_application(
        job_url=job_url,
        job_board="indeed",
        materials=materials,
        user_profile=user_profile
    )
    
    # Display results
    if result.get("error"):
        print(f"\n❌ FORM FILLING FAILED")
        print(f"   Error: {result['error']}")
        
        if result.get("fallback_required"):
            print(f"\n💡 MANUAL FALLBACK REQUIRED")
            print(f"   Reason: CAPTCHA or login detected")
            print(f"   Action: Please apply manually at {job_url}")
        
        if result.get("screenshot_path"):
            print(f"\n📸 Error screenshot saved: {result['screenshot_path']}")
        
        return False
    
    print(f"\n✅ FORM FILLED SUCCESSFULLY")
    print(f"\n📊 Fields Filled:")
    for field, filled in result.get("fields_filled", {}).items():
        status = "✅" if filled else "❌"
        print(f"   {status} {field.capitalize()}")
    
    print(f"\n📸 Screenshot saved: {result.get('screenshot_path')}")
    print(f"\n⏸️  PAUSED FOR REVIEW")
    print(f"   Please review the screenshot before submission")
    print(f"   In production, user would approve/reject via frontend")
    
    return True


def test_experience_highlights_path():
    """Regression test: experience entries with highlights[] should be optimized, not skipped."""
    print_header("TEST: Experience Highlights Path")

    class MockHFService:
        def optimize_experience_bullets(self, original_bullets, job_description, optimization_rules, job_keywords):
            return {
                "optimized_bullets": [
                    {
                        "original": b,
                        "optimized": f"Optimized: {b}",
                        "reasoning": "mock rewrite"
                    }
                    for b in original_bullets
                ],
                "validation": {"passed": True, "warnings": []}
            }

    # Construct service without full __init__ to avoid external model/API dependencies.
    service = object.__new__(ResumeOptimizationService)
    service.hf_service = MockHFService()
    service.retrieve_optimization_rules = lambda *args, **kwargs: []

    experience = [
        {
            "role": "ML Engineer",
            "company": "Acme AI",
            "highlights": [
                "Built inference API for vision model",
                "Reduced model latency by 20%"
            ]
        }
    ]

    result = service._optimize_experience_section(
        experience_list=experience,
        job_description="Looking for backend engineer with ML deployment experience",
        role_tags=["General"],
        jd_keywords=["Python", "Backend", "ML"]
    )

    optimized = result.get("optimized_experience", [])
    if not optimized:
        print("❌ No optimized experience returned")
        return False

    updated_highlights = optimized[0].get("highlights", [])
    if not updated_highlights:
        print("❌ Highlights missing after optimization")
        return False

    if not all(str(item).startswith("Optimized: ") for item in updated_highlights):
        print("❌ Highlights were not rewritten (possible silent bypass)")
        print(f"   Returned highlights: {updated_highlights}")
        return False

    print("✅ Highlights-array experience was optimized (no silent bypass)")
    print(f"   Updated highlights: {updated_highlights}")
    return True


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Campaign Manager Integration Tests")
    parser.add_argument(
        "--mode",
        choices=["materials", "fill", "experience", "full"],
        default="materials",
        help="Test mode: materials (default), fill, experience, or full"
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Job URL for form filling test (required for --mode fill)"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="Test user UUID (overrides TEST_USER_ID)"
    )
    
    args = parser.parse_args()
    
    # Override TEST_USER_ID if provided
    if args.user_id:
        global TEST_USER_ID
        TEST_USER_ID = args.user_id
    
    print_header("CAMPAIGN MANAGER INTEGRATION TESTS")
    print(f"Mode: {args.mode}")
    print(f"Test User: {TEST_USER_ID}")
    
    # Check if Playwright is installed
    try:
        from playwright.sync_api import sync_playwright
        print("✅ Playwright installed")
    except ImportError:
        if args.mode in ["fill", "full"]:
            print("❌ Playwright not installed")
            print("💡 Run: pip install playwright && playwright install")
            return
        else:
            print("⚠️  Playwright not installed (not needed for materials test)")
    
    # Run tests based on mode
    if args.mode == "materials":
        test_job = test_material_preparation()
        if test_job:
            print("\n" + "=" * 70)
            print("✅ MATERIAL PREPARATION TEST PASSED")
            print("=" * 70)
    
    elif args.mode == "fill":
        if not args.url:
            print("❌ --url required for fill mode")
            print("💡 Example: python test_campaign.py --mode fill --url https://indeed.com/job/xyz")
            return
        
        success = test_form_filling(job_url=args.url)
        if success:
            print("\n" + "=" * 70)
            print("✅ FORM FILLING TEST PASSED")
            print("=" * 70)

    elif args.mode == "experience":
        success = test_experience_highlights_path()
        if success:
            print("\n" + "=" * 70)
            print("✅ EXPERIENCE HIGHLIGHTS TEST PASSED")
            print("=" * 70)
    
    elif args.mode == "full":
        # Run both tests
        test_job = test_material_preparation()
        if test_job:
            print("\n⏸️  Press Enter to continue to form filling test...")
            input()
            success = test_form_filling(test_job=test_job)
            if success:
                print("\n" + "=" * 70)
                print("✅ ALL TESTS PASSED")
                print("=" * 70)


if __name__ == "__main__":
    main()
