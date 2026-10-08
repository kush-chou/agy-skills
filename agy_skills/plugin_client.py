"""Antigravity Language Server Connect RPC client for live plugin lifecycle operations."""

import json
import os
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request


class AntigravityPluginClient:
    """Client for interacting with the local Antigravity Language Server RPC service."""

    def __init__(self, address: Optional[str] = None, csrf_token: Optional[str] = None):
        self.address = address or os.environ.get("ANTIGRAVITY_LS_ADDRESS", "localhost:5387")
        self.csrf_token = csrf_token or os.environ.get("ANTIGRAVITY_CSRF_TOKEN", "")
        self.base_url = f"http://{self.address}"

    def is_available(self, timeout: float = 1.0) -> bool:
        """Check whether the Antigravity Language Server is running and responding."""
        try:
            url = f"{self.base_url}/healthz"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _rpc(self, method: str, payload: Dict[str, Any], timeout: float = 3.0) -> Optional[Dict[str, Any]]:
        """Execute a Connect RPC call against LanguageServerService."""
        url = f"{self.base_url}/exa.language_server_pb.LanguageServerService/{method}"
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-codeium-csrf-token": self.csrf_token,
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8")
                    return json.loads(body)
        except Exception:
            pass
        return None

    def get_all_plugins(self) -> List[Dict[str, Any]]:
        """Fetch all installed plugins and their live configuration state."""
        resp = self._rpc("GetAllPlugins", {})
        if not resp:
            return []

        raw_plugins = resp.get("plugins", [])
        cleaned = []
        for p in raw_plugins:
            path_str = p.get("path", "")
            dir_name = path_str.split("/")[-1] if path_str else p.get("name", "")
            cleaned.append({
                "name": p.get("name", ""),
                "dir": dir_name,
                "path": path_str,
                "disabled": p.get("disabled", False),
                "isGlobal": p.get("isGlobal", False),
                "skills": [s.get("name", "") for s in p.get("skills", []) if isinstance(s, dict)],
                "agents": [a.get("name", "") for a in p.get("agents", []) if isinstance(a, dict)],
                "rules": [r.get("absolutePath", "") for r in p.get("rules", []) if isinstance(r, dict)],
                "mcp": [m.get("name", "") for m in p.get("mcpServers", []) if isinstance(m, dict)],
            })
        return cleaned

    def set_plugin_enabled(self, dir_name: str, enabled: bool) -> bool:
        """Live toggle a plugin on or off via JetboxWriteState (no restart required)."""
        payload = {
            "userConfig": {
                "plugins": {
                    dir_name: {
                        "enabled": bool(enabled)
                    }
                }
            }
        }
        resp = self._rpc("JetboxWriteState", payload)
        return resp is not None

    def uninstall_plugin(self, dir_name: str) -> bool:
        """Uninstall a plugin via DeletePlugin."""
        # Ensure plugin is enabled first so stale disabled state isn't remembered on reinstall
        self.set_plugin_enabled(dir_name, True)
        payload = {"pluginId": dir_name}
        resp = self._rpc("DeletePlugin", payload)
        return resp is not None

    def install_plugin(self, marketplace_id: str) -> bool:
        """Install a plugin from the marketplace."""
        payload = {"id": marketplace_id}
        resp = self._rpc("InstallCustomization", payload)
        return resp is not None
