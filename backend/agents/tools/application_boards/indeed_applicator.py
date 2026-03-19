import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY")

# ---------------------------------------------------------------------------
# CapSolver helpers (ported from FlexVisitor.py, adapted for Playwright)
# ---------------------------------------------------------------------------

def solve_recaptcha_capsolver(website_url: str, site_key: str) -> str:
    """
    Submit a reCAPTCHA v2 task to CapSolver and poll until the token is ready.

    Mirrors the logic in FlexVisitor.py but is framework-agnostic — it only
    makes HTTP calls, so it works equally well with Selenium, Playwright, or
    PinchTab.

    Args:
        website_url: The page URL where the captcha appears.
        site_key:    The reCAPTCHA site key found on that page.

    Returns:
        The gRecaptchaResponse token string.

    Raises:
        RuntimeError: If CAPSOLVER_API_KEY is missing or the API returns an error.
        TimeoutError: If the captcha is not solved within ~90 seconds.
    """
    if not CAPSOLVER_API_KEY:
        raise RuntimeError("Missing CAPSOLVER_API_KEY in environment (.env)")

    # Step 1 — create task
    create_payload = {
        "clientKey": CAPSOLVER_API_KEY,
        "task": {
            "type": "ReCaptchaV2TaskProxyLess",
            "websiteURL": website_url,
            "websiteKey": site_key,
        },
    }
    r = requests.post("https://api.capsolver.com/createTask", json=create_payload).json()
    if r.get("errorId", 1) != 0:
        raise RuntimeError(f"CapSolver createTask error: {r}")
    task_id = r["taskId"]

    # Step 2 — poll until ready (up to ~90 s)
    for _ in range(30):
        time.sleep(3)
        res = requests.post(
            "https://api.capsolver.com/getTaskResult",
            json={"clientKey": CAPSOLVER_API_KEY, "taskId": task_id},
        ).json()
        if res.get("status") == "ready":
            return res["solution"]["gRecaptchaResponse"]

    raise TimeoutError("CapSolver: captcha solve timed out after 90 seconds")


def detect_indeed_site_key(page) -> str:
    """
    Try to read the reCAPTCHA site key directly from the page.
    Falls back to Indeed's known default key if it cannot be found.

    Works with any Playwright Page object (sync or async-wrapped).
    """
    # Indeed's known reCAPTCHA v2 site key (update here if Indeed changes it)
    INDEED_DEFAULT_SITE_KEY = "6LdL8p0UAAAAAKTMBHHTdvFKJB1zHDVMQCpXoBAX"

    try:
        recaptcha_frame = page.query_selector('iframe[src*="recaptcha"]')
        if recaptcha_frame:
            src = recaptcha_frame.get_attribute("src") or ""
            if "k=" in src:
                detected = src.split("k=")[1].split("&")[0]
                if detected:
                    print(f"[Captcha] Detected site key from iframe: {detected}")
                    return detected
    except Exception:
        pass

    print(f"[Captcha] Could not detect site key; using default: {INDEED_DEFAULT_SITE_KEY}")
    return INDEED_DEFAULT_SITE_KEY


def handle_login_captcha(page, login_url: str, site_key: str = None) -> bool:
    """
    Detect a reCAPTCHA on the current page and solve it automatically via
    CapSolver, then inject the token so the form can be submitted.

    This is the PinchTab/Playwright equivalent of the captcha logic in
    FlexVisitor.py (which used Selenium).  The user has already filled in
    their credentials manually — this function only handles the captcha step.

    Args:
        page:       A Playwright Page object (from PinchTab's BrowserManager).
        login_url:  The URL of the login page (needed by CapSolver).
        site_key:   Optional reCAPTCHA site key. Auto-detected when omitted.

    Returns:
        True  — captcha solved and token injected (or no captcha present).
        False — captcha handling failed.
    """
    try:
        # Auto-detect site key when not supplied
        if not site_key:
            site_key = detect_indeed_site_key(page)

        # Check if a captcha is actually present before bothering the API
        captcha_frame = page.query_selector('iframe[src*="recaptcha"]')
        if not captcha_frame:
            print("[Captcha] No reCAPTCHA iframe found on the page — skipping.")
            return True

        print(f"[Captcha] reCAPTCHA detected. Requesting CapSolver solution…")
        token = solve_recaptcha_capsolver(login_url, site_key)
        print("[Captcha] Token received. Injecting into page…")

        # Inject token — identical approach to FlexVisitor.py but using
        # Playwright's page.evaluate() instead of Selenium's execute_script()
        page.evaluate(
            """(token) => {
                // Primary target
                let el = document.getElementById('g-recaptcha-response');
                if (el) {
                    el.style.display = 'block';
                    el.value = token;
                } else {
                    // Fallback: scan all textareas for a recaptcha-related name
                    for (let ta of document.getElementsByTagName('textarea')) {
                        if (ta.name && ta.name.toLowerCase().includes('recaptcha')) {
                            ta.style.display = 'block';
                            ta.value = token;
                        }
                    }
                }

                // Fire the grecaptcha callback if the widget exposes one
                try {
                    if (window.grecaptcha && typeof window.grecaptcha.execute === 'function') {
                        window.grecaptcha.execute();
                    }
                } catch (_) {}
            }""",
            token,
        )

        time.sleep(1.5)  # give the page a moment to register the token
        print("[Captcha] Token injected successfully.")
        return True

    except Exception as exc:
        print(f"[Captcha] Error handling captcha: {exc}")
        return False


# ---------------------------------------------------------------------------
# Indeed applicator
# ---------------------------------------------------------------------------
"""
Indeed Applicator: Indeed Easy Apply form automation.

Handles Indeed-specific form filling with support for:
- Easy Apply button detection
- Multi-step forms
- Resume upload
- Standard contact fields
"""

