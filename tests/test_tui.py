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

    def test_responsive_footer(self):
        # On standard 80-column terminal, footer must fit and contain Filter and Quit
        foot_80 = self.tui._get_footer_text(80)
        self.assertLessEqual(len(foot_80), 79)
        self.assertIn("[/] Filter", foot_80)
        self.assertIn("[q] Quit", foot_80)

        # On wide terminals, full shortcut labels are provided
        foot_120 = self.tui._get_footer_text(120)
        self.assertIn("Breakdowns", foot_120)
        self.assertIn("Toggle/Install", foot_120)
        self.assertIn("[q] Quit", foot_120)

        # On narrow terminal, essential shortcuts fit
        foot_60 = self.tui._get_footer_text(60)
        self.assertLessEqual(len(foot_60), 59)
        self.assertIn("[q] Quit", foot_60)

    def test_markdown_renderer(self):
        sample_md = (
            "# Main Title\n"
            "This is a **bold** paragraph with `inline_code`.\n\n"
            "## Sub Section\n"
            "- First bullet item with **details**\n"
            "- Second bullet item\n\n"
            "| Column A | Column B |\n"
            "| :--- | :--- |\n"
            "| **Val 1** | `Val 2` |\n\n"
            "```python\n"
            "def foo():\n"
            "    return True\n"
            "```\n"
        )
        rendered = self.tui._render_markdown(sample_md, 60)
        rendered_texts = [txt for txt, _ in rendered]

        # Verify heading rendered cleanly without #
        self.assertTrue(any("◆ Main Title" in t for t in rendered_texts))
        self.assertFalse(any(t.startswith("# ") for t in rendered_texts))
        self.assertTrue(any("▸ Sub Section" in t for t in rendered_texts))
        self.assertFalse(any(t.startswith("## ") for t in rendered_texts))

        # Verify bullets use clean bullet character
        self.assertTrue(any("• First bullet item with details" in t for t in rendered_texts))

        # Verify raw markdown syntax stripped
        self.assertFalse(any("**bold**" in t for t in rendered_texts))
        self.assertFalse(any("`inline_code`" in t for t in rendered_texts))

        # Verify table formatted with column dividers rather than raw :---
        self.assertTrue(any("Column A │ Column B" in t for t in rendered_texts))
        self.assertTrue(any("─┼─" in t for t in rendered_texts))
        self.assertFalse(any(":---" in t for t in rendered_texts))
        self.assertTrue(any("Val 1" in t and "Val 2" in t and "│" in t for t in rendered_texts))

        # Verify code block borders
        self.assertTrue(any("┌─ [ python ]" in t for t in rendered_texts))
        self.assertTrue(any("│ def foo():" in t for t in rendered_texts))
        self.assertTrue(any("└────" in t for t in rendered_texts))

    def test_tab_bar_target_badge_clean(self):
        from unittest.mock import MagicMock
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (35, 80)

        # On 80-column terminal, TARGET badge must NOT be rendered to avoid orphan label
        self.tui._draw_tab_bar(stdscr, 80)
        calls_80 = [args[0][2] for args in stdscr.addstr.call_args_list]
        self.assertFalse(any("TARGET:" in str(c) for c in calls_80))

        # On 120-column terminal, TARGET badge should be rendered
        stdscr.reset_mock()
        stdscr.getmaxyx.return_value = (35, 120)
        self.tui._draw_tab_bar(stdscr, 120)
        calls_120 = [args[0][2] for args in stdscr.addstr.call_args_list]
        self.assertTrue(any("TARGET: [WORKSPACE]" in str(c) for c in calls_120))

    def test_split_view_divider_and_truncation(self):
        from unittest.mock import MagicMock
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (35, 80)

        self.tui._draw_split_view(stdscr, 35, 80)
        calls = [args[0][2] for args in stdscr.addstr.call_args_list]
        # Vertical divider line must be rendered
        self.assertTrue(any("│" in str(c) for c in calls))

    def test_tab_bar_all_tabs_visible_on_80_col(self):
        from unittest.mock import MagicMock
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (35, 80)

        self.tui._draw_tab_bar(stdscr, 80)
        calls_80 = [args[0][2] for args in stdscr.addstr.call_args_list]
        # Tab 7: Status must be fully visible and NOT truncated as " 7: Sta"
        self.assertTrue(any("7: Status" in str(c) for c in calls_80))

    def test_top_banner_not_truncated_on_80_col(self):
        from unittest.mock import MagicMock
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (35, 80)

        # Set active tokens to a large number that previously overflowed
        self.tui.registry.token_budget = 20000
        self.tui._draw_top_banner(stdscr, 80)
        banner_text = stdscr.addstr.call_args_list[0][0][2]
        self.assertLessEqual(len(banner_text), 79)
        self.assertTrue(banner_text.endswith("%)"))

    def test_markdown_renderer_pipes_and_unclosed_blocks(self):
        # A normal sentence containing | should NOT be rendered as a table with ─┼─
        non_table_md = "This is option A | option B in a sentence."
        rendered = self.tui._render_markdown(non_table_md, 60)
        texts = [t for t, _ in rendered]
        self.assertFalse(any("─┼─" in t for t in texts))
        self.assertTrue(any("option A" in t and "option B" in t for t in texts))

        # Unclosed code block should have closing border
        unclosed_code_md = "```python\nprint('hello')\n"
        rendered_code = self.tui._render_markdown(unclosed_code_md, 60)
        code_texts = [t for t, _ in rendered_code]
        self.assertTrue(any(t.startswith("└") for t in code_texts))

    def test_responsive_footer_all_widths(self):
        # Test all integer widths from 50 to 140
        for w in range(50, 140):
            foot = self.tui._get_footer_text(w)
            self.assertLessEqual(len(foot), w - 1, f"Footer exceeded terminal width at w={w}")
            self.assertIn("[q] Quit", foot)
            self.assertIn("[/] Filter", foot)


if __name__ == "__main__":
    unittest.main()

