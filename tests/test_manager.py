import unittest
import tempfile
import os
import shutil
from agy_skills.types import ScopeContext
from agy_skills.manager import SkillManager

class TestSkillManager(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.workspace_skills = os.path.join(self.test_root, "workspace", "skills")
        self.shared_skills = os.path.join(self.test_root, "shared", "skills")
        self.global_agents = os.path.join(self.test_root, "global_agents")
        self.builtin_skills = os.path.join(self.test_root, "builtin", "skills")
        self.catalog_dir = os.path.join(self.test_root, "catalog")

        for d in [self.workspace_skills, self.shared_skills, self.global_agents, self.builtin_skills, self.catalog_dir]:
            os.makedirs(d, exist_ok=True)

        # Create a sample skill in catalog
        self.sample_skill_dir = os.path.join(self.catalog_dir, "test-skill")
        os.makedirs(self.sample_skill_dir, exist_ok=True)
        with open(os.path.join(self.sample_skill_dir, "SKILL.md"), "w") as f:
            f.write("---\nname: test-skill\ndescription: A test skill for verification\n---\n# Instructions\nDo testing.")

        self.scope = ScopeContext(
            workspace_root=os.path.join(self.test_root, "workspace"),
            workspace_skills_dir=self.workspace_skills,
            global_agents_dir=self.global_agents,
            shared_skills_dir=self.shared_skills,
            builtin_skills_dir=self.builtin_skills,
            catalog_dirs=[self.catalog_dir],
            is_project_detected=True,
        )
        self.manager = SkillManager(self.scope)

    def tearDown(self):
        shutil.rmtree(self.test_root)

    def test_scan_and_find_in_catalog(self):
        ws, shared, builtin, catalog = self.manager.scan_all()
        self.assertIn("test-skill", catalog)
        self.assertEqual(catalog["test-skill"].description, "A test skill for verification")

    def test_enable_and_disable_symlink_roundtrip(self):
        # Enable in workspace
        ok, msg = self.manager.enable("test-skill", target_tier="workspace")
        self.assertTrue(ok)
        dest = os.path.join(self.workspace_skills, "test-skill")
        self.assertTrue(os.path.islink(dest))

        # Check it is now in workspace and NOT in available catalog
        ws, shared, builtin, catalog = self.manager.scan_all()
        self.assertIn("test-skill", ws)
        self.assertNotIn("test-skill", catalog)

        # Disable
        ok, msg = self.manager.disable("test-skill", target_tier="workspace")
        self.assertTrue(ok)
        self.assertFalse(os.path.exists(dest))

        # Source in catalog remains untouched
        self.assertTrue(os.path.exists(os.path.join(self.sample_skill_dir, "SKILL.md")))

if __name__ == "__main__":
    unittest.main()
