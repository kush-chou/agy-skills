"""Unit tests for customization discovery."""

from pathlib import Path
import tempfile
import unittest

from agy_skills.discovery import CustomizationRegistry, find_workspace_root
from agy_skills.models import Scope


class TestDiscovery(unittest.TestCase):
    def test_find_workspace_root(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            git_dir = root / ".git"
            git_dir.mkdir()

            sub_dir = root / "src" / "pkg"
            sub_dir.mkdir(parents=True)

            found = find_workspace_root(sub_dir)
            self.assertEqual(found, root)

    def test_discover_workspace_items(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()

            # Create workspace skill
            skill_dir = root / ".agents" / "skills" / "local-helper"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: local-helper\ndescription: Project specific helper procedure.\n---\n# Steps\n1. Run",
                encoding="utf-8",
            )

            # Create workspace rule
            (root / "GEMINI.md").write_text("# Project guidelines\nDo not break builds.", encoding="utf-8")

            # Create fake home dir with no configs
            home = root / "fake_home"
            home.mkdir()

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            skills, rules = registry.discover_all()

            ws_skills = [s for s in skills if s.scope == Scope.WORKSPACE]
            ws_rules = [r for r in rules if r.scope == Scope.WORKSPACE]

            self.assertEqual(len(ws_skills), 1)
            self.assertEqual(ws_skills[0].name, "local-helper")
            self.assertEqual(len(ws_rules), 1)
            self.assertEqual(ws_rules[0].name, "GEMINI.md")

    def test_discover_mcp_servers_and_toggle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            # Create mock MCP server in ~/.gemini/antigravity/mcp/StitchMCP
            mcp_dir = home / ".gemini" / "antigravity" / "mcp" / "StitchMCP"
            mcp_dir.mkdir(parents=True)
            (mcp_dir / "instructions.md").write_text("# Stitch MCP Instructions", encoding="utf-8")
            (mcp_dir / "create_project.json").write_text("{}", encoding="utf-8")
            (mcp_dir / "list_screens.json").write_text("{}", encoding="utf-8")

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            self.assertEqual(len(registry.mcp_servers), 1)
            srv = registry.mcp_servers[0]
            self.assertEqual(srv.name, "StitchMCP")
            self.assertEqual(srv.tools_count, 2)
            self.assertIn("create_project", srv.tools)
            self.assertIn("list_screens", srv.tools)
            self.assertTrue(srv.is_active)
            self.assertIn("Stitch MCP Instructions", srv.instructions)

            # Test toggle
            registry.toggle_item(srv)
            self.assertFalse(srv.is_active)
            registry.toggle_item(srv)
            self.assertTrue(srv.is_active)

    def test_calibrated_plugin_metrics_and_component_toggle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            # Create mock plugin gemini-api
            plugin_dir = home / ".gemini" / "config" / "plugins" / "gemini-api"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.json").write_text(
                '{"name": "gemini-api", "version": "2.2.0", "description": "Google Gemini SDK"}',
                encoding="utf-8",
            )
            skills_dir = plugin_dir / "skills" / "gemini-api-dev"
            skills_dir.mkdir(parents=True)
            (skills_dir / "SKILL.md").write_text(
                "---\nname: gemini-api-dev\ndescription: Gemini Dev\n---\nBody",
                encoding="utf-8",
            )

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            plug = next((p for p in registry.plugins if p.name == "gemini-api"), None)
            self.assertIsNotNone(plug)
            # Must match official IDE calibration
            self.assertEqual(plug.tokens, 1314)
            self.assertEqual(plug.skills_tokens, 566)
            self.assertEqual(plug.mcp_tokens, 748)
            self.assertEqual(plug.version, "2.2.0")
            self.assertEqual(plug.excluded_tools_count, 1)

            # Test toggling individual subcomponent
            # Initially active tokens is 1314
            self.assertEqual(plug.active_tokens, 1314)
            # Toggle gemini_search_docs
            res = registry.toggle_plugin_component("gemini-api", "gemini_search_docs")
            self.assertFalse(res)
            # Should subtract 374 tokens
            self.assertEqual(plug.active_tokens, 1314 - 374)

    def test_plugin_state_resolution_from_config_json(self):
        import json
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            config_dir = home / ".gemini" / "config"
            plugin_dir = config_dir / "plugins" / "test-plug"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.json").write_text(
                '{"name": "test-plug", "version": "1.0.0", "description": "Test Plugin"}',
                encoding="utf-8",
            )

            # Persist disabled state in config.json
            config_file = config_dir / "config.json"
            config_file.write_text(
                json.dumps({"plugins": {"test-plug": {"enabled": False}}}),
                encoding="utf-8",
            )

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            plug = next((p for p in registry.plugins if p.name == "test-plug"), None)
            self.assertIsNotNone(plug)
            # Must reflect disabled state from config.json
            self.assertFalse(plug.is_active)
            self.assertEqual(registry.get_total_active_tokens(), 0)

            # Toggle plugin on
            registry.toggle_item(plug)
            self.assertTrue(plug.is_active)
            # config.json should be updated
            saved_cfg = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertTrue(saved_cfg["plugins"]["test-plug"]["enabled"])


if __name__ == "__main__":
    unittest.main()
