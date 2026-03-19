"""
Test script for Indeed login with automatic captcha solving.

Prerequisites:
1. Set CAPSOLVER_API_KEY in your .env file
2. Make sure you have a CapSolver account with credits

Usage:
    python test_indeed_login.py
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from playwright.sync_api import sync_playwright
from agents.tools.application_boards.indeed_applicator import IndeedApplicator


def test_indeed_login():
    """Test Indeed login with manual credential input and automatic captcha solving."""

    print("=" * 70)
    print("INDEED LOGIN TEST - Automatic Captcha Solving")
    print("=" * 70)
    print("\nThis script will:")
    print("  1. Open Indeed login page in browser")
    print("  2. Wait for you to enter your credentials manually")
    print("  3. Automatically solve the captcha using CapSolver API")
    print("  4. Click Sign In button")
    print("\n" + "=" * 70 + "\n")

    with sync_playwright() as p:
        # Launch browser in non-headless mode so user can enter credentials
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = context.new_page()

        try:
            # Create Indeed applicator instance
            applicator = IndeedApplicator(page)

            # Perform login (with manual credential input and automatic captcha solving)
            result = applicator.login(wait_for_manual_input=True)

            print("\n" + "=" * 70)
            print("LOGIN RESULT")
            print("=" * 70)
            print(f"Success: {result['success']}")
            print(f"Message: {result['message']}")
            if result['error']:
                print(f"Error: {result['error']}")
            print("=" * 70 + "\n")

            if result['success']:
                print("✓ Login successful! Browser will stay open for 30 seconds...")
                print("  You can now navigate to job pages and test applications.")

                # Keep browser open for a while to verify
                import time
                time.sleep(30)
            else:
                print("✗ Login failed. Please check the error message above.")
                input("Press Enter to close browser...")

        except Exception as exc:
            print(f"\n✗ Error during test: {exc}")
            import traceback
            traceback.print_exc()
            input("Press Enter to close browser...")

        finally:
            browser.close()


if __name__ == "__main__":
    # Check if CAPSOLVER_API_KEY is set
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("CAPSOLVER_API_KEY")
    if not api_key:
        print("\n" + "=" * 70)
        print("ERROR: CAPSOLVER_API_KEY not found in .env file")
        print("=" * 70)
        print("\nPlease:")
        print("  1. Get an API key from https://www.capsolver.com/")
        print("  2. Add it to your .env file:")
        print("     CAPSOLVER_API_KEY=your_api_key_here")
        print("\n" + "=" * 70 + "\n")
        sys.exit(1)

    test_indeed_login()
