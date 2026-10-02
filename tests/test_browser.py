import unittest
from agy_skills.types import ScopeContext, SkillInfo
from agy_skills.manager import SkillManager
from agy_skills.browse import SkillBrowser

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
        self.assertFalse(self.browser.search_mode)

    def test_browser_structured_items(self):
        items = self.browser.get_structured_items()
        self.assertIsInstance(items, list)
        selectable = self.browser.get_selectable_indices(items)
        self.assertIsInstance(selectable, list)

    def test_load_skill_preview(self):
        info = SkillInfo(
            name="test-skill",
            description="A test skill with a somewhat long description to test word wrapping in hero card",
            path="/tmp/test_ws/.agents/skills/test-skill/SKILL.md",
            tier="workspace",
            is_symlink=False
        )
        preview = self.browser.load_skill_preview(info, width=60)
        self.assertTrue(len(preview) > 0)
        # Check hero title exists in output
        titles = [text for text, style in preview if style == "hero_title"]
        self.assertTrue(any("test-skill" in t for t in titles))

if __name__ == "__main__":
    unittest.main()