import random
from typing import Dict, Any
from pathlib import Path

try:
    from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
except ImportError:
    Page = None
    PlaywrightTimeout = Exception

from agents.tools.application_boards.base_applicator import BaseApplicator


class IndeedApplicator(BaseApplicator):
    def __init__(self, page):
        self.page = page
        self.platform_name = "Indeed"
        self.login_url = "https://secure.indeed.com/account/login"

    def login(self, wait_for_manual_input: bool = True) -> Dict[str, Any]:
        """
        Navigate to the Indeed login page and — once the user has entered their
        credentials manually — solve the captcha automatically via CapSolver.

        The user is never asked to provide credentials through the script; they
        type them directly into the browser.

        Args:
            wait_for_manual_input: When True (default), pauses and prompts the
                user to enter credentials before the captcha is solved.

        Returns:
            {
                "success": bool,
                "message": str,
                "error": str | None
            }
        """
        try:
            print(f"[Login] Navigating to Indeed login page: {self.login_url}")
            self.page.goto(self.login_url, wait_until="domcontentloaded")
            time.sleep(2)

            if wait_for_manual_input:
                print()
                print("=" * 60)
                print("MANUAL CREDENTIAL INPUT REQUIRED")
                print("=" * 60)
                print("Please enter your Indeed credentials in the browser window:")
                print("  1. Enter your email / username")
                print("  2. Enter your password")
                print("  3. Do NOT click Sign In yet")
                print("  4. Do NOT solve the captcha manually")
                print("  5. Press Enter here when done — the captcha will be")
                print("     solved automatically before Sign In is clicked.")
                print("=" * 60)
                input("\nPress Enter after filling in credentials…")

            # Solve captcha (site key auto-detected from the live page)
            captcha_solved = handle_login_captcha(self.page, self.login_url)
            if not captcha_solved:
                return {
                    "success": False,
                    "message": "Failed to solve captcha",
                    "error": "Captcha solving failed",
                }

            # Click Sign In
            print("[Login] Clicking Sign In button…")
            sign_in_selectors = [
                'button[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Continue")',
                "#login-submit-button",
                'button[data-tn-element="auth-page-sign-in-password-form-submit-button"]',
            ]
            sign_in_clicked = False
            for selector in sign_in_selectors:
                try:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        sign_in_clicked = True
                        print(f"[Login] Clicked: {selector}")
                        break
                except Exception:
                    continue

            if not sign_in_clicked:
                return {
                    "success": False,
                    "message": "Could not find sign-in button",
                    "error": "Sign-in button not found",
                }

            print("[Login] Waiting for post-login navigation…")
            time.sleep(3)

            current_url = self.page.url
            if "login" in current_url.lower():
                return {
                    "success": False,
                    "message": "Login may have failed — still on login page",
                    "error": "Login verification failed",
                }

            return {
                "success": True,
                "message": "Login successful!",
                "error": None,
            }

        except Exception as exc:
            return {
                "success": False,
                "message": f"Login error: {exc}",
                "error": str(exc),
            }

    def click_apply_button(self, page) -> bool:
        """Find and click the Indeed Easy Apply button. Returns True on success."""
        try:
            selectors = [
                "button.ia-IndeedApplyButton",
                'button[aria-label*="Apply"]',
                'button:has-text("Apply Now")',
                'button:has-text("Apply easily")',
            ]
            for selector in selectors:
                btn = page.query_selector(selector)
                if btn:
                    btn.click()
                    time.sleep(random.uniform(1.0, 2.0))
                    return True
        except Exception:
            pass
        return False

    def fill_form(
        self,
        page,
        materials: Dict[str, Any],
        user_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fill Indeed application form fields. Returns fields_filled, warnings, error."""
        fields_filled = {}
        warnings = []
        error = None
        try:
            contact_fields = {
                'input[name="applicant.name"]': user_profile.get("name", ""),
                'input[name="applicant.email"]': user_profile.get("email", ""),
                'input[name="applicant.phoneNumber"]': user_profile.get("phone", ""),
                'input[name="applicant.location"]': user_profile.get("location", ""),
            }
            for selector, value in contact_fields.items():
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.fill(value)
                        fields_filled[selector] = True
                    else:
                        fields_filled[selector] = False
                        warnings.append(f"Field not found: {selector}")
                except Exception as exc:
                    fields_filled[selector] = False
                    warnings.append(f"Error filling {selector}: {exc}")

            # Cover letter
            cover_letter = materials.get("cover_letter", "")
            try:
                cl_el = page.query_selector('textarea[name*="cover"]')
                if cl_el:
                    cl_el.fill(cover_letter)
                    fields_filled["cover_letter"] = True
                else:
                    fields_filled["cover_letter"] = False
            except Exception as exc:
                fields_filled["cover_letter"] = False
                warnings.append(f"Error filling cover letter: {exc}")

            # Resume upload
            try:
                resume_input = page.query_selector('input[type="file"][name*="resume"]')
                if resume_input and "resume_path" in materials:
                    resume_input.set_input_files(materials["resume_path"])
                    fields_filled["resume"] = True
                else:
                    fields_filled["resume"] = False
            except Exception as exc:
                fields_filled["resume"] = False
                warnings.append(f"Error uploading resume: {exc}")

        except Exception as exc:
            error = str(exc)

        return {"fields_filled": fields_filled, "warnings": warnings, "error": error}

    def detect_multi_step(self, page) -> bool:
        """Return True if the application form has multiple steps."""
        try:
            if page.query_selector('button:has-text("Next")'):
                return True
            if page.query_selector('button:has-text("Continue")'):
                return True
        except Exception:
            pass
        return False