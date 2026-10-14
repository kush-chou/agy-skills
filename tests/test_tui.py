"""Unit tests for the lean 2-pane SkillManagerTUI component and interactions."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

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
            "---\nname: demo-tool\ndescription: A demo tool for verifying TUI behaviors.\nauthor: tester\n---\n# Docs\nBody content.",
            encoding="utf-8",
        )

        # Workspace rule
        (self.root / "GEMINI.md").write_text("# Project Guidelines\nClean code.", encoding="utf-8")

        # Fake home dir
        self.home = self.root / "fake_home"
        self.home.mkdir()

        self.registry = CustomizationRegistry(workspace_root=self.root, home_dir=self.home)
        self.tui = SkillManagerTUI(self.registry)
        self.tui.refresh_data()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_initial_state_and_scope(self):
        self.assertEqual(self.tui.scope_filter, "ALL")
        self.assertEqual(self.tui.target_scope, Scope.WORKSPACE)
        self.assertEqual(self.tui.selected_index, 0)

    def test_grouped_items_and_filtering(self):
        grouped = self.tui.get_current_items_grouped()
        self.assertTrue(any("WORKSPACE SKILLS" in title for title, _ in grouped))
        self.assertTrue(any("WORKSPACE RULES" in title for title, _ in grouped))

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

    def test_scope_filter_cycling(self):
        self.assertEqual(self.tui.scope_filter, "ALL")
        self.tui._cycle_scope()
        self.assertEqual(self.tui.scope_filter, "WORKSPACE")
        self.tui._cycle_scope()
        self.assertEqual(self.tui.scope_filter, "GLOBAL")
        self.tui._cycle_scope()
        self.assertEqual(self.tui.scope_filter, "ALL")

    def test_render_mock(self):
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (35, 120)

        self.tui._draw_top_banner(stdscr, 120)
        self.tui._draw_split_view(stdscr, 35, 120)
        self.tui._draw_bottom_bar(stdscr, 35, 120)

        self.assertGreater(stdscr.addstr.call_count, 5)

    def test_responsive_footer(self):
        # On standard 80-column terminal, footer must fit and contain Filter and Quit
        foot_80 = self.tui._get_footer_text(80)
        self.assertLessEqual(len(foot_80), 79)
        self.assertIn("[/] Filter", foot_80)
        self.assertIn("[q] Quit", foot_80)

        # On wide terminals, full shortcut hints are provided
        foot_120 = self.tui._get_footer_text(120)
        self.assertIn("[Space] Toggle", foot_120)
        self.assertIn("[Tab] Scope", foot_120)
        self.assertIn("[q] Quit", foot_120)

        # On narrow terminal, essential shortcuts fit
        foot_60 = self.tui._get_footer_text(60)
        self.assertLessEqual(len(foot_60), 59)
        self.assertIn("[q] Quit", foot_60)

    def test_responsive_footer_all_widths(self):
        for w in range(40, 140):
            foot = self.tui._get_footer_text(w)
            self.assertLessEqual(len(foot), w - 1, f"Footer exceeded terminal width at w={w}")
            self.assertIn("[q] Quit", foot)

    def test_split_view_divider(self):
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (35, 80)

        self.tui._draw_split_view(stdscr, 35, 80)
        calls = [args[0][2] for args in stdscr.addstr.call_args_list]
        self.assertTrue(any("│" in str(c) for c in calls))

    def test_markdown_renderer(self):
        sample_md = (
            "# Main Title\n"
            "This is a **bold** paragraph with `inline_code`.\n\n"
            "## Sub Section\n"
            "- First bullet item with **details**\n"
            "- Second bullet item\n\n"
            "| Col A | Col B |\n"
            "| :--- | :--- |\n"
            "| Val 1 | Val 2 |\n\n"
            "```python\n"
            "def foo():\n"
            "    return True\n"
            "```\n"
        )
        rendered = self.tui._render_markdown(sample_md, 60)
        rendered_texts = [txt for txt, _ in rendered]

        # Verify headings without #
        self.assertTrue(any("◆ Main Title" in t for t in rendered_texts))
        self.assertFalse(any(t.startswith("# ") for t in rendered_texts))
        self.assertTrue(any("▸ Sub Section" in t for t in rendered_texts))

        # Verify bullets use clean bullet character
        self.assertTrue(any("• First bullet item with details" in t for t in rendered_texts))

        # Verify raw markdown syntax stripped
        self.assertFalse(any("**bold**" in t for t in rendered_texts))

        # Verify code block borders
        self.assertTrue(any("┌─ [ python ]" in t for t in rendered_texts))
        self.assertTrue(any("│ def foo():" in t for t in rendered_texts))
        self.assertTrue(any("└" in t for t in rendered_texts))


    def test_delete_item(self):
        rule = next((i for i in self.tui.get_flattened_selectable_items() if i.name == "GEMINI.md"), None)
        self.assertIsNotNone(rule)
        path = rule.path
        self.assertTrue(path.exists())

        # Test delete
        self.registry.delete_item(rule)
        self.assertFalse(path.exists())
        self.tui.refresh_data()
        self.assertIsNone(next((i for i in self.tui.get_flattened_selectable_items() if i.name == "GEMINI.md"), None))


if __name__ == "__main__":
    unittest.main()

