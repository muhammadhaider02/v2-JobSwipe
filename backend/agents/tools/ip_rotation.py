"""Proxy/IP rotation helper for PinchTab application sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProxyEntry:
    """Normalized proxy entry parsed from text file."""

    host: str
    port: int
    username: str = ""
    password: str = ""
    scheme: str = "http"

    @property
    def server(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    def to_pinchtab_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "scheme": self.scheme,
            "server": self.server,
            "proxyServer": self.server,
        }
        if self.username:
            payload["username"] = self.username
            payload["proxyUsername"] = self.username
        if self.password:
            payload["password"] = self.password
            payload["proxyPassword"] = self.password
        return payload


class IpRotationManager:
    """Round-robin proxy rotation backed by a local text file and state file."""

    def __init__(self, proxy_file_path: Path, state_file_path: Path, default_scheme: str = "http"):
        self.proxy_file_path = Path(proxy_file_path)
        self.state_file_path = Path(state_file_path)
        self.default_scheme = (default_scheme or "http").strip().lower() or "http"

    def _parse_proxy_line(self, line: str) -> Optional[ProxyEntry]:
        raw = (line or "").strip()
        if not raw or raw.startswith("#"):
            return None

        parts = [p.strip() for p in raw.split(":") if p.strip()]
        if len(parts) == 1:
            return ProxyEntry(host=parts[0], port=80, scheme=self.default_scheme)
        if len(parts) == 2:
            return ProxyEntry(host=parts[0], port=int(parts[1]), scheme=self.default_scheme)
        if len(parts) >= 4:
            return ProxyEntry(
                host=parts[0],
                port=int(parts[1]),
                username=parts[2],
                password=parts[3],
                scheme=self.default_scheme,
            )
        raise ValueError(f"Invalid proxy line format: {raw}")

    def _load_proxies(self) -> List[ProxyEntry]:
        if not self.proxy_file_path.exists():
            return []

        proxies: List[ProxyEntry] = []
        for line in self.proxy_file_path.read_text(encoding="utf-8").splitlines():
            entry = self._parse_proxy_line(line)
            if entry is not None:
                proxies.append(entry)
        return proxies

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_file_path.exists():
            return {"next_index": 0}
        try:
            return json.loads(self.state_file_path.read_text(encoding="utf-8"))
        except Exception:
            return {"next_index": 0}

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_file_path.write_text(json.dumps(state), encoding="utf-8")

    def get_next_proxy(self) -> Optional[ProxyEntry]:
        proxies = self._load_proxies()
        if not proxies:
            return None

        state = self._load_state()
        next_index = int(state.get("next_index", 0))
        selected = proxies[next_index % len(proxies)]
        state["next_index"] = (next_index + 1) % len(proxies)
        self._save_state(state)
        return selected

    def rotate_ip(self) -> Optional[Dict[str, Any]]:
        """Return the next proxy payload for PinchTab startup in round-robin order."""
        next_proxy = self.get_next_proxy()
        if next_proxy is None:
            return None
        return next_proxy.to_pinchtab_payload()
