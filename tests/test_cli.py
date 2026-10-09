"""Unit tests for CLI diagnostic outputs."""

import io
from pathlib import Path
import sys
import tempfile
import unittest

from agy_skills.cli import print_info, print_lint, print_list
from agy_skills.discovery import CustomizationRegistry


class TestCLI(unittest.TestCase):
    def test_cli_list_and_lint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()

            skill_dir = root / ".agents" / "skills" / "sample-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: sample-skill\ndescription: A valid sample skill for testing CLI output.\n---\nBody",
                encoding="utf-8",
            )

            home = root / "fake_home"
            home.mkdir()

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)

            # Capture stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                print_list(registry)
                exit_code = print_lint(registry)
            finally:
                sys.stdout = sys.__stdout__

            output = captured.getvalue()
            self.assertIn("sample-skill", output)
            self.assertEqual(exit_code, 0)

    def test_cli_plugin_inspect_and_tokens(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()
            home = root / "fake_home"
            home.mkdir()

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            registry.discover_all()

            # Test print_tokens
            captured = io.StringIO()
            sys.stdout = captured
            try:
                from agy_skills.cli import print_tokens
                print_tokens(registry)
            finally:
                sys.stdout = sys.__stdout__

            tok_out = captured.getvalue()
            self.assertIn("20,000 tokens", tok_out)
            self.assertIn("Context Gauge:", tok_out)

    def test_cli_plugin_info_and_toggle(self):
        from agy_skills.cli import print_plugin_info, toggle_plugin_component_cli
        from agy_skills.models import ComponentBreakdown, Plugin, Scope

        bd1 = ComponentBreakdown(name="sub-tool-1", category="Mcp Tools", tokens=374, is_active=True, description="Tool 1")
        bd2 = ComponentBreakdown(name="sub-tool-2", category="Mcp Tools", tokens=374, is_active=True, description="Tool 2")
        plugin = Plugin(
            name="test-plugin",
            path=Path("/tmp/test-plugin"),
            version="1.0.0",
            tokens=748,
            is_active=True,
            scope=Scope.CATALOG,
            breakdowns=[bd1, bd2],
            mcp_tools=["sub-tool-1", "sub-tool-2"],
        )

        captured = io.StringIO()
        sys.stdout = captured
        try:
            print_plugin_info(plugin, show_breakdowns=True)
        finally:
            sys.stdout = sys.__stdout__

        info_out = captured.getvalue()
        self.assertIn("test-plugin", info_out)
        self.assertIn("sub-tool-1", info_out)
        self.assertIn("748", info_out)


if __name__ == "__main__":
    unittest.main()
