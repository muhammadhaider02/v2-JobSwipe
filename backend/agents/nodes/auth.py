"""Authentication gate nodes for persistent PinchTab sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage

from agents.state import AgentState
from agents.tools.browser_manager import BrowserManager
from config.settings import get_settings
from services.pinchtab_service import PinchTabError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_auth_status_node(state: AgentState) -> Dict[str, Any]:
    """Ensure persistent browser context exists and verify session auth state."""
    target_job = state.get("target_job") or {}
    job_url = target_job.get("job_url")
    board = (target_job.get("board") or "indeed").lower()
    user_profile = state.get("user_profile") or {}

    if not job_url:
        msg = "No target job URL found for auth validation."
        return {"error": msg, "auth_status": "failed", "messages": [AIMessage(content=msg)]}

    try:
        manager = BrowserManager(board=board)
        session = manager.ensure_session(
            user_profile=user_profile,
            instance_id=state.get("browser_instance_id"),
        )
        instance_id = session.get("instance_id")

        nav = manager.navigate(instance_id=instance_id, url=job_url)
        tab_id = nav.get("tab_id")

        auth = manager.check_auth_status(tab_id=tab_id)
        is_authenticated = bool(auth.get("authenticated"))

        if is_authenticated:
            ok_msg = "Session validation passed. Existing login session is active."
            return {
                "browser_instance_id": instance_id,
                "browser_tab_id": tab_id,
                "auth_required": False,
                "auth_status": "authenticated",
                "auth_message": ok_msg,
                "application_status": state.get("application_status") or "ready",
                "messages": [AIMessage(content=ok_msg)],
            }

        wait_msg = "Session expired. Please log in manually in the opened browser window."
        return {
            "browser_instance_id": instance_id,
            "browser_tab_id": tab_id,
            "auth_required": True,
            "auth_status": "waiting_for_login",
            "auth_message": auth.get("reason", wait_msg),
            "login_wait_started_at": _now_iso(),
            "login_resume_requested": False,
            "resume_command": None,
            "application_status": "paused_auth",
            "messages": [AIMessage(content=wait_msg)],
        }

    except PinchTabError as exc:
        msg = f"PinchTab auth check failed: {exc}"
        return {
            "error": msg,
            "auth_status": "failed",
            "application_status": "error",
            "messages": [AIMessage(content=msg)],
        }


def wait_for_login_node(state: AgentState) -> Dict[str, Any]:
    """Pause until a resume command is issued, then re-check auth."""
    settings = get_settings()
    instance_id = state.get("browser_instance_id")
    tab_id = state.get("browser_tab_id")
    target_job = state.get("target_job") or {}
    board = (target_job.get("board") or "indeed").lower()

    if not instance_id or not tab_id:
        msg = "Missing browser session context for login wait state."
        return {"error": msg, "auth_status": "failed", "messages": [AIMessage(content=msg)]}

    resume_requested = bool(state.get("login_resume_requested"))
    resume_command = str(state.get("resume_command") or "").strip().lower()

    if not resume_requested and resume_command != "resume":
        wait_msg = "Session expired. Please log in manually in the opened browser window."
        return {
            "auth_required": True,
            "auth_status": "waiting_for_login",
            "application_status": "paused_auth",
            "messages": [AIMessage(content=wait_msg)],
        }

    try:
        manager = BrowserManager(board=board)

        # Re-check quickly after explicit human resume command.
        auth = manager.check_auth_status(tab_id=tab_id)
        if bool(auth.get("authenticated")):
            ok_msg = "Manual login confirmed. Resuming workflow."
            return {
                "auth_required": False,
                "auth_status": "authenticated",
                "auth_message": ok_msg,
                "login_resume_requested": False,
                "resume_command": None,
                "application_status": "ready",
                "messages": [AIMessage(content=ok_msg)],
            }

        # Optional bounded polling to absorb race conditions right after manual login.
        polled = manager.wait_for_manual_login(
            tab_id=tab_id,
            timeout_sec=min(60, settings.pinchtab_auth_wait_timeout_sec),
            poll_interval_sec=settings.pinchtab_auth_poll_interval_sec,
        )
        if bool(polled.get("authenticated")):
            ok_msg = "Manual login confirmed. Resuming workflow."
            return {
                "auth_required": False,
                "auth_status": "authenticated",
                "auth_message": ok_msg,
                "login_resume_requested": False,
                "resume_command": None,
                "application_status": "ready",
                "messages": [AIMessage(content=ok_msg)],
            }

        still_waiting_msg = "Login still required. Complete login and send Resume command again."
        return {
            "auth_required": True,
            "auth_status": "waiting_for_login",
            "auth_message": polled.get("reason", still_waiting_msg),
            "login_resume_requested": False,
            "resume_command": None,
            "application_status": "paused_auth",
            "messages": [AIMessage(content=still_waiting_msg)],
        }

    except PinchTabError as exc:
        msg = f"PinchTab login wait failed: {exc}"
        return {
            "error": msg,
            "auth_status": "failed",
            "application_status": "error",
            "messages": [AIMessage(content=msg)],
        }
