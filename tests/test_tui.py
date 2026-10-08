"""Unit tests for the SkillManagerTUI component and interactions."""

from pathlib import Path
import tempfile
import unittest

from agy_skills.discovery import CustomizationRegistry
from agy_skills.models import Scope, Skill
from agy_skills.tui.app import SkillManagerTUI


class TestSkillManagerTUI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        (self.root / ".git").mkdir()

        # Workspace skill
        s_dir = self.root / ".agents" / "skills" / "demo-tool"
        s_dir.mkdir(parents=True)
        (s_dir / "SKILL.md").write_text(
            "---\nname: demo-tool\ndescription: A demo tool for verifying TUI behaviors.\nauthor: tester\n---\n# Docs",
            encoding="utf-8",
        )

        # Fake home dir
        self.home = self.root / "fake_home"
        self.home.mkdir()

        self.registry = CustomizationRegistry(workspace_root=self.root, home_dir=self.home)
        self.tui = SkillManagerTUI(self.registry)
        self.tui.refresh_data()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_initial_state_and_tabs(self):
        self.assertEqual(self.tui.active_tab, "skills")
        self.assertEqual(self.tui.target_scope, Scope.WORKSPACE)
        self.assertGreaterEqual(len(self.tui.tabs), 5)

    def test_grouped_items_and_filtering(self):
        grouped = self.tui.get_current_items_grouped()
        self.assertTrue(any("WORKSPACE" in title for title, _ in grouped))

        # Test filter text
        self.tui.filter_text = "demo"
        filtered_items = self.tui.get_flattened_selectable_items()
        self.assertEqual(len(filtered_items), 1)
        self.assertEqual(filtered_items[0].name, "demo-tool")

        # Test non-matching filter
        self.tui.filter_text = "non-existent-xyz"
        filtered_items = self.tui.get_flattened_selectable_items()
        self.assertEqual(len(filtered_items), 0)

    def test_toggle_and_token_meter(self):
        initial_tokens = self.registry.get_total_active_tokens()
        items = self.tui.get_flattened_selectable_items()
        self.assertTrue(len(items) > 0)

        demo_skill = next((i for i in items if i.name == "demo-tool"), None)
        self.assertIsNotNone(demo_skill)
        self.assertTrue(demo_skill.is_active)

        # Toggle skill off
        self.registry.toggle_item(demo_skill)
        self.assertFalse(demo_skill.is_active)
        self.assertLess(self.registry.get_total_active_tokens(), initial_tokens)

        # Toggle skill back on
        self.registry.toggle_item(demo_skill)
        self.assertTrue(demo_skill.is_active)
        self.assertEqual(self.registry.get_total_active_tokens(), initial_tokens)

    def test_activate_and_deactivate_all(self):
        items = self.tui.get_flattened_selectable_items()
        self.tui.registry.deactivate_all(items)
        for i in items:
            self.assertFalse(i.is_active)

        self.tui.registry.activate_all(items)
        for i in items:
            self.assertTrue(i.is_active)

    def test_tab_switching(self):
        # Switch to rules
        self.tui.active_tab_idx = 1
        self.assertEqual(self.tui.active_tab, "rules")

        # Switch to subagents
        self.tui.active_tab_idx = 2
        self.assertEqual(self.tui.active_tab, "subagents")
        subs = self.tui.get_flattened_selectable_items()
        self.assertTrue(any(s.name == "self" for s in subs))

        # Switch to plugins
        self.tui.active_tab_idx = 3
        self.assertEqual(self.tui.active_tab, "plugins")

        # Switch to mcp
        self.tui.active_tab_idx = 4
        self.assertEqual(self.tui.active_tab, "mcp")

        # Switch to marketplace
        self.tui.active_tab_idx = 5
        self.assertEqual(self.tui.active_tab, "marketplace")

        # Switch to status
        self.tui.active_tab_idx = 6
        self.assertEqual(self.tui.active_tab, "status")

    def test_render_mock(self):
        from unittest.mock import MagicMock
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (35, 120)

        # Test render each tab
        for idx in range(len(self.tui.tabs)):
            self.tui.active_tab_idx = idx
            self.tui._draw_top_banner(stdscr, 120)
            self.tui._draw_tab_bar(stdscr, 120)
            if self.tui.active_tab == "status":
                self.tui._draw_status_dashboard(stdscr, 35, 120)
            else:
                self.tui._draw_split_view(stdscr, 35, 120)
            self.tui._draw_footer(stdscr, 35, 120)

        self.assertGreater(stdscr.addstr.call_count, 10)


if __name__ == "__main__":
    unittest.main()
