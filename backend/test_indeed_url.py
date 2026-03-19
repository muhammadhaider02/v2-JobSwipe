"""
Standalone test script for PinchTab-based Indeed form filling.

Usage examples:
  python test_indeed_url.py --url "https://pk.indeed.com/viewjob?jk=..."
  python test_indeed_url.py --url "https://pk.indeed.com/viewjob?jk=..." --headless
  python test_indeed_url.py --url "https://pk.indeed.com/viewjob?jk=..." --user-id <uuid>

This script tests the current v1 behavior:
- Navigates with PinchTab
- Attempts to fill common fields
- Captures screenshot evidence for HITL review
- Does not submit the application
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Ensure backend imports resolve when running script directly.
sys.path.insert(0, str(Path(__file__).parent))

from agents.tools.browser_manager import BrowserManager
from agents.tools.browser_tool import BrowserTool
from config.settings import reload_settings
from services.pinchtab_service import PinchTabError
from services.supabase_service import get_supabase_service


INDEED_LOGIN_URL = (
    "https://secure.indeed.com/auth?hl=en_PK&co=PK&continue="
    "https%3A%2F%2Fpk.indeed.com%2F%3Fr%3Dus%26from%3Dgnav-util-homepage"
    "&tmpl=desktop&from=gnav-util-homepage&jsContinue="
    "https%3A%2F%2Fonboarding.indeed.com%2Fonboarding%3Fhl%3Den_PK%26co%3DPK%26from%3Dgnav-homepage"
    "&empContinue=https%3A%2F%2Faccount.indeed.com%2Fmyaccess"
)


def _header(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72)


def _build_default_profile(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "name": args.name,
        "email": args.email,
        "phone": args.phone,
        "location": args.location,
    }


def _load_profile_from_supabase(user_id: str) -> Dict[str, Any]:
    supabase = get_supabase_service()
    profile = supabase.get_user_profile(user_id)
    if not profile:
        raise ValueError(f"User profile not found for user_id={user_id}")
    return {
        "name": profile.get("name") or "",
        "email": profile.get("email") or "",
        "phone": profile.get("phone") or "",
        "location": profile.get("location") or "",
    }


def _build_materials(args: argparse.Namespace) -> Dict[str, Any]:
    cover_letter = args.cover_letter
    if args.cover_letter_file:
        cover_letter = Path(args.cover_letter_file).read_text(encoding="utf-8")

    return {
        "cover_letter": cover_letter,
        "optimized_resume": {},
    }


def _apply_runtime_overrides(args: argparse.Namespace) -> None:
    """Apply runtime environment overrides before settings are loaded."""
    applied: Dict[str, str] = {}

    if args.disable_proxy_rotation:
        os.environ["PINCHTAB_PROXY_ROTATION_ENABLED"] = "false"
        os.environ["PINCHTAB_ROTATE_IP_PER_APPLY"] = "false"
        applied["PINCHTAB_PROXY_ROTATION_ENABLED"] = "false"
        applied["PINCHTAB_ROTATE_IP_PER_APPLY"] = "false"

    profile_prefix = args.profile_prefix
    if args.fresh_profile and not profile_prefix:
        profile_prefix = f"jobswipe-fresh-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    if profile_prefix:
        os.environ["PINCHTAB_PROFILE_PREFIX"] = profile_prefix
        applied["PINCHTAB_PROFILE_PREFIX"] = profile_prefix

    # Ensure all downstream code sees updated values from this process env.
    reload_settings()

    if applied:
        print("Runtime overrides applied:")
        for key, value in applied.items():
            print(f"  {key}={value}")


def _derive_login_url(job_url: str, board: str) -> str:
    """Derive the correct login URL for a board, respecting the job URL domain.

    For international Indeed URLs (e.g. pk.indeed.com) the login page lives on
    the same subdomain.  Falling back to secure.indeed.com would set cookies on
    the wrong domain and the session wouldn't carry over.
    """
    if board == "indeed":
        if job_url:
            parsed = urlparse(job_url)
            netloc = parsed.netloc.lower()
            if "indeed." in netloc:
                return f"https://{parsed.netloc}/account/login"
        return INDEED_LOGIN_URL
    _defaults = {
        "linkedin": "https://www.linkedin.com/login",
    }
    return _defaults.get(board, "")


def _print_preauth_instructions(board: str, job_url: str, login_url_override: str = "") -> None:
    login_url = login_url_override or _derive_login_url(job_url, board)
    print("Pre-authentication is required before automation starts.")
    print("Important: PinchTab session is separate from your normal Chrome profile.")
    print("Being logged into Indeed in Chrome does not log PinchTab in.")
    if login_url:
        print(f"Use this login URL inside PinchTab: {login_url}")
    print("Recommended flow:")
    print("  1) Run bootstrap login first")
    print("  2) Complete login in the opened PinchTab tab (non-incognito)")
    print("  3) Run apply command after bootstrap succeeds")


def _prompt_for_manual_login(
    result: Dict[str, Any],
    board: str,
    timeout_sec: int,
    job_url: str = "",
) -> Optional[Dict[str, str]]:
    instance_id = result.get("instance_id")
    tab_id = result.get("tab_id")
    if not instance_id:
        print("Cannot continue manual login flow: instance context missing.")
        return None

    manager = BrowserManager(board=board)

    # Navigate the existing tab to the correct login page so the user can
    # actually sign in.  Deriving the URL from the job URL handles international
    # domains (pk.indeed.com, ca.indeed.com, etc.) correctly.
    login_url = _derive_login_url(job_url, board)
    if login_url and tab_id:
        print(f"\nNavigating PinchTab to login page: {login_url}")
        try:
            nav = manager.navigate(instance_id=instance_id, url=login_url)
            new_tab_id = nav.get("tab_id")
            if new_tab_id:
                tab_id = new_tab_id
                print(f"Login tab opened: {tab_id}")
        except PinchTabError as exc:
            print(f"Warning: could not navigate to login page: {exc}")

    print("\nPlease sign in to your account in the PinchTab browser window.")
    print(f"Instance: {instance_id}")
    print(f"Tab:      {tab_id}")
    print()
    print("=" * 60)
    print("MANUAL CREDENTIAL INPUT REQUIRED")
    print("=" * 60)
    print("  1. Enter your email / username in the browser")
    print("  2. Enter your password")
    print("  3. Do NOT click Sign In yet")
    print("  4. Do NOT solve the captcha manually")
    print("  5. Press Enter here — the captcha will be solved")
    print("     automatically before Sign In is clicked.")
    print("=" * 60)
    input("\nPress Enter after filling in credentials…")

    # --- CAPTCHA SOLVING via CapSolver (same API used in FlexVisitor.py) ---
    try:
        from agents.tools.application_boards.indeed_applicator import handle_login_captcha

        # Retrieve the live Playwright Page object from PinchTab's BrowserManager.
        # BrowserManager.get_page_for_tab() must return a Playwright Page; if your
        # BrowserManager exposes a different method name, update the call below.
        page = manager.get_page_for_tab(instance_id=instance_id, tab_id=tab_id)
        if page is None:
            raise RuntimeError("BrowserManager returned None for the requested tab.")

        # Site key is auto-detected from the live page by handle_login_captcha;
        # pass login_url so CapSolver knows which site to solve for.
        captcha_solved = handle_login_captcha(page, login_url)
        if captcha_solved:
            print("[Captcha] Captcha solved and injected.")
            print("You may now click Sign In in the browser, or the script will")
            print("proceed to click it automatically if IndeedApplicator.login()")
            print("is called as part of the retry flow.")
        else:
            print("[Captcha] Captcha solve returned False — you may need to solve it manually.")
    except Exception as exc:
        print(f"[Captcha Solve Error] {exc}")
        print("You may need to solve the captcha manually in the browser.")

    print("\nAfter Sign In completes, return here and press Enter to verify auth.")
    input()

    if tab_id:
        try:
            status = manager.wait_for_manual_login(
                tab_id=tab_id,
                timeout_sec=timeout_sec,
                poll_interval_sec=2.0,
            )
        except PinchTabError as exc:
            print(f"Manual login re-check failed: {exc}")
            return None

        if not bool(status.get("authenticated")):
            print(f"Login still not detected: {status.get('reason')}")
            return None

    print("Login confirmed. Retrying form fill using the authenticated tab first...")
    # Keep the authenticated tab context for retry. BrowserTool will attempt to
    # reuse this tab and only fall back to opening a new tab if it no longer exists.
    return {"instance_id": str(instance_id), "tab_id": str(tab_id) if tab_id else ""}


def _bootstrap_login(user_profile: Dict[str, Any], board: str, timeout_sec: int, login_url: str) -> int:
    _header("Login Bootstrap")
    manager = BrowserManager(board=board)
    try:
        session = manager.ensure_session(user_profile=user_profile, rotate_ip=False)
        instance_id = str(session.get("instance_id") or "")
        if not instance_id:
            print("FAIL: could not start PinchTab instance for bootstrap")
            return 1

        nav = manager.navigate(instance_id=instance_id, url=login_url)
        tab_id = str(nav.get("tab_id") or "")
        if not tab_id:
            print("FAIL: could not open login tab for bootstrap")
            return 1

        print("Mirrored-profile mode: login validation is skipped.")
        print(f"Instance: {instance_id}")
        print(f"Tab: {tab_id}")
        print("PASS: session initialized and ready for apply automation.")
        return 0
    except PinchTabError as exc:
        print(f"FAIL: login bootstrap failed: {exc}")
        return 1


def main() -> int:
    load_dotenv(".env.local")

    parser = argparse.ArgumentParser(description="Test PinchTab Indeed form fill by job URL")
    parser.add_argument("--url", help="Indeed job URL")
    parser.add_argument("--headless", action="store_true", help="Force headless browser mode")
    parser.add_argument("--user-id", help="Load user profile from Supabase by UUID")
    parser.add_argument("--name", default="Test User", help="Fallback full name")
    parser.add_argument("--email", default="test.user@example.com", help="Fallback email")
    parser.add_argument("--phone", default="+923001234567", help="Fallback phone")
    parser.add_argument("--location", default="Lahore, Pakistan", help="Fallback location")
    parser.add_argument(
        "--cover-letter",
        default="I am excited to apply for this role and believe my background is a strong fit.",
        help="Cover letter text used for form-fill testing",
    )
    parser.add_argument(
        "--cover-letter-file",
        help="Optional path to a text file containing cover letter content",
    )
    parser.add_argument(
        "--wait-for-login",
        action="store_true",
        default=False,
        help="When login wall is detected, pause for manual login and retry once (default: disabled)",
    )
    parser.add_argument(
        "--no-wait-for-login",
        dest="wait_for_login",
        action="store_false",
        help="Disable manual-login prompt/wait flow",
    )
    parser.add_argument(
        "--auth-timeout",
        type=int,
        default=300,
        help="Seconds to wait for login confirmation after pressing Enter",
    )
    parser.add_argument(
        "--board",
        default="indeed",
        help="Job board name for auth marker checks (default: indeed)",
    )
    parser.add_argument(
        "--bootstrap-login",
        action="store_true",
        help="Start/attach PinchTab session, open login page, and wait for manual login",
    )
    parser.add_argument(
        "--login-url",
        default=INDEED_LOGIN_URL,
        help="Login URL used by --bootstrap-login",
    )
    parser.add_argument(
        "--disable-proxy-rotation",
        action="store_true",
        help="Disable proxy/IP rotation for this run (helps avoid CAPTCHA loops)",
    )
    parser.add_argument(
        "--profile-prefix",
        help="Override PinchTab profile prefix for this run (use a fresh value to mimic incognito)",
    )
    parser.add_argument(
        "--fresh-profile",
        action="store_true",
        help="Use a unique temporary profile prefix for this run",
    )

    args = parser.parse_args()

    if not args.bootstrap_login and not args.url:
        print("ERROR: --url is required unless --bootstrap-login is used.")
        return 1

    _apply_runtime_overrides(args)

    _header("Indeed URL Fill Test")
    print(f"Target URL: {args.url or '[bootstrap mode]'}")
    print(f"Mode: {'headless' if args.headless else 'configured default'}")

    if args.url:
        parsed = urlparse(args.url)
        path_lower = parsed.path.lower()
        if "indeed." in parsed.netloc.lower() and "/viewjob" not in path_lower:
            print("WARNING: This looks like an Indeed search/listing URL, not a single job page.")
            print("Use a URL like: https://pk.indeed.com/viewjob?jk=<job_key>")

    try:
        if args.user_id:
            user_profile = _load_profile_from_supabase(args.user_id)
            print(f"Using Supabase profile for user_id: {args.user_id}")
        else:
            user_profile = _build_default_profile(args)
            print("Using CLI-provided fallback profile")

        if args.bootstrap_login:
            return _bootstrap_login(
                user_profile=user_profile,
                board=args.board,
                timeout_sec=max(30, int(args.auth_timeout)),
                login_url=args.login_url,
            )

        materials = _build_materials(args)

        browser = BrowserTool(headless=args.headless)
        result = browser.fill_application(
            job_url=args.url,
            job_board=args.board,
            materials=materials,
            user_profile=user_profile,
            require_preauth=True,
        )

        _header("Result")
        print(json.dumps(result, indent=2))

        if result.get("error"):
            print("\nFAIL: form fill did not complete")
            if result.get("preauth_required"):
                _print_preauth_instructions(
                    board=args.board,
                    job_url=args.url or "",
                    login_url_override=args.login_url,
                )
            if result.get("fallback_required"):
                print("Reason suggests CAPTCHA/login wall. Manual fallback is expected in this case.")
                if args.wait_for_login and not args.headless:
                    resume_context = _prompt_for_manual_login(
                        result=result,
                        board=args.board,
                        timeout_sec=max(30, int(args.auth_timeout)),
                        job_url=args.url or "",
                    )
                    if resume_context:
                        retry = browser.fill_application(
                            job_url=args.url,
                            job_board=args.board,
                            materials=materials,
                            user_profile=user_profile,
                            instance_id=resume_context.get("instance_id"),
                            tab_id=resume_context.get("tab_id"),
                            require_preauth=True,
                        )
                        _header("Retry Result")
                        print(json.dumps(retry, indent=2))
                        if not retry.get("error"):
                            print("\nPASS: form fill flow completed after manual login")
                            print("Review screenshot_path output for HITL approval before manual submission.")
                            return 0
                        print("\nFAIL: retry after manual login still did not complete")
                        return 1
                elif result.get("preauth_required"):
                    print("\nManual retry is disabled by default for reliability.")
                    print("Run with --bootstrap-login first, then rerun apply.")
            return 1

        print("\nPASS: form fill flow completed")
        print("Review screenshot_path output for HITL approval before manual submission.")
        return 0

    except Exception as exc:
        _header("Unexpected Error")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())