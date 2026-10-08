"""Unit tests for the Antigravity Language Server plugin client."""

import json
import unittest
from unittest.mock import MagicMock, patch

from agy_skills.plugin_client import AntigravityPluginClient


class TestPluginClient(unittest.TestCase):
    def setUp(self):
        self.client = AntigravityPluginClient(address="localhost:5387", csrf_token="test_token")

    @patch("urllib.request.urlopen")
    def test_healthz_check(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.assertTrue(self.client.is_available())

    @patch("urllib.request.urlopen")
    def test_get_all_plugins(self, mock_urlopen):
        sample_data = {
            "plugins": [
                {
                    "name": "sample-plugin",
                    "path": "/path/to/plugins/sample-plugin",
                    "disabled": False,
                    "isGlobal": True,
                    "skills": [{"name": "sample-skill"}],
                    "agents": [],
                    "rules": [],
                    "mcpServers": [{"name": "sample-mcp"}],
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(sample_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        plugins = self.client.get_all_plugins()
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0]["name"], "sample-plugin")
        self.assertEqual(plugins[0]["dir"], "sample-plugin")
        self.assertFalse(plugins[0]["disabled"])
        self.assertEqual(plugins[0]["skills"], ["sample-skill"])
        self.assertEqual(plugins[0]["mcp"], ["sample-mcp"])

    @patch("urllib.request.urlopen")
    def test_set_plugin_enabled(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success = self.client.set_plugin_enabled("sample-plugin", True)
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
