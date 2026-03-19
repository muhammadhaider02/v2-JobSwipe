"""
PinchTab HTTP service wrapper.

Provides a small, typed integration layer for the local PinchTab server used by
campaign automation workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional

import requests

from config.settings import get_settings


class PinchTabError(Exception):
    """Raised when a PinchTab API operation fails."""


@dataclass
class PinchTabContext:
    """Tracks instance/tab identifiers for a workflow."""

    instance_id: str
    tab_id: str


class PinchTabService:
    """Thin HTTP client around PinchTab's API."""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.pinchtab_base_url.rstrip("/")
        self.token = settings.pinchtab_token.strip() if settings.pinchtab_token else ""
        self.timeout = max(int(settings.pinchtab_request_timeout_sec), 5)
        self.default_mode = settings.pinchtab_mode

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        expect_json: bool = True,
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json_body,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise PinchTabError(f"PinchTab request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text.strip()[:500]
            raise PinchTabError(f"PinchTab {method} {path} failed ({response.status_code}): {detail}")

        if not expect_json:
            return response.content

        if not response.text:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise PinchTabError(f"Invalid JSON from PinchTab {method} {path}") from exc

    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health")

    def _attach_proxy_payload(self, payload: Dict[str, Any], proxy: Optional[Dict[str, Any]]) -> None:
        if not proxy:
            return
        payload["proxy"] = proxy
        server = str(proxy.get("server") or proxy.get("proxyServer") or "").strip()
        username = str(proxy.get("username") or proxy.get("proxyUsername") or "").strip()
        password = str(proxy.get("password") or proxy.get("proxyPassword") or "").strip()
        if server:
            payload["proxyServer"] = server
        if username:
            payload["proxyUsername"] = username
        if password:
            payload["proxyPassword"] = password

    def start_instance(
        self,
        mode: Optional[str] = None,
        profile_name: Optional[str] = None,
        data_dir: Optional[str] = None,
        headless: Optional[bool] = None,
        proxy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        launch_mode = mode or self.default_mode
        payload: Dict[str, Any] = {"mode": launch_mode}
        if data_dir:
            payload["dataDir"] = data_dir
        if headless is not None:
            payload["headless"] = bool(headless)
        self._attach_proxy_payload(payload, proxy)

        if profile_name:
            profile_payload: Dict[str, Any] = {"headless": launch_mode == "headless"}
            if headless is not None:
                profile_payload["headless"] = bool(headless)
            if data_dir:
                profile_payload["dataDir"] = data_dir
            self._attach_proxy_payload(profile_payload, proxy)
            try:
                return self._request("POST", f"/profiles/{profile_name}/start", json_body=profile_payload)
            except PinchTabError as exc:
                # Fresh environments may not have this profile yet. Create it once,
                # then retry profile-based start so auth state is durable.
                msg = str(exc).lower()
                if "profile" not in msg or "not found" not in msg:
                    raise
                self.create_profile(profile_name)
                return self._request("POST", f"/profiles/{profile_name}/start", json_body=profile_payload)

        try:
            return self._request("POST", "/instances/start", json_body=payload)
        except PinchTabError:
            return self._request("POST", "/instances/launch", json_body=payload)

    def list_instances(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/instances")

    def list_profiles(self, include_all: bool = False) -> List[Dict[str, Any]]:
        params = {"all": "true"} if include_all else None
        return self._request("GET", "/profiles", params=params)

    def create_profile(self, profile_name: str) -> Dict[str, Any]:
        payload = {"name": profile_name}
        return self._request("POST", "/profiles", json_body=payload)

    def find_instance_by_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        for item in self.list_instances() or []:
            if str(item.get("profileName", "")).strip().lower() == profile_name.strip().lower():
                return item
        return None

    def wait_instance_ready(self, instance_id: str, timeout_sec: int = 20, poll_interval_sec: float = 0.75) -> bool:
        deadline = time.time() + max(timeout_sec, 1)
        while time.time() < deadline:
            try:
                instances = self.list_instances()
                if isinstance(instances, list):
                    for item in instances:
                        if str(item.get("id")) == str(instance_id):
                            status = str(item.get("status", "")).lower()
                            if status == "running":
                                return True
                            break
            except PinchTabError:
                pass
            time.sleep(max(poll_interval_sec, 0.1))
        return False

    def navigate(
        self,
        instance_id: str,
        url: str,
        tab_id: Optional[str] = None,
        new_tab: Optional[bool] = None,
        timeout_sec: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"instanceId": instance_id, "url": url}
        if tab_id:
            payload["tabId"] = tab_id
        if new_tab is not None:
            payload["newTab"] = bool(new_tab)
        if timeout_sec is not None:
            payload["timeout"] = max(int(timeout_sec), 1)
        try:
            return self._request("POST", "/navigate", json_body=payload)
        except PinchTabError as exc:
            msg = str(exc).lower()
            if "context deadline exceeded" in msg or "context canceled" in msg:
                # Instance is up but tab creation can race; quick retry often succeeds.
                time.sleep(1.0)
                return self._request("POST", "/navigate", json_body=payload)

            # Backward compatibility only when top-level endpoint is unavailable.
            if "404" not in msg:
                raise
            return self._request("POST", f"/instances/{instance_id}/navigate", json_body={"url": url})

    def snapshot(
        self,
        tab_id: str,
        *,
        filter_mode: str = "interactive",
        format_mode: str = "compact",
    ) -> Dict[str, Any]:
        params = {"tabId": tab_id, "filter": filter_mode, "format": format_mode}
        try:
            return self._request("GET", "/snap", params=params)
        except PinchTabError as exc:
            first_err = str(exc)

        # Legacy top-level endpoint fallback.
        try:
            return self._request("GET", "/snapshot", params=params)
        except PinchTabError as exc:
            second_err = str(exc)

        # Modern tab-scoped endpoint fallback used by some PinchTab builds.
        scoped_params = {"filter": filter_mode, "format": format_mode}
        try:
            return self._request("GET", f"/tabs/{tab_id}/snapshot", params=scoped_params)
        except PinchTabError as exc:
            third_err = str(exc)

        # Alternate scoped alias for compatibility.
        try:
            return self._request("GET", f"/tabs/{tab_id}/snap", params=scoped_params)
        except PinchTabError as exc:
            fourth_err = str(exc)

        raise PinchTabError(
            "PinchTab snapshot failed across all known endpoints: "
            f"/snap -> {first_err} | /snapshot -> {second_err} | "
            f"/tabs/{{tab}}/snapshot -> {third_err} | /tabs/{{tab}}/snap -> {fourth_err}"
        )

    def snapshot_interactive(self, tab_id: str) -> Dict[str, Any]:
        return self.snapshot(tab_id=tab_id, filter_mode="interactive", format_mode="compact")

    def text(self, tab_id: str, mode: str = "raw") -> Dict[str, Any]:
        params = {"tabId": tab_id, "mode": mode}
        return self._request("GET", "/text", params=params)

    def find(self, tab_id: str, query: str) -> Dict[str, Any]:
        payload = {"tabId": tab_id, "query": query}
        return self._request("POST", "/find", json_body=payload)

    def action(self, tab_id: str, kind: str, **kwargs: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"tabId": tab_id, "kind": kind}
        payload.update(kwargs)
        return self._request("POST", "/action", json_body=payload)

    def screenshot_bytes(self, tab_id: str) -> bytes:
        params = {"tabId": tab_id}
        return self._request("GET", "/screenshot", params=params, expect_json=False)

    def stop_instance(self, instance_id: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        return self._request("POST", f"/instances/{instance_id}/stop", json_body=payload)


_pinchtab_service: Optional[PinchTabService] = None


def get_pinchtab_service() -> PinchTabService:
    """Get shared PinchTab service instance."""
    global _pinchtab_service
    if _pinchtab_service is None:
        _pinchtab_service = PinchTabService()
    return _pinchtab_service
