import unittest
import tempfile
import os
import shutil
from agy_skills.types import ScopeContext, SkillInfo, RuleInfo, SubagentInfo
from agy_skills.manager import SkillManager
from agy_skills.browse import SkillBrowser, TAB_SKILLS, TAB_RULES, TAB_SUBAGENTS, TAB_PLUGINS

class TestBrowser(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.ws_skills = os.path.join(self.test_root, "ws_skills")
        self.ws_rules = os.path.join(self.test_root, "ws_rules")
        os.makedirs(self.ws_skills, exist_ok=True)
        os.makedirs(self.ws_rules, exist_ok=True)

        self.sample_skill = os.path.join(self.ws_skills, "sample", "SKILL.md")
        os.makedirs(os.path.dirname(self.sample_skill), exist_ok=True)
        with open(self.sample_skill, "w") as f:
            f.write("---\nname: sample\ndescription: Sample skill\n---\nLine 1\nLine 2\n")

        self.scope = ScopeContext(
            is_project_detected=True,
            workspace_root=self.test_root,
            workspace_skills_dir=self.ws_skills,
            shared_skills_dir=os.path.join(self.test_root, "shared"),
            global_agents_dir=os.path.join(self.test_root, "global"),
            builtin_skills_dir=os.path.join(self.test_root, "builtin"),
            catalog_dirs=[],
            workspace_rules_dir=self.ws_rules,
        )
        self.mgr = SkillManager(self.scope)
        self.browser = SkillBrowser(self.mgr)

    def tearDown(self):
        shutil.rmtree(self.test_root)

    def test_browser_initialization(self):
        self.assertEqual(self.browser.target_scope, "workspace")
        self.assertEqual(self.browser.selected_idx, 0)
        self.assertEqual(self.browser.active_tab, TAB_SKILLS)
        self.assertFalse(self.browser.search_mode)
        self.assertFalse(self.browser.edit_mode)

    def test_browser_tabs_and_items(self):
        for tab in [TAB_SKILLS, TAB_RULES, TAB_SUBAGENTS, TAB_PLUGINS]:
            self.browser.active_tab = tab
            items = self.browser.get_items_for_current_tab()
            self.assertIsInstance(items, list)
            selectable = self.browser.get_selectable_indices(items)
            self.assertIsInstance(selectable, list)

    def test_nano_editor_open_and_writeout(self):
        info = SkillInfo(
            name="sample",
            description="Sample skill",
            path=self.sample_skill,
            tier="workspace"
        )
        # 1. Enter edit mode
        self.browser.enter_edit_mode(info, "skill")
        self.assertTrue(self.browser.edit_mode)
        self.assertIn("Line 1", self.browser.edit_lines)

        # 2. Mutate in-memory lines
        self.browser.edit_lines.append("Line 3 modified")
        self.browser.edit_dirty = True

        # 3. Save In-Place
        ok, msg = self.browser.write_out_file(fork=False)
        self.assertTrue(ok)
        with open(self.sample_skill, "r") as f:
            saved_content = f.read()
        self.assertIn("Line 3 modified", saved_content)

        # 4. Fork as (user)
        ok_fork, msg_fork = self.browser.write_out_file(fork=True)
        self.assertTrue(ok_fork)
        fork_path = os.path.join(self.ws_skills, "sample-user", "SKILL.md")
        self.assertTrue(os.path.isfile(fork_path))

    def test_nano_editor_discard_and_exit(self):
        info = SkillInfo(
            name="sample",
            description="Sample skill",
            path=self.sample_skill,
            tier="workspace"
        )
        self.browser.enter_edit_mode(info, "skill")
        self.browser.edit_lines.append("Temporary unwanted line")
        self.browser.edit_dirty = True

        # Discard & Exit
        self.browser.discard_changes(exit_editor=True)
        self.assertFalse(self.browser.edit_mode)
        self.assertFalse(self.browser.edit_dirty)

        # File on disk remains untouched
        with open(self.sample_skill, "r") as f:
            content = f.read()
        self.assertNotIn("Temporary unwanted line", content)

    def test_nano_editor_discard_revert_disk(self):
        info = SkillInfo(
            name="sample",
            description="Sample skill",
            path=self.sample_skill,
            tier="workspace"
        )
        self.browser.enter_edit_mode(info, "skill")
        self.browser.edit_lines.append("Another unwanted edit")
        self.browser.edit_dirty = True

        # Revert in-place (stay in editor)
        self.browser.discard_changes(exit_editor=False)
        self.assertTrue(self.browser.edit_mode)
        self.assertFalse(self.browser.edit_dirty)
        self.assertNotIn("Another unwanted edit", self.browser.edit_lines)

    def test_batch_toggle_collection(self):
        # Create a catalog skill in @android collection
        android_dir = os.path.join(self.test_root, "catalog", "android-tool")
        os.makedirs(android_dir, exist_ok=True)
        with open(os.path.join(android_dir, "SKILL.md"), "w") as f:
            f.write("---\nname: android-tool\ndescription: Android tool\n---\n")

        self.scope.catalog_dirs = [os.path.join(self.test_root, "catalog")]
        self.browser.active_tab = TAB_PLUGINS
        items = self.browser.get_items_for_current_tab()
        selectable = self.browser.get_selectable_indices(items)
        self.assertGreater(len(selectable), 0)

        # Batch activate @android
        msg = self.browser.batch_toggle_collection("@android", enable=True)
        self.assertIn("Activated", msg)

        # Batch disable @android
        msg_disable = self.browser.batch_toggle_collection("@android", enable=False)
        self.assertIn("Disabled", msg_disable)

if __name__ == "__main__":
    unittest.main()
