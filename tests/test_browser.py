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

    def test_browser_filter_and_items(self):
        items = self.browser.get_items()
        self.assertIsInstance(items, list)

    def test_load_skill_preview(self):
        info = SkillInfo(
            name="test-skill",
            description="A test skill",
            path="/tmp/test_ws/.agents/skills/test-skill/SKILL.md",
            tier="workspace",
            is_symlink=False
        )
        # Should gracefully handle non-existent file in preview
        preview = self.browser.load_skill_preview(info)
        self.assertTrue(len(preview) > 0)
        self.assertIn("Name: test-skill", preview[0])

if __name__ == "__main__":
    unittest.main()
