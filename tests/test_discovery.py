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

    def test_standalone_subagent_discovery_and_disabled_toggling(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            agents_dir = home / ".gemini" / "config" / "agents"
            agents_dir.mkdir(parents=True)

            # Active agent
            (agents_dir / "product-architect.md").write_text(
                "---\nname: product-architect\nrole: Product Architect\ndescription: Spec author\n---\nPrompt",
                encoding="utf-8",
            )

            # Disabled agent inside .disabled
            dis_dir = agents_dir / ".disabled"
            dis_dir.mkdir()
            (dis_dir / "code-reviewer.md").write_text(
                "---\nname: code-reviewer\nrole: Staff Code Reviewer\ndescription: Reviewer\n---\nPrompt",
                encoding="utf-8",
            )

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            active_sub = next((s for s in registry.subagents if s.name == "product-architect"), None)
            disabled_sub = next((s for s in registry.subagents if s.name == "code-reviewer"), None)

            self.assertIsNotNone(active_sub)
            self.assertTrue(active_sub.is_active)
            self.assertEqual(active_sub.tier, "GLOBAL")

            self.assertIsNotNone(disabled_sub)
            self.assertFalse(disabled_sub.is_active)

            # Test toggling active_sub off -> moves to .disabled/
            registry.toggle_item(active_sub)
            self.assertFalse(active_sub.is_active)
            self.assertTrue((dis_dir / "product-architect.md").is_file())
            self.assertFalse((agents_dir / "product-architect.md").is_file())

            # Test toggling disabled_sub on -> moves out of .disabled/
            registry.toggle_item(disabled_sub)
            self.assertTrue(disabled_sub.is_active)
            self.assertTrue((agents_dir / "code-reviewer.md").is_file())
            self.assertFalse((dis_dir / "code-reviewer.md").is_file())

    def test_workspace_plugin_isolation_and_exclusion(self):
        import json
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            # Global plugin
            plugin_dir = home / ".gemini" / "config" / "plugins" / "flutter"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.json").write_text(
                '{"name": "flutter", "version": "1.0.0", "description": "Flutter SDK"}',
                encoding="utf-8",
            )

            # Workspace excludes flutter via plugins.json
            ws_gemini = root / ".gemini"
            ws_gemini.mkdir()
            ws_plugins_json = ws_gemini / "plugins.json"
            ws_plugins_json.write_text(
                json.dumps({
                    "inherits": [
                        {
                            "path": "~/.gemini/config/plugins.json",
                            "exclude": ["flutter"],
                        }
                    ]
                }),
                encoding="utf-8",
            )

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            plug = next((p for p in registry.plugins if p.name == "flutter"), None)
            self.assertIsNotNone(plug)
            # Workspace exclusion should mark plugin as inactive
            self.assertFalse(plug.is_active)

    def test_zero_touch_personal_vault_invariant(self):
        """Verify that under no circumstances does agy-skills write into ~/.agents."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            # Create private git vault ~/.agents/
            personal_vault = home / ".agents"
            personal_vault.mkdir()
            (personal_vault / "secret-prompt.md").write_text("Confidential", encoding="utf-8")

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            # Run installs, toggles, discovery
            from agy_skills.cli import run_install
            from agy_skills.models import Scope
            run_install("superpowers", Scope.WORKSPACE, root, home)
            run_install("graphify", Scope.GLOBAL, root, home)

            # Personal vault must remain completely untouched
            self.assertEqual(list(personal_vault.iterdir()), [personal_vault / "secret-prompt.md"])
            self.assertFalse((personal_vault / "skills").exists())


if __name__ == "__main__":
    unittest.main()
