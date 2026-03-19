"""
BrowserManager for persistent PinchTab sessions with auth validation.

This manager keeps a stable profile session for job boards so users can log in
once and resume automation without repeated authentication walls.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.tools.ip_rotation import IpRotationManager
from config.settings import get_settings
from services.pinchtab_service import PinchTabError, get_pinchtab_service


class BrowserManager:
    """High-level persistent browsing manager for PinchTab-driven automation."""

    def __init__(self, board: str = "indeed"):
        self.settings = get_settings()
        self.service = get_pinchtab_service()
        self.board = (board or "indeed").lower()

        self.profile_data_path: Path = self.settings.pinchtab_profile_data_path
        self.profile_data_path.mkdir(parents=True, exist_ok=True)
        self.bootstrap_marker = self.profile_data_path / ".auth_bootstrap_done"
        self.ip_rotator = IpRotationManager(
            proxy_file_path=self.settings.pinchtab_proxy_list_path,
            state_file_path=self.profile_data_path / ".proxy_rotation_state.json",
            default_scheme=self.settings.pinchtab_proxy_scheme,
        )

    def _profile_name(self, user_profile: Dict[str, Any]) -> str:
        email = (user_profile.get("email") or "anonymous").strip().lower()
        safe_email = "".join(ch for ch in email if ch.isalnum() or ch in {"-", "_"})
        if not safe_email:
            safe_email = "anonymous"
        return f"{self.settings.pinchtab_profile_prefix}-{safe_email}"

    def _instance_is_running(self, instance_id: str) -> bool:
        for item in self.service.list_instances() or []:
            if str(item.get("id")) == str(instance_id):
                return str(item.get("status", "")).lower() == "running"
        return False

    def _is_auth_bootstrap_run(self) -> bool:
        return bool(self.settings.pinchtab_first_run_headed and not self.bootstrap_marker.exists())

    def ensure_session(
        self,
        user_profile: Dict[str, Any],
        instance_id: Optional[str] = None,
        rotate_ip: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Attach to an existing running instance or start a profile-backed session."""
        try:
            self.service.health()
        except PinchTabError as exc:
            raise PinchTabError(
                "PinchTab server is not reachable on http://127.0.0.1:9867. "
                "Start PinchTab before running campaign automation."
            ) from exc

        rotate_ip_enabled = bool(self.settings.pinchtab_proxy_rotation_enabled)
        rotate_now = bool(
            rotate_ip_enabled and
            (self.settings.pinchtab_rotate_ip_per_apply if rotate_ip is None else rotate_ip)
        )

        if instance_id and self._instance_is_running(instance_id):
            return {"instance_id": instance_id, "reused": True}

        profile_name = self._profile_name(user_profile)
        existing = self.service.find_instance_by_profile(profile_name)
        existing_running = bool(existing and str(existing.get("status", "")).lower() == "running")

        # For pre-auth flows, prioritize the already-running session even when rotate is enabled.
        if existing_running and self.settings.pinchtab_auth_session_priority:
            return {"instance_id": existing.get("id"), "reused": True}

        if existing_running and not rotate_now:
            return {"instance_id": existing.get("id"), "reused": True}

        proxy_payload = self.ip_rotator.rotate_ip() if rotate_now else None
        if rotate_now and existing_running and existing and existing.get("id"):
            try:
                self.stop_session(str(existing.get("id")))
            except Exception:
                pass

        auth_bootstrap = self._is_auth_bootstrap_run()
        mode = "headed" if auth_bootstrap else self.settings.pinchtab_mode

        # Keep this env override explicit so first-run auth can happen interactively.
        if auth_bootstrap:
            os.environ["PINCHTAB_HEADLESS"] = "false"
            os.environ["BRIDGE_HEADLESS"] = "false"

        created = self.service.start_instance(
            mode=mode,
            profile_name=profile_name,
            data_dir=str(self.profile_data_path),
            headless=False if auth_bootstrap else None,
            proxy=proxy_payload,
        )
        new_instance_id = created.get("id")
        if not new_instance_id:
            raise PinchTabError("PinchTab did not return instance id while starting persistent session.")

        if not self.service.wait_instance_ready(new_instance_id, timeout_sec=25):
            raise PinchTabError("PinchTab instance launched but did not become ready in time.")

        if auth_bootstrap:
            self.bootstrap_marker.touch(exist_ok=True)

        result = {"instance_id": new_instance_id, "reused": False}
        if proxy_payload:
            result["proxy_rotated"] = True
            result["proxy_server"] = proxy_payload.get("server") or proxy_payload.get("proxyServer")
        return result

    def navigate(
        self,
        instance_id: str,
        url: str,
        tab_id: Optional[str] = None,
        new_tab: Optional[bool] = None,
        timeout_sec: Optional[int] = None,
    ) -> Dict[str, Any]:
        nav = self.service.navigate(
            instance_id=instance_id,
            url=url,
            tab_id=tab_id,
            new_tab=new_tab,
            timeout_sec=timeout_sec,
        )
        tab_id = nav.get("tabId") or nav.get("tab_id") or nav.get("id")
        if not tab_id:
            raise PinchTabError("PinchTab did not return tab id after navigation.")
        return {"tab_id": tab_id, "raw": nav}

    def _auth_markers(self) -> List[str]:
        board_markers = {
            "indeed": ["sign in", "log in", "signin", "continue with google"],
            "mustakbil": ["sign in", "log in", "login", "register"],
            "linkedin": ["sign in", "join now", "login"],
            "greenhouse": ["sign in", "log in"],
            "lever": ["sign in", "log in"],
        }
        return board_markers.get(self.board, ["sign in", "log in", "login"])

    def check_auth_status(self, tab_id: str) -> Dict[str, Any]:
        """Inspect accessibility tree/text to determine if auth wall is present."""
        markers = self._auth_markers()

        snapshot = {}
        try:
            snapshot = self.service.snapshot_interactive(tab_id=tab_id)
        except PinchTabError:
            snapshot = {}

        snapshot_text = json.dumps(snapshot, ensure_ascii=True).lower()
        for marker in markers:
            if marker in snapshot_text:
                return {
                    "authenticated": False,
                    "reason": f"Auth marker detected in snapshot: '{marker}'",
                }

        raw_text = ""
        try:
            payload = self.service.text(tab_id=tab_id, mode="raw")
            raw_text = (payload.get("text") or "").lower()
        except PinchTabError:
            raw_text = ""

        for marker in markers:
            if marker in raw_text:
                return {
                    "authenticated": False,
                    "reason": f"Auth marker detected in text: '{marker}'",
                }

        return {"authenticated": True, "reason": "No login markers detected"}

    def wait_for_manual_login(
        self,
        tab_id: str,
        timeout_sec: Optional[int] = None,
        poll_interval_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Poll auth state until logged in or timeout is reached."""
        timeout = int(timeout_sec or self.settings.pinchtab_auth_wait_timeout_sec)
        poll = float(poll_interval_sec or self.settings.pinchtab_auth_poll_interval_sec)

        deadline = time.time() + max(timeout, 1)
        last_reason = "auth status unknown"
        while time.time() < deadline:
            status = self.check_auth_status(tab_id=tab_id)
            last_reason = status.get("reason", last_reason)
            if bool(status.get("authenticated")):
                return {"authenticated": True, "reason": "Manual login detected"}
            time.sleep(max(0.5, poll))

        return {
            "authenticated": False,
            "reason": f"Timeout waiting for manual login ({timeout}s). Last check: {last_reason}",
        }

    def find_stable_ref(self, tab_id: str, query: str) -> Optional[str]:
        match = self.service.find(tab_id=tab_id, query=query)
        return match.get("best_ref")

    def human_type(self, tab_id: str, ref: str, text: str) -> Dict[str, Any]:
        if not ref:
            raise PinchTabError("Stable element ref is required for humanType action.")
        return self.service.action(tab_id=tab_id, kind="humanType", ref=ref, text=text)

    def human_click(self, tab_id: str, ref: str) -> Dict[str, Any]:
        if not ref:
            raise PinchTabError("Stable element ref is required for humanClick action.")
        return self.service.action(tab_id=tab_id, kind="humanClick", ref=ref)

    def fill_with_stable_ref(self, tab_id: str, query: str, value: str) -> bool:
        """Find stable element ref by semantic query, then type with humanType."""
        if not value:
            return False
        ref = self.find_stable_ref(tab_id=tab_id, query=query)
        if not ref:
            return False
        self.human_type(tab_id=tab_id, ref=ref, text=value)
        return True

    def stop_session(self, instance_id: Optional[str]) -> None:
        if not instance_id:
            return
        try:
            self.service.stop_instance(instance_id=instance_id)
        except PinchTabError:
            # Non-fatal cleanup path.
            return
