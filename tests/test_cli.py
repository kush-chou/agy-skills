"""Unit tests for CLI diagnostic outputs."""

import io
from pathlib import Path
import sys
import tempfile
import unittest

from agy_skills.cli import print_info, print_lint, print_list
from agy_skills.discovery import CustomizationRegistry


class TestCLI(unittest.TestCase):
    def test_cli_list_and_lint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".git").mkdir()

            skill_dir = root / ".agents" / "skills" / "sample-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: sample-skill\ndescription: A valid sample skill for testing CLI output.\n---\nBody",
                encoding="utf-8",
            )

            home = root / "fake_home"
            home.mkdir()

            registry = CustomizationRegistry(workspace_root=root, home_dir=home)

            # Capture stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                print_list(registry)
                exit_code = print_lint(registry)
            finally:
                sys.stdout = sys.__stdout__

            output = captured.getvalue()
            self.assertIn("sample-skill", output)
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
