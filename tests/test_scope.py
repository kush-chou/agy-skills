import unittest
import tempfile
import os
import shutil
from agy_skills.scope import find_workspace_root, resolve_scope

class TestScopeResolution(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_find_workspace_root_with_git(self):
        # Create fake git repo
        git_dir = os.path.join(self.test_dir, "my_repo", ".git")
        os.makedirs(git_dir)
        sub_dir = os.path.join(self.test_dir, "my_repo", "src", "deep")
        os.makedirs(sub_dir)

        root = find_workspace_root(sub_dir)
        self.assertEqual(root, os.path.join(self.test_dir, "my_repo"))

    def test_find_workspace_root_with_agents_dir(self):
        # Create fake agents directory
        agents_dir = os.path.join(self.test_dir, "project", ".agents")
        os.makedirs(agents_dir)
        sub_dir = os.path.join(self.test_dir, "project", "pkg")
        os.makedirs(sub_dir)

        root = find_workspace_root(sub_dir)
        self.assertEqual(root, os.path.join(self.test_dir, "project"))

    def test_resolve_scope_project_detected(self):
        project_dir = os.path.join(self.test_dir, "app")
        os.makedirs(os.path.join(project_dir, ".git"))

        scope = resolve_scope(project_dir)
        self.assertTrue(scope.is_project_detected)
        self.assertEqual(scope.workspace_root, project_dir)
        self.assertEqual(scope.workspace_skills_dir, os.path.join(project_dir, ".agents", "skills"))

if __name__ == "__main__":
    unittest.main()
