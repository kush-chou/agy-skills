import unittest
from agy_skills.types import ScopeContext, SkillInfo, RuleInfo, SubagentInfo
from agy_skills.manager import SkillManager
from agy_skills.browse import SkillBrowser, TAB_SKILLS, TAB_RULES, TAB_SUBAGENTS, TAB_PLUGINS

class TestBrowser(unittest.TestCase):
    def setUp(self):
        self.scope = ScopeContext(
            is_project_detected=True,
            workspace_root="/tmp/test_ws",
            workspace_skills_dir="/tmp/test_ws/.agents/skills",
            shared_skills_dir="/tmp/test_shared",
            global_agents_dir="/tmp/test_global",
            builtin_skills_dir="/tmp/test_builtin",
            catalog_dirs=["/tmp/test_catalog"]
        )
        self.mgr = SkillManager(self.scope)
        self.browser = SkillBrowser(self.mgr)

    def test_browser_initialization(self):
        self.assertEqual(self.browser.target_scope, "workspace")
        self.assertEqual(self.browser.selected_idx, 0)
        self.assertEqual(self.browser.active_tab, TAB_SKILLS)
        self.assertFalse(self.browser.search_mode)

    def test_browser_tabs_and_items(self):
        for tab in [TAB_SKILLS, TAB_RULES, TAB_SUBAGENTS, TAB_PLUGINS]:
            self.browser.active_tab = tab
            items = self.browser.get_items_for_current_tab()
            self.assertIsInstance(items, list)
            selectable = self.browser.get_selectable_indices(items)
            self.assertIsInstance(selectable, list)

    def test_budget_calculation(self):
        budget = self.mgr.calculate_budget()
        self.assertGreaterEqual(budget.total_tokens, 0)
        self.assertEqual(budget.max_tokens, 20000)
        self.assertIsInstance(budget.percentage, float)

    def test_load_item_preview(self):
        info = SkillInfo(
            name="test-skill",
            description="A test skill with a somewhat long description to test word wrapping in hero card",
            path="/tmp/test_ws/.agents/skills/test-skill/SKILL.md",
            tier="workspace",
            is_symlink=False
        )
        preview = self.browser.load_item_preview(info, "skill", width=60)
        self.assertTrue(len(preview) > 0)
        titles = [text for text, style in preview if style == "hero_title"]
        self.assertTrue(any("test-skill" in t for t in titles))

if __name__ == "__main__":
    unittest.main()
