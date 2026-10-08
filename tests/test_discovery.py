"""Unit tests for customization discovery."""

from pathlib import Path
import tempfile
import unittest

from agy_skills.discovery import CustomizationRegistry, find_workspace_root
from agy_skills.models import Scope


class TestDiscovery(unittest.TestCase):
    def test_find_workspace_root(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            git_dir = root / ".git"
            git_dir.mkdir()

            sub_dir = root / "src" / "pkg"
            sub_dir.mkdir(parents=True)

            found = find_workspace_root(sub_dir)
            self.assertEqual(found, root)

    def test_discover_workspace_items(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()

            # Create workspace skill
            skill_dir = root / ".agents" / "skills" / "local-helper"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: local-helper\ndescription: Project specific helper procedure.\n---\n# Steps\n1. Run",
                encoding="utf-8",
            )

            # Create workspace rule
            (root / "GEMINI.md").write_text("# Project guidelines\nDo not break builds.", encoding="utf-8")

            # Create fake home dir with no configs
            home = root / "fake_home"
            home.mkdir()

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)
            skills, rules = registry.discover_all()

            ws_skills = [s for s in skills if s.scope == Scope.WORKSPACE]
            ws_rules = [r for r in rules if r.scope == Scope.WORKSPACE]

            self.assertEqual(len(ws_skills), 1)
            self.assertEqual(ws_skills[0].name, "local-helper")
            self.assertEqual(len(ws_rules), 1)
            self.assertEqual(ws_rules[0].name, "GEMINI.md")


if __name__ == "__main__":
    unittest.main()
