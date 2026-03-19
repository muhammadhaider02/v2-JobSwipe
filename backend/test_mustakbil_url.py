"""
Standalone test script for PinchTab-based Mustakbil apply flow.

Usage examples:
  python test_mustakbil_url.py --url "https://www.mustakbil.com/jobs/job/..."
  python test_mustakbil_url.py --url "https://www.mustakbil.com/jobs/job/..." --headless
  python test_mustakbil_url.py --url "https://www.mustakbil.com/jobs/job/..." --user-id <uuid>

This script tests the current v1 behavior:
- Navigates with PinchTab
- Clicks Mustakbil Apply Now
- Attempts to answer Yes/No toggles
- Captures screenshot evidence for HITL review
- Does not submit the application
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

# Ensure backend imports resolve when running script directly.
sys.path.insert(0, str(Path(__file__).parent))

from agents.tools.browser_manager import BrowserManager
from agents.tools.browser_tool import BrowserTool
from config.settings import reload_settings
from services.pinchtab_service import PinchTabError
from services.supabase_service import get_supabase_service


MUSTAKBIL_LOGIN_URL = "https://www.mustakbil.com/"


def _open_mustakbil_login_from_home(manager: BrowserManager, tab_id: str) -> bool:
    """Open Mustakbil login UI from homepage by clicking the Login button."""
    for query in ("Login", "Log in", "Sign in"):
        try:
            ref = manager.find_stable_ref(tab_id=tab_id, query=query)
            if not ref:
                continue
            manager.human_click(tab_id=tab_id, ref=ref)
            return True
        except PinchTabError:
            continue
    return False


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

    screening_answers: Dict[str, str] = {}
    for item in args.answer or []:
        if "=" not in item:
            continue
        question, value = item.split("=", 1)
        screening_answers[question.strip()] = value.strip()

    return {
        "cover_letter": cover_letter,
        "optimized_resume": {},
        "screening_answers": screening_answers,
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

    reload_settings()

    if applied:
        print("Runtime overrides applied:")
        for key, value in applied.items():
            print(f"  {key}={value}")


def _derive_login_url(job_url: str, board: str) -> str:
    if board == "mustakbil":
        return MUSTAKBIL_LOGIN_URL

    if board == "indeed":
        return "https://secure.indeed.com/account/login"

    return ""


def _print_preauth_instructions(board: str, job_url: str, login_url_override: str = "") -> None:
    login_url = login_url_override or _derive_login_url(job_url, board)
    print("Pre-authentication is required before automation starts.")
    print("Important: PinchTab session is separate from your normal Chrome profile.")
    print("Being logged into your regular browser does not log PinchTab in.")
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

    login_url = _derive_login_url(job_url, board)
    if login_url and tab_id:
        print(f"\nNavigating PinchTab to login page: {login_url}")
        try:
            nav = manager.navigate(instance_id=instance_id, url=login_url, tab_id=tab_id, new_tab=False)
            new_tab_id = nav.get("tab_id")
            if new_tab_id:
                tab_id = new_tab_id
                print(f"Login tab reused: {tab_id}")
                if board == "mustakbil":
                    opened = _open_mustakbil_login_from_home(manager, tab_id)
                    if opened:
                        print("Mustakbil login button clicked.")
                    else:
                        print("Could not auto-click Mustakbil Login button. Please click it manually.")
        except PinchTabError as exc:
            print(f"Warning: could not navigate to login page: {exc}")

    print("\nPlease sign in to your account in the PinchTab browser window.")
    print(f"Instance: {instance_id}")
    print(f"Tab:      {tab_id}")
    print("After completing login, return here and press Enter to verify auth.")
    input()

    if tab_id:
        try:
            status = manager.wait_for_manual_login(tab_id=tab_id, timeout_sec=timeout_sec, poll_interval_sec=2.0)
        except PinchTabError as exc:
            print(f"Manual login re-check failed: {exc}")
            return None

        if not bool(status.get("authenticated")):
            print(f"Login still not detected: {status.get('reason')}")
            return None

    print("Login confirmed. Retrying apply flow using the authenticated tab first...")
    return {"instance_id": str(instance_id), "tab_id": str(tab_id) if tab_id else ""}


def _bootstrap_login(user_profile: Dict[str, Any], board: str, login_url: str) -> int:
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

        if board == "mustakbil":
            opened = _open_mustakbil_login_from_home(manager, tab_id)
            if opened:
                print("Mustakbil login button clicked.")
            else:
                print("Could not auto-click Mustakbil Login button. Please click it manually.")

        print("Session initialized in persistent profile mode.")
        print(f"Instance: {instance_id}")
        print(f"Tab: {tab_id}")
        print("PASS: session initialized and ready for apply automation.")
        return 0
    except PinchTabError as exc:
        print(f"FAIL: login bootstrap failed: {exc}")
        return 1


def main() -> int:
    load_dotenv(".env.local")

    parser = argparse.ArgumentParser(description="Test PinchTab Mustakbil apply flow by job URL")
    parser.add_argument("--url", help="Mustakbil job URL")
    parser.add_argument("--headless", action="store_true", help="Force headless browser mode")
    parser.add_argument("--user-id", help="Load user profile from Supabase by UUID")
    parser.add_argument("--name", default="Test User", help="Fallback full name")
    parser.add_argument("--email", default="test.user@example.com", help="Fallback email")
    parser.add_argument("--phone", default="+923001234567", help="Fallback phone")
    parser.add_argument("--location", default="Lahore, Pakistan", help="Fallback location")
    parser.add_argument(
        "--cover-letter",
        default="I am excited to apply for this role and believe my background is a strong fit.",
        help="Cover letter text used for testing",
    )
    parser.add_argument(
        "--cover-letter-file",
        help="Optional path to a text file containing cover letter content",
    )
    parser.add_argument(
        "--answer",
        action="append",
        help="Optional screening answer mapping as 'question fragment=yes|no'. Can be passed multiple times.",
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
        default="mustakbil",
        help="Job board name for auth marker checks (default: mustakbil)",
    )
    parser.add_argument(
        "--bootstrap-login",
        action="store_true",
        help="Start/attach PinchTab session, open login page, and keep same tab/profile",
    )
    parser.add_argument(
        "--login-url",
        default=MUSTAKBIL_LOGIN_URL,
        help="Login URL used by --bootstrap-login",
    )
    parser.add_argument(
        "--disable-proxy-rotation",
        action="store_true",
        help="Disable proxy/IP rotation for this run",
    )
    parser.add_argument(
        "--profile-prefix",
        help="Override PinchTab profile prefix for this run",
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

    _header("Mustakbil URL Apply Test")
    print(f"Target URL: {args.url or '[bootstrap mode]'}")
    print(f"Mode: {'headless' if args.headless else 'configured default'}")

    if args.url:
        parsed = urlparse(args.url)
        if "mustakbil.com" in parsed.netloc.lower() and "/jobs/" not in parsed.path.lower():
            print("WARNING: This looks like a listing URL, not a single job page.")

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

        board_actions = result.get("board_actions") or {}
        if args.board.lower() == "mustakbil" and not bool(board_actions.get("apply_clicked")):
            print("\nFAIL: Mustakbil Apply Now click did not succeed")
            return 1
        if args.board.lower() == "mustakbil" and not bool(board_actions.get("apply_transition_detected")):
            print("\nFAIL: Apply click happened but page did not transition to screening/apply state")
            print(f"Reason: {board_actions.get('apply_transition_reason') or 'No post-click transition marker detected.'}")
            return 1

        if result.get("error"):
            print("\nFAIL: apply flow did not complete")
            if result.get("preauth_required"):
                _print_preauth_instructions(
                    board=args.board,
                    job_url=args.url or "",
                    login_url_override=args.login_url,
                )
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
                        print("\nPASS: apply flow completed after manual login")
                        return 0
                    print("\nFAIL: retry after manual login still did not complete")
            return 1

        print("\nPASS: apply flow completed")
        return 0

    except Exception as exc:
        _header("Unexpected Error")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
